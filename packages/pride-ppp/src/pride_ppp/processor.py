"""PrideProcessor — concurrent-safe RINEX → kinematic position pipeline.

Owns all internal state (ProductEnvironment, WorkSpace, DependencySpec).
Each ``process()`` call runs pdp3 in a date-partitioned working directory
(``pride_dir/{year}/{doy}/``) so concurrent calls never collide.
"""

from __future__ import annotations

import datetime
import enum
import logging
import re
import shutil
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from itertools import groupby
from pathlib import Path
from typing import Dict, List, Literal, LiteralString, Optional, Sequence, Union
import tempfile
import pandas as pd

from gnss_ppp_products import (
    DependencyResolver,
    ProductEnvironment,
    QueryFactory,
    ResourceFetcher,
    WorkSpace,
)
from gnss_ppp_products.configs import (
    CENTERS_RESOURCE_DIR,
    FORMAT_SPEC_YAML,
    LOCAL_SPEC_DIR,
    META_SPEC_YAML,
    PRODUCT_SPEC_YAML,
)
from gnss_ppp_products.specifications.dependencies.dependencies import (
    DependencyResolution,
    DependencySpec,
)

from .cli import PrideCLIConfig
from .config import PRIDEPPPFileConfig, SatelliteProducts
from .defaults import (
    PRIDE_CENTERS_DIR,
    PRIDE_DIR_SPEC,
    PRIDE_INSTALL_SPEC,
    PRIDE_PPPAR_FINAL_SPEC,
    PRIDE_PPPAR_SPEC,
    PRIDE_PRODUCT_SPEC,
)
from .output import get_wrms_from_res, kin_to_kin_position_df
from .rinex import rinex_get_time_range

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Processing mode
# ---------------------------------------------------------------------------


class ProcessingMode(enum.Enum):
    """Product timeliness mode.

    Controls which dependency-spec YAML is used for product resolution.

    * ``DEFAULT`` — cascades through FIN → RAP → ULT (best available).
    * ``FINAL``   — only accepts final (FIN) products.
    * ``RAPID``   — only accepts rapid (RAP) products.
    """

    DEFAULT = "default"
    FINAL = "final"


_MODE_TO_SPEC: Dict[ProcessingMode, Path] = {
    ProcessingMode.DEFAULT: PRIDE_PPPAR_SPEC,
    ProcessingMode.FINAL: PRIDE_PPPAR_FINAL_SPEC,
}

# Regex for inferring 4-char site ID from RINEX filenames.
# Matches the leading 4 alphabetic characters of the filename stem.
_SITE_RE = re.compile(r"^([A-Za-z0-9]{4})")

# Spec name → SatelliteProducts field mapping
_SPEC_TO_PRODUCT_FIELD: Dict[str, str] = {
    "ORBIT": "satellite_orbit",
    "CLOCK": "satellite_clock",
    "BIA": "code_phase_bias",
    "ATTOBX": "quaternions",
    "ERP": "erp",
}


