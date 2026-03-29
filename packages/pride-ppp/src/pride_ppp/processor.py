"""PrideProcessor — concurrent-safe RINEX → kinematic position pipeline.

Owns all internal state (ProductEnvironment, WorkSpace, DependencySpec).
Each ``process()`` call runs pdp3 in an isolated temporary directory so
concurrent calls never collide on working directory or output paths.
"""

from __future__ import annotations

import datetime
import logging
import re
import shutil
import subprocess
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from itertools import groupby
from pathlib import Path
from typing import Dict, List, Optional, Sequence

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
    PRIDE_PPPAR_SPEC,
    PRIDE_PRODUCT_SPEC,
)
from .output import get_wrms_from_res, kin_to_kin_position_df
from .rinex import rinex_get_time_range

logger = logging.getLogger(__name__)

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
    """Immutable result from a single RINEX → kinematic processing run."""

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
        """Parse the .kin file into a DataFrame with WRMS residuals."""
        if not self.success or self.kin_path is None:
            return None
        return kin_to_kin_position_df(self.kin_path)

    def residuals(self) -> Optional[pd.DataFrame]:
        """Parse the .res file into a WRMS DataFrame."""
        if self.res_path is None or not self.res_path.exists():
            return None
        return get_wrms_from_res(self.res_path)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _infer_site(rinex: Path) -> str:
    m = _SITE_RE.match(rinex.stem)
    return m.group(1).upper() if m else "SIT1"