# ---------------------------------------------------------------------------
# Result
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ProcessingResult:
    """Immutable result from a single RINEX → kinematic processing run.

    Attributes
    ----------
    rinex_path : Path
        Path to the input RINEX observation file.
    site : str
        4-character station identifier (e.g. ``"NCC1"``).
    date : datetime.date
        Observation date for this processing run.
    kin_path : Path or None
        Path to the output ``.kin`` file, or ``None`` if pdp3 did not
        produce one.
    res_path : Path or None
        Path to the output ``.res`` residuals file, or ``None``.
    config_path : Path
        Path to the ``config_file`` used for this run.
    resolution : DependencyResolution
        Product resolution result (fulfilled and missing dependencies).
    returncode : int
        pdp3 process exit code (0 = success).
    stderr : str
        Captured stderr from the pdp3 subprocess.
    """

    rinex_path: Path
    site: str
    date: datetime.date
    kin_path: Optional[Path]
    res_path: Optional[Path]
    config_path: Path
    resolution: DependencyResolution
    returncode: int = 0
    stderr: str = ""

    @property
    def success(self) -> bool:
        """``True`` if pdp3 produced a valid .kin output file."""
        return self.kin_path is not None and self.kin_path.exists()

    def positions(self) -> Optional[pd.DataFrame]:
        """Parse the ``.kin`` file into a DataFrame with WRMS residuals.

        Returns
        -------
        pd.DataFrame or None
            Kinematic position DataFrame, or ``None`` if the run failed.
        """
        if not self.success or self.kin_path is None:
            return None
        return kin_to_kin_position_df(self.kin_path)

    def residuals(self) -> Optional[pd.DataFrame]:
        """Parse the ``.res`` file into a WRMS DataFrame.

        Returns
        -------
        pd.DataFrame or None
            WRMS residuals indexed by timestamp, or ``None``.
        """
        if self.res_path is None or not self.res_path.exists():
            return None
        return get_wrms_from_res(self.res_path)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _infer_site(rinex: Path) -> str:
    """Extract a 4-character site identifier from a RINEX filename.

    Matches the first four alphanumeric characters of the filename stem
    (e.g. ``NCC12540.25o`` → ``NCC1``).  Falls back to ``"SIT1"`` when
    the filename does not conform to the expected RINEX naming convention.

    Args:
        rinex: Path to a RINEX observation file.

    Returns:
        Uppercase 4-char site ID.
    """
    m = _SITE_RE.match(rinex.stem)
    return m.group(1).upper() if m else "SIT1"


def _resolution_to_satellite_products(
    resolution: DependencyResolution,
) -> tuple[SatelliteProducts, Optional[Path]]:
    """Map a dependency resolution to PRIDE-PPPAR satellite product paths.

    Iterates over the fulfilled dependencies in *resolution* and extracts
    the local filenames for each product category that pdp3 needs
    (orbits, clocks, biases, quaternions, ERP).  The resulting
    ``SatelliteProducts`` instance is written directly into the PRIDE
    config file.

    Only the **first** fulfilled dependency per category is used (the
    resolver already returns them in preference order).

    Args:
        resolution: A completed ``DependencyResolution`` from the resolver.

    Returns:
        A 2-tuple of ``(SatelliteProducts, product_directory)``.
        *product_directory* is the common parent directory of the resolved
        product files, or ``None`` if no products were fulfilled.
    """
    product_fields: Dict[str, str] = {}
    product_dir: Optional[Path] = None

    for rd in resolution.fulfilled:
        # Map the spec name (e.g. "ORBIT") to the SatelliteProducts field name
        field_name = _SPEC_TO_PRODUCT_FIELD.get(rd.spec)
        if field_name is None or field_name in product_fields:
            continue
        path = rd.local_path
        if path is None:
            continue
        product_fields[field_name] = path.name
        # Use the first product's parent as the common product directory
        if product_dir is None:
            product_dir = path.parent

    return (
        SatelliteProducts(
            satellite_orbit=product_fields.get("satellite_orbit"),
            satellite_clock=product_fields.get("satellite_clock"),
            code_phase_bias=product_fields.get("code_phase_bias"),
            quaternions=product_fields.get("quaternions"),
            erp=product_fields.get("erp"),
            product_directory=str(product_dir) if product_dir else "Default",
        ),
        product_dir,
    )


def _resolution_to_table_dir(resolution: DependencyResolution) -> Optional[Path]:
    """Locate the directory containing ANTEX / reference table files.

    Scans fulfilled dependencies for the ``ATTATX`` spec (antenna phase
    centre corrections) and returns its parent directory.  pdp3 uses this
    as the ``table_directory`` in its config file to find ancillary data
    (ANTEX, leap-second table, satellite metadata, etc.).

    Args:
        resolution: A completed ``DependencyResolution``.

    Returns:
        Parent directory of the ANTEX file, or ``None`` if not resolved.
    """
    for rd in resolution.fulfilled:
        if rd.spec in "ATTATX":
            path = rd.local_path
            if path is not None:
                return path.parent
    return None