def _resolution_to_satellite_products(
    resolution: DependencyResolution,
) -> tuple[SatelliteProducts, Optional[Path]]:
    product_fields: Dict[str, str] = {}
    product_dir: Optional[Path] = None

    for rd in resolution.fulfilled:
        field_name = _SPEC_TO_PRODUCT_FIELD.get(rd.spec)
        if field_name is None or field_name in product_fields:
            continue
        path = rd.local_path
        if path is None:
            continue
        product_fields[field_name] = path.name
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

    Owns its own ProductEnvironment and WorkSpace. No global state.
    Thread-safe for concurrent ``process()`` calls.
    """

    def __init__(
        self,
        pride_dir: Path,
        output_dir: Path,
        *,
        pride_install_dir: Optional[Path] = None,
        cli_config: Optional[PrideCLIConfig] = None,
    ) -> None:
        self._pride_dir = Path(pride_dir)
        self._output_dir = Path(output_dir)
        self._pride_install_dir = (
            Path(pride_install_dir) if pride_install_dir else None
        )
        self._cli_config = cli_config if cli_config is not None else PrideCLIConfig()

        # Build private ProductEnvironment (immutable after .build())
        self._env = self._build_env()

        # Load DependencySpec from bundled YAML
        self._dep_spec = DependencySpec.from_yaml(PRIDE_PPPAR_SPEC)

        # Build private WorkSpace, registered once
        self._workspace = self._build_workspace()

        self._qf = QueryFactory(product_environment=self._env, workspace=self._workspace)
        self._fetcher = ResourceFetcher(max_connections=10)
    # ------------------------------------------------------------------ #
    # Private construction helpers
    # ------------------------------------------------------------------ #

    def _build_env(self) -> ProductEnvironment:
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
        station: Optional[str] = None,
    ) -> DependencyResolution:

        resolver = DependencyResolver(
            dep_spec=self._dep_spec,
            product_environment=self._env,
            query_factory=self._qf,
            fetcher=self._fetcher,
        )
        resolution, _ = resolver.resolve(
            date=date, local_sink_id=local_sink_id, station=station,
        )
        return resolution

    # ------------------------------------------------------------------ #
    # Subprocess execution
    # ------------------------------------------------------------------ #

    def _run_pdp3(
        self,
        rinex: Path,
        site: str,
        config_path: Path,
    ) -> tuple[Optional[Path], Optional[Path], int, str]:
        """Run pdp3 in an isolated temp dir. Returns (kin, res, returncode, stderr)."""
        if not shutil.which("pdp3") and self._cli_config.local_pdp3_path is None:
            raise FileNotFoundError("pdp3 binary not found in PATH")

        cli = PrideCLIConfig(
            **{
                **self._cli_config.model_dump(),
                "pride_configfile_path": config_path,
            }
        )
        command = cli.generate_pdp_command(site=site, local_file_path=str(rinex))

        tmpdir = Path(
            tempfile.mkdtemp(prefix="pride_", dir=str(self._pride_dir))
        )
        try:
            result = subprocess.run(
                command,
                cwd=str(tmpdir),
                capture_output=True,
                text=True,
            )

            if result.stdout:
                for line in result.stdout.strip().splitlines():
                    logger.info(line)
            if result.stderr:
                for line in result.stderr.strip().splitlines():
                    logger.warning(line)

            # Locate output files in the tmpdir tree
            kin_files = list(tmpdir.rglob(f"kin_*_{site.lower()}"))
            res_files = list(tmpdir.rglob(f"res_*_{site.lower()}"))

            kin_out: Optional[Path] = None
            res_out: Optional[Path] = None

            self._output_dir.mkdir(parents=True, exist_ok=True)

            if kin_files:
                src = kin_files[0]
                dst = self._output_dir / (src.name + ".kin")
                shutil.move(str(src), str(dst))
                kin_out = dst
                logger.info("Generated kin file %s", dst)

            if res_files:
                src = res_files[0]
                dst = self._output_dir / (src.name + ".res")
                shutil.move(str(src), str(dst))
                res_out = dst
                logger.info("Generated res file %s", dst)

            return kin_out, res_out, result.returncode, result.stderr

        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    def process(
        self,
        rinex: Path,
        *,
        site: Optional[str] = None,
        date: Optional[datetime.date] = None,
    ) -> ProcessingResult:
        """Process one RINEX file end-to-end.

        Resolves products, writes a PRIDE config, runs pdp3 in an isolated
        temp directory, and moves outputs to ``output_dir``.

        Args:
            rinex: Path to the RINEX observation file.
            site: 4-char site ID.  Inferred from filename if omitted.
            date: Override date (otherwise extracted from RINEX header).
        """
        rinex = Path(rinex)
        if not rinex.exists():
            raise FileNotFoundError(f"RINEX file not found: {rinex}")

        if site is None:
            site = _infer_site(rinex)

        # Determine date
        if date is None:
            ts_start, _ = rinex_get_time_range(rinex)
            start_date = ts_start.date() if isinstance(ts_start, datetime.datetime) else ts_start
        else:
            start_date = date if isinstance(date, datetime.date) else date.date()

        target_dt = datetime.datetime(
            start_date.year, start_date.month, start_date.day,
            tzinfo=datetime.timezone.utc,
        )

        # Check for existing output
        doy = start_date.timetuple().tm_yday
        kin_name = f"kin_{start_date.year}{doy:03d}_{site.lower()}.kin"
        existing_kin = self._output_dir / kin_name
        if existing_kin.exists():
            res_name = f"res_{start_date.year}{doy:03d}_{site.lower()}.res"
            existing_res = self._output_dir / res_name
            logger.info("Output already exists: %s", existing_kin)
            # Build a minimal resolution for the result
            resolution = self._resolve(target_dt, station=site)
            return ProcessingResult(
                rinex_path=rinex,
                site=site,
                date=start_date,
                kin_path=existing_kin,
                res_path=existing_res if existing_res.exists() else None,
                config_path=Path("(cached)"),
                resolution=resolution,
            )

        # Resolve products
        logger.info("Resolving products for %s (site=%s)", start_date, site)
        resolution = self._resolve(target_dt, station=site)
        logger.info(resolution.summary())

        if not resolution.all_required_fulfilled:
            missing = [r.spec for r in resolution.missing if r.required]
            logger.error("Missing required products: %s", missing)

        # Write config to a temp location
        sat_products, _ = _resolution_to_satellite_products(resolution)
        table_dir = _resolution_to_table_dir(resolution)
        config_dir = Path(
            tempfile.mkdtemp(prefix="pride_cfg_", dir=str(self._pride_dir))
        )
        try:
            config_path = _write_config(sat_products, table_dir, config_dir / "config_file")

            # Run pdp3
            kin_path, res_path, returncode, stderr = self._run_pdp3(
                rinex=rinex, site=site, config_path=config_path,
            )
        finally:
            shutil.rmtree(config_dir, ignore_errors=True)

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
    ) -> List[ProcessingResult]:
        """Process N RINEX files, grouping by date to share product resolution.

        Args:
            rinex_files: Paths to RINEX observation files.
            sites: Per-file site IDs. If None, inferred from filenames.
            max_workers: Parallel pdp3 subprocess limit. 1 = sequential.
        """
        if sites is None:
            sites = [_infer_site(Path(r)) for r in rinex_files]

        if len(sites) != len(rinex_files):
            raise ValueError(
                f"sites ({len(sites)}) must match rinex_files ({len(rinex_files)})"
            )

        # Gather (rinex, site, date) tuples
        jobs: List[tuple[Path, str, datetime.date]] = []
        for rinex, site in zip(rinex_files, sites):
            rinex = Path(rinex)
            ts_start, _ = rinex_get_time_range(rinex)
            d = ts_start.date() if isinstance(ts_start, datetime.datetime) else ts_start
            jobs.append((rinex, site, d))

        # Group by date to resolve products once per date
        jobs_sorted = sorted(jobs, key=lambda j: j[2])
        resolutions: Dict[datetime.date, DependencyResolution] = {}
        for date_key, group in groupby(jobs_sorted, key=lambda j: j[2]):
            target_dt = datetime.datetime(
                date_key.year, date_key.month, date_key.day,
                tzinfo=datetime.timezone.utc,
            )
            logger.info("Resolving products for %s", date_key)
            resolutions[date_key] = self._resolve(target_dt)
            logger.info(resolutions[date_key].summary())

        # Pre-build per-date config files in temp dirs
        config_dirs: Dict[datetime.date, Path] = {}
        config_paths: Dict[datetime.date, Path] = {}
        try:
            for date_key, resolution in resolutions.items():
                sat_products, _ = _resolution_to_satellite_products(resolution)
                table_dir = _resolution_to_table_dir(resolution)
                cfg_dir = Path(
                    tempfile.mkdtemp(prefix="pride_cfg_", dir=str(self._pride_dir))
                )
                config_dirs[date_key] = cfg_dir
                config_paths[date_key] = _write_config(
                    sat_products, table_dir, cfg_dir / "config_file",
                )

            # Run pdp3 for each job
            def _run_one(job: tuple[Path, str, datetime.date]) -> ProcessingResult:
                rinex, site, d = job
                resolution = resolutions[d]
                config_path = config_paths[d]

                # Check for existing output
                doy = d.timetuple().tm_yday
                kin_name = f"kin_{d.year}{doy:03d}_{site.lower()}.kin"
                existing_kin = self._output_dir / kin_name
                if existing_kin.exists():
                    res_name = f"res_{d.year}{doy:03d}_{site.lower()}.res"
                    existing_res = self._output_dir / res_name
                    return ProcessingResult(
                        rinex_path=rinex,
                        site=site,
                        date=d,
                        kin_path=existing_kin,
                        res_path=existing_res if existing_res.exists() else None,
                        config_path=config_path,
                        resolution=resolution,
                    )

                kin_path, res_path, rc, stderr = self._run_pdp3(
                    rinex=rinex, site=site, config_path=config_path,
                )
                return ProcessingResult(
                    rinex_path=rinex,
                    site=site,
                    date=d,
                    kin_path=kin_path,
                    res_path=res_path,
                    config_path=config_path,
                    resolution=resolution,
                    returncode=rc,
                    stderr=stderr,
                )

            results: List[ProcessingResult] = []
            if max_workers <= 1:
                results = [_run_one(job) for job in jobs]
            else:
                with ThreadPoolExecutor(max_workers=max_workers) as pool:
                    future_to_job = {pool.submit(_run_one, job): job for job in jobs}
                    for future in as_completed(future_to_job):
                        results.append(future.result())
                # Preserve original order
                job_order = {id(job): i for i, job in enumerate(jobs)}
                results.sort(
                    key=lambda r: next(
                        job_order[id(j)]
                        for j in jobs
                        if j[0] == r.rinex_path and j[1] == r.site
                    )
                )
        finally:
            for cfg_dir in config_dirs.values():
                shutil.rmtree(cfg_dir, ignore_errors=True)

        return results