def _write_config(
    satellite_products: SatelliteProducts,
    table_dir: Optional[Path],
    dest: Path,
) -> Path:
    """Write a PRIDE-PPPAR ``config_file`` to disk.

    Loads the default config template, injects the resolved satellite
    product filenames and table directory, then serialises to *dest*.
    Parent directories are created automatically.

    Args:
        satellite_products: Resolved product paths for orbits, clocks, etc.
        table_dir: Directory containing ANTEX and reference tables.
        dest: Target path for the config file (e.g.
              ``pride_dir/2025/015/config_file``).

    Returns:
        The path that was written (same as *dest*).
    """
    config = PRIDEPPPFileConfig.load_default()
    config.satellite_products = satellite_products
    config.observation.table_directory = str(table_dir) if table_dir else "Default"
    dest.parent.mkdir(parents=True, exist_ok=True)
    config.write_config_file(dest)
    return dest


# ---------------------------------------------------------------------------
# PrideProcessor
# ---------------------------------------------------------------------------


class PrideProcessor:
    """Facade: RINEX file in → kinematic positions out.

    Owns its own ProductEnvironment and WorkSpace.  No global state.
    Thread-safe for concurrent ``process()`` calls.

    Attributes
    ----------
    _pride_dir : Path
        Root directory for PRIDE products and working state.
    _output_dir : Path
        Final destination for ``.kin`` / ``.res`` output files.
    _pride_install_dir : Path or None
        Optional path to an existing PRIDE-PPPAR installation.
    _cli_config : PrideCLIConfig
        Configuration for pdp3 CLI flag generation.
    _mode : ProcessingMode
        Product timeliness mode (DEFAULT or FINAL).
    _env : ProductEnvironment
        Fully-built product environment (immutable after construction).
    _dep_spec : DependencySpec
        Dependency specification governing product resolution.
    _workspace : WorkSpace
        Maps logical sink IDs to physical directories.
    _qf : QueryFactory
        Translates (spec, date, params) into concrete download queries.
    _fetcher : ResourceFetcher
        Shared HTTP fetcher for downloading products.
    """

    def __init__(
        self,
        pride_dir: Path,
        output_dir: Path,
        *,
        pride_install_dir: Optional[Path] = None,
        cli_config: Optional[PrideCLIConfig] = PrideCLIConfig(),
        mode: Union[
            ProcessingMode, Literal["FINAL", "DEFAULT"]
        ] = ProcessingMode.DEFAULT,
    ) -> None:
        """Initialise the processor and all its owned subsystems.

        Construction is intentionally *eager*: the ProductEnvironment is
        built, all spec YAMLs are parsed, and the WorkSpace is registered
        so that every subsequent ``process()`` / ``process_batch()`` call
        can proceed without further setup.

        Args:
            pride_dir: Root directory for PRIDE products and working state.
                Config files and pdp3 working directories will be written
                under ``pride_dir/{year}/{doy}/``.
            output_dir: Final destination for ``.kin`` / ``.res`` output
                files produced by pdp3.
            pride_install_dir: Optional path to a PRIDE-PPPAR installation
                that provides additional table files.  When set, its spec
                is registered on the WorkSpace.
            cli_config: Override the default pdp3 CLI flags.  When ``None``
                a default ``PrideCLIConfig`` (kinematic, 1 s, loose edit)
                is used.
            mode: Product timeliness mode.  Selects which dependency-spec
                YAML governs product resolution:

                * ``ProcessingMode.DEFAULT`` — FIN → RAP → ULT cascade.
                * ``ProcessingMode.FINAL``   — only FINAL products.

                Also accepts the string literals ``"DEFAULT"`` or
                ``"FINAL"`` for convenience.
        """
        if isinstance(mode, str):
            mode = ProcessingMode(mode.upper())
        self._pride_dir = Path(pride_dir)
        self._output_dir = Path(output_dir)
        self._pride_install_dir = Path(pride_install_dir) if pride_install_dir else None
        self._cli_config = cli_config if cli_config is not None else PrideCLIConfig()
        self._mode = mode

        # Build private ProductEnvironment (immutable after .build()).
        # Loads parameter metadata, format specs, product specs (including
        # PRIDE-specific products), and all analysis-centre resource specs.
        self._env = self._build_env()

        # Load the DependencySpec that matches the requested processing mode.
        # The dep-spec controls which TTT (timeliness) values the resolver
        # will accept — e.g. FINAL mode restricts TTT to [FIN].
        spec_path = _MODE_TO_SPEC[self._mode]
        self._dep_spec = DependencySpec.from_yaml(spec_path)
        logger.info("Processing mode: %s  (spec: %s)", mode.value, spec_path.name)

        # Build and register the WorkSpace — maps logical sink IDs ("pride",
        # "pride_install") to physical directories on disk so resolved
        # products know where to land.
        self._workspace = self._build_workspace()

        # QueryFactory translates (spec, date, parameters) into concrete
        # queries that the ResourceFetcher can execute against remote hosts.
        self._qf = QueryFactory(
            product_environment=self._env, workspace=self._workspace
        )
        # Shared HTTP fetcher — reusable across multiple resolve() calls.
        self._fetcher = ResourceFetcher(max_connections=10)

    # ------------------------------------------------------------------ #
    # Private construction helpers
    # ------------------------------------------------------------------ #

    def _build_env(self) -> ProductEnvironment:
        """Construct and finalise the ``ProductEnvironment``.

        Loads, in order:

        1. **Parameter metadata** — dimension names, allowed values.
        2. **Format spec** — file naming templates (SP3, CLK, …).
        3. **Product specs** — the core product catalogue *and* the
           PRIDE-specific product catalogue (tables, ocean models, etc.).
        4. **Resource specs** — per-analysis-centre YAML files that
           describe where each product lives on the remote servers.
           Both the shared ``CENTERS_RESOURCE_DIR`` and the PRIDE-specific
           ``PRIDE_CENTERS_DIR`` are scanned.

        Returns:
            A fully built (immutable) ``ProductEnvironment``.
        """
        env = ProductEnvironment()
        env.add_parameter_spec(META_SPEC_YAML)
        env.add_format_spec(FORMAT_SPEC_YAML)
        env.add_product_spec(PRODUCT_SPEC_YAML)
        env.add_product_spec(PRIDE_PRODUCT_SPEC, id="pride")
        for path in Path(CENTERS_RESOURCE_DIR).glob("*.yaml"):
            env.add_resource_spec(path)
        if PRIDE_CENTERS_DIR.is_dir():
            for path in PRIDE_CENTERS_DIR.glob("*.yaml"):
                env.add_resource_spec(path)
        env.build()
        return env

    def _build_workspace(self) -> WorkSpace:
        """Create the ``WorkSpace`` and register local directory specs.

        A WorkSpace maps logical *sink IDs* to physical base directories.
        After registration, the resolver can materialise files under:

        * ``"pride"``          → ``self._pride_dir``
        * ``"pride_install"``  → ``self._pride_install_dir`` (optional)

        Returns:
            A configured ``WorkSpace`` ready for use by the ``QueryFactory``.
        """
        ws = WorkSpace()
        for path in Path(LOCAL_SPEC_DIR).glob("*.yaml"):
            ws.add_resource_spec(path)

        ws.add_resource_spec(PRIDE_DIR_SPEC)
        ws.add_resource_spec(PRIDE_INSTALL_SPEC)

        ws.register_spec(
            base_dir=self._pride_dir,
            spec_ids=["pride_config"],
            alias="pride",
        )
        if self._pride_install_dir:
            ws.register_spec(
                base_dir=self._pride_install_dir,
                spec_ids=["pride_install_config"],
                alias="pride_install",
            )
        return ws

    # ------------------------------------------------------------------ #
    # Resolution (per-call fresh resolver)
    # ------------------------------------------------------------------ #

    def _resolve(
        self,
        date: datetime.datetime,
        local_sink_id: str = "pride",
    ) -> DependencyResolution:
        """Resolve all dependencies for a single UTC date.

        Creates a fresh ``DependencyResolver`` (stateless) and delegates
        to it.  The resolver walks the dependency spec's preference list
        (centre × timeliness) top-down and for each product either verifies
        a local copy already exists or downloads it.

        Args:
            date: Target date (midnight UTC) for product resolution.
            local_sink_id: WorkSpace alias that receives downloaded files.
                Defaults to ``"pride"`` which maps to ``self._pride_dir``.

        Returns:
            A ``DependencyResolution`` containing fulfilled and missing
            product entries.
        """
        resolver = DependencyResolver(
            dep_spec=self._dep_spec,
            product_environment=self._env,
            query_factory=self._qf,
            fetcher=self._fetcher,
        )
        resolution, _ = resolver.resolve(
            date=date,
            local_sink_id=local_sink_id,
        )
        return resolution

    # ------------------------------------------------------------------ #
    # Directory helpers
    # ------------------------------------------------------------------ #

    def _working_dir(self, date: datetime.date) -> Path:
        """Return ``pride_dir/{year}/{doy}/``, creating it if needed."""
        doy = date.timetuple().tm_yday
        d = self._pride_dir / str(date.year) / f"{doy:03d}"
        d.mkdir(parents=True, exist_ok=True)
        return d

    # ------------------------------------------------------------------ #
    # Subprocess execution
    # ------------------------------------------------------------------ #
    def _build_pdp_command(
        self, rinex: Path, site: str, config_path: Path
    ) -> List[str]:
        """Assemble the full ``pdp3`` command-line invocation.

        Clones the processor's CLI config, overriding
        ``pride_configfile_path`` with the date-specific config file, then
        generates the argument list via ``PrideCLIConfig.generate_pdp_command``.

        Args:
            rinex: Path to the observation file passed to pdp3.
            site: 4-char site identifier (e.g. ``"NCC1"``).
            config_path: The ``config_file`` written by ``_write_config``.

        Returns:
            A list of strings suitable for ``subprocess.run()``.
        """
        cli = PrideCLIConfig(
            **{
                **self._cli_config.model_dump(),
                "pride_configfile_path": config_path,
            }
        )
        return cli.generate_pdp_command(site=site, local_file_path=str(rinex))

    @staticmethod
    def _run_pdp3(
        command: List[str],
        site: str,
        output_dir: Path,
    ) -> tuple[Optional[Path], Optional[Path], int, str]:
        """Execute pdp3 in *working_dir* and move outputs to *output_dir*.

        pdp3 writes intermediate files (ambiguity tables, residual grids)
        into its current working directory.  We point it at the persistent
        ``pride_dir/{year}/{doy}/`` directory so these artefacts are
        available for inspection after the run.

        After execution the method searches recursively for ``kin_*`` and
        ``res_*`` output files matching *site*, appends ``.kin`` / ``.res``
        extensions, and moves them to *output_dir*.

        Args:
            command: Full pdp3 argument list from ``_build_pdp_command``.
            site: 4-char site ID used to locate output files by pattern.
            working_dir: Directory where pdp3 runs (``cwd``).
            output_dir: Final destination for ``.kin`` / ``.res`` files.

        Returns:
            ``(kin_path, res_path, returncode, stderr)`` where paths are
            ``None`` when the corresponding output was not produced.

        Raises:
            FileNotFoundError: If the ``pdp3`` binary is not on ``PATH``.
        """
        if not shutil.which("pdp3"):
            raise FileNotFoundError("pdp3 binary not found in PATH")

        with tempfile.TemporaryDirectory() as tmpdir:
            # Run pdp3 as a blocking subprocess, capturing all output
            result = subprocess.run(
                command,
                cwd=tmpdir,
                capture_output=True,
                text=True,
            )

            # Replay stdout/stderr through the logger for observability
            if result.stdout:
                for line in result.stdout.strip().splitlines():
                    logger.info(line)
            if result.stderr:
                for line in result.stderr.strip().splitlines():
                    logger.warning(line)

            # pdp3 writes outputs as e.g. "kin_2025254_ncc1" (no extension).
            # Search recursively in the working dir to find them.
            kin_files = list(Path(tmpdir).rglob(f"kin_*_{site.lower()}"))
            res_files = list(Path(tmpdir).rglob(f"res_*_{site.lower()}"))

            kin_out: Optional[Path] = None
            res_out: Optional[Path] = None

            output_dir.mkdir(parents=True, exist_ok=True)

            # Move outputs to the final output directory with proper extensions
            if kin_files:
                src = kin_files[0]
                dst = output_dir / (src.name + ".kin")
                shutil.move(str(src), str(dst))
                kin_out = dst
                logger.info("Generated kin file %s", dst)

            if res_files:
                src = res_files[0]
                dst = output_dir / (src.name + ".res")
                shutil.move(str(src), str(dst))
                res_out = dst
                logger.info("Generated res file %s", dst)

        return kin_out, res_out, result.returncode, result.stderr

    def _build_kin_res_paths(
        self, date: datetime.datetime, site: str, output_dir: Path
    ) -> tuple[Optional[Path], Optional[Path]]:
        """Construct the expected ``.kin`` and ``.res`` output paths.

        The naming convention mirrors what pdp3 produces:
        ``kin_{YYYY}{DOY}_{site}.kin`` and ``res_{YYYY}{DOY}_{site}.res``.
        These paths are used to check for pre-existing valid output
        before launching a new pdp3 run.

        Args:
            date: The observation date (used for YYYY and DOY components).
            site: Lowercase 4-char site ID.
            output_dir: Directory where outputs are stored.

        Returns:
            ``(kin_path, res_path)`` — both may point to non-existent files.
        """
        doy = date.timetuple().tm_yday
        kin_name = f"kin_{date.year}{doy:03d}_{site.lower()}.kin"
        res_name = f"res_{date.year}{doy:03d}_{site.lower()}.res"
        kin_path = output_dir / kin_name
        res_path = output_dir / res_name
        return kin_path, res_path

    def _validate_kinfile(self, kin_path: Path, override: bool = False) -> bool:
        """Check whether a ``.kin`` output file already contains valid data.

        When *override* is ``True`` the check is skipped entirely and the
        method returns ``False`` (i.e. "no valid cached result") so that
        the caller always re-runs pdp3.

        When *override* is ``False`` the method returns ``True`` only if
        *kin_path* exists on disk **and** can be successfully parsed into
        a non-empty DataFrame of kinematic positions.

        Args:
            kin_path: Expected location of the ``.kin`` file.
            override: Force re-processing regardless of existing output.

        Returns:
            ``True`` if a valid, parseable output already exists.
        """
        if not override:
            if not kin_path.exists():
                return False
            # Attempt to parse the kinfile — only accept it if it yields data
            kin_df: Optional[pd.DataFrame] = kin_to_kin_position_df(kin_path)
            if kin_df and not kin_df.empty:
                return True
        return False

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    def process(
        self,
        rinex: Path,
        *,
        site: Optional[str] = None,
        date: Optional[datetime.date] = None,
        override: bool = False,
    ) -> ProcessingResult:
        """Process one RINEX file end-to-end.

        This is the primary single-file entry point.  The full pipeline is:

        1. **Infer metadata** — site ID and observation date are extracted
           from the RINEX filename / header if not provided explicitly.
        2. **Resolve products** — the ``DependencyResolver`` walks the
           preference cascade (centre × timeliness) and downloads any
           missing products to ``pride_dir``.
        3. **Check cache** — if a valid ``.kin`` output already exists in
           ``output_dir`` and *override* is ``False``, the run is skipped
           and a cached ``ProcessingResult`` is returned immediately.
        4. **Write config** — a ``config_file`` is written to
           ``pride_dir/{year}/{doy}/``.
        5. **Run pdp3** — the binary is executed with ``cwd`` set to the
           same ``{year}/{doy}/`` directory.  Outputs are moved to
           ``output_dir``.

        Args:
            rinex: Path to the RINEX observation file.
            site: 4-char site ID.  Inferred from the filename if omitted.
            date: Override observation date.  When ``None`` the date is
                  extracted from the RINEX header via
                  ``rinex_get_time_range``.
            override: When ``True``, re-run pdp3 even if a valid ``.kin``
                      file already exists.

        Returns:
            A ``ProcessingResult`` summarising the run outcome, including
            paths to output files, the resolved products, and pdp3's
            return code.

        Raises:
            FileNotFoundError: If *rinex* does not exist.
        """
        rinex = Path(rinex)
        if not rinex.exists():
            raise FileNotFoundError(f"RINEX file not found: {rinex}")

        # --- 1. Infer metadata ------------------------------------------------
        if site is None:
            site = _infer_site(rinex)

        # Determine date
        if date is None:
            ts_start, _ = rinex_get_time_range(rinex)
            start_date = (
                ts_start.date() if isinstance(ts_start, datetime.datetime) else ts_start
            )
        else:
            start_date = date if isinstance(date, datetime.date) else date.date()

        # Normalise to midnight UTC for the resolver
        target_dt = datetime.datetime(
            start_date.year,
            start_date.month,
            start_date.day,
            tzinfo=datetime.timezone.utc,
        )

        # --- 2. Resolve products ----------------------------------------------
        logger.info("Resolving products for %s (site=%s)", start_date, site)
        resolution = self._resolve(target_dt)
        logger.info(resolution.summary())

        # --- 3. Check cache ---------------------------------------------------
        kin_file, res_file = self._build_kin_res_paths(
            date=target_dt, site=site, output_dir=self._output_dir
        )
        if self._validate_kinfile(kin_file, override=override):
            logger.info(
                "Valid output already exists for %s on %s, skipping pdp3 run",
                site,
                start_date,
            )
            return ProcessingResult(
                rinex_path=rinex,
                site=site,
                date=start_date,
                kin_path=kin_file,
                res_path=res_file if res_file and res_file.exists() else None,
                config_path=Path("(cached)"),
                resolution=resolution,
            )

        if not resolution.all_required_fulfilled:
            missing = [r.spec for r in resolution.missing if r.required]
            logger.error("Missing required products: %s", missing)

        # --- 4. Write config --------------------------------------------------
        # Config is persisted at pride_dir/{year}/{doy}/config_file so it can
        # be inspected after the run and reused by subsequent pdp3 calls for
        # the same date.
        work_dir = self._working_dir(start_date)
        sat_products, _ = _resolution_to_satellite_products(resolution)
        table_dir = _resolution_to_table_dir(resolution)
        config_path = _write_config(sat_products, table_dir, work_dir / "config_file")
        command = self._build_pdp_command(
            rinex=rinex, site=site, config_path=config_path
        )

        # --- 5. Run pdp3 ------------------------------------------------------
        kin_path, res_path, returncode, stderr = self._run_pdp3(
            command=command,
            site=site,
            output_dir=self._output_dir,
        )

        return ProcessingResult(
            rinex_path=rinex,
            site=site,
            date=start_date,
            kin_path=kin_path,
            res_path=res_path,
            config_path=config_path,
            resolution=resolution,
            returncode=returncode,
            stderr=stderr,
        )

    def process_batch(
        self,
        rinex_files: Sequence[Path],
        *,
        sites: Optional[Sequence[str]] = None,
        max_workers: int = 1,
        override: bool = False,
    ) -> List[ProcessingResult]:
        """Process multiple RINEX files, sharing product resolution per date.

        This is the preferred entry point when processing many files.
        The pipeline is structured to minimise redundant network calls:

        1. **Group by date** — RINEX files are sorted by observation date
           so that product resolution (the expensive step) happens exactly
           once per unique date.
        2. **Resolve & write configs** — for each unique date, resolve
           products and write a ``config_file`` to the year/doy working
           directory under ``pride_dir``.
        3. **Skip cached results** — any RINEX whose ``.kin`` output
           already exists and validates is returned immediately without
           running pdp3 (unless *override* is ``True``).
        4. **Dispatch pdp3** — remaining jobs are dispatched to a
           ``ThreadPoolExecutor`` for parallel subprocess execution.
           Resolution and config generation are always single-threaded
           (main thread) to avoid race conditions.

        Args:
            rinex_files: Paths to RINEX observation files.
            sites: Per-file 4-char site IDs.  When ``None``, inferred from
                   filenames via ``_infer_site``.
            max_workers: Maximum number of concurrent pdp3 subprocesses.
                         ``1`` means fully sequential execution.
            override: Re-run pdp3 even when valid output already exists.

        Returns:
            One ``ProcessingResult`` per input file, in the same order.
            Results for skipped (cached) files have ``returncode == 0``
            and ``config_path`` set to the shared date config.

        Raises:
            ValueError: If *sites* length does not match *rinex_files*.
        """
        if sites is None:
            sites = [_infer_site(Path(r)) for r in rinex_files]

        if len(sites) != len(rinex_files):
            raise ValueError(
                f"sites ({len(sites)}) must match rinex_files ({len(rinex_files)})"
            )

        # --- Step 1: Gather metadata for each RINEX file ------------------------
        # Build (rinex, site, date) tuples by reading each RINEX header.
        jobs: List[tuple[Path, str, datetime.date]] = []
        for rinex, site in zip(rinex_files, sites):
            rinex = Path(rinex)
            ts_start, _ = rinex_get_time_range(rinex)
            d = ts_start.date() if isinstance(ts_start, datetime.datetime) else ts_start
            jobs.append((rinex, site, d))

        # --- Step 2: Resolve products once per unique date ----------------------
        # Sorting + groupby ensures each date is visited exactly once.
        jobs_sorted = sorted(jobs, key=lambda j: j[2])
        resolutions: Dict[datetime.date, DependencyResolution] = {}
        for date_key, group in groupby(jobs_sorted, key=lambda j: j[2]):
            target_dt = datetime.datetime(
                date_key.year,
                date_key.month,
                date_key.day,
                tzinfo=datetime.timezone.utc,
            )
            logger.info("Resolving products for %s", date_key)
            resolutions[date_key] = self._resolve(target_dt)
            logger.info(resolutions[date_key].summary())

        # --- Step 3: Write per-date config files in year/doy dirs ---------------
        work_dirs: Dict[datetime.date, Path] = {}
        config_paths: Dict[datetime.date, Path] = {}
        for date_key, resolution in resolutions.items():
            sat_products, _ = _resolution_to_satellite_products(resolution)
            table_dir = _resolution_to_table_dir(resolution)
            work_dir = self._working_dir(date_key)
            work_dirs[date_key] = work_dir
            config_paths[date_key] = _write_config(
                sat_products,
                table_dir,
                work_dir / "config_file",
            )

        # --- Step 4: Build commands, skip cached results -------------------------
        pending: List[tuple[int, List[str], str, datetime.date]] = []
        results: List[Optional[ProcessingResult]] = [None] * len(jobs)

        for i, (rinex, site, d) in enumerate(jobs):
            kin_file, res_file = self._build_kin_res_paths(
                date=d,
                site=site,
                output_dir=self._output_dir,
            )
            if self._validate_kinfile(kin_file, override=override):
                logger.info(
                    "Valid output already exists for %s on %s, skipping", site, d
                )
                results[i] = ProcessingResult(
                    rinex_path=rinex,
                    site=site,
                    date=d,
                    kin_path=kin_file,
                    res_path=res_file if res_file and res_file.exists() else None,
                    config_path=config_paths[d],
                    resolution=resolutions[d],
                )
                continue

            command = self._build_pdp_command(
                rinex=rinex,
                site=site,
                config_path=config_paths[d],
            )
            pending.append((i, command, site, d))

        # --- Step 5: Dispatch pdp3 subprocesses ---------------------------------
        # Only the pdp3 calls are parallelised; resolution and config writing
        # above are always single-threaded to avoid race conditions.
        if max_workers <= 1:
            for idx, command, site, d in pending:
                kin_path, res_path, rc, stderr = self._run_pdp3(
                    command=command,
                    site=site,
                    output_dir=self._output_dir,
                )
                rinex, site, d = jobs[idx]
                results[idx] = ProcessingResult(
                    rinex_path=rinex,
                    site=site,
                    date=d,
                    kin_path=kin_path,
                    res_path=res_path,
                    config_path=config_paths[d],
                    resolution=resolutions[d],
                    returncode=rc,
                    stderr=stderr,
                )
        else:
            with ThreadPoolExecutor(max_workers=max_workers) as pool:
                future_to_idx = {
                    pool.submit(
                        self._run_pdp3,
                        command=cmd,
                        site=site,
                        output_dir=self._output_dir,
                    ): idx
                    for idx, cmd, site, d in pending
                }
                for future in as_completed(future_to_idx):
                    idx = future_to_idx[future]
                    kin_path, res_path, rc, stderr = future.result()
                    rinex, site, d = jobs[idx]
                    results[idx] = ProcessingResult(
                        rinex_path=rinex,
                        site=site,
                        date=d,
                        kin_path=kin_path,
                        res_path=res_path,
                        config_path=config_paths[d],
                        resolution=resolutions[d],
                        returncode=rc,
                        stderr=stderr,
                    )

        return [r for r in results if r is not None]
