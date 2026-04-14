"""User configuration for gnss-ppp-etl.

Config files use TOML format.  Resolution order (highest priority last):

  1. Compiled defaults
  2. User config  (~/.config/gnss-ppp-etl/config.toml)
  3. Project config (gnss-ppp-etl.toml in *project_dir*)
  4. Environment variables  (GNSS_*)

Usage::

    from gnss_ppp_etl_cli.config import ConfigLoader, ENV_VAR, USER_CONFIG_PATH

    cfg = ConfigLoader.load()
    client = GNSSClient.from_defaults(**cfg.to_client_kwargs())
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

try:
    import tomllib
except ModuleNotFoundError:
    try:
        import tomli as tomllib  # type: ignore[no-redef]
    except ModuleNotFoundError:
        tomllib = None  # type: ignore[assignment]

# ── Public constants ──────────────────────────────────────────────────────────

ENV_VAR = "GNSS_CONFIG"

_USER_CONFIG_PATH: Path = Path.home() / ".config" / "gnss-ppp-etl" / "config.toml"
USER_CONFIG_PATH: Path = _USER_CONFIG_PATH


# ── Sub-section view helpers ──────────────────────────────────────────────────


class _ClientView:
    """Read-only view of client-related config fields."""

    __slots__ = ("_cfg",)

    def __init__(self, cfg: UserConfig) -> None:
        self._cfg = cfg

    @property
    def base_dir(self) -> Path | None:
        return self._cfg.base_dir

    @property
    def centers(self) -> list[str]:
        return self._cfg.centers

    @property
    def max_connections(self) -> int:
        return self._cfg.max_connections


# ── Main config class ─────────────────────────────────────────────────────────


class UserConfig:
    """Resolved configuration for gnss-ppp-etl."""

    def __init__(
        self,
        base_dir: str | Path | None = None,
        centers: list[str] | None = None,
        max_connections: int = 4,
        log_level: str = "WARNING",
    ) -> None:
        self.base_dir: Path | None = Path(base_dir).expanduser() if base_dir else None
        self.centers: list[str] = list(centers) if centers else []
        self.max_connections: int = int(max_connections)
        self.log_level: str = log_level
        self._sources: dict[str, str] = {}

    @property
    def client(self) -> _ClientView:
        return _ClientView(self)

    # ── kwarg factories ───────────────────────────────────────────────────────

    def to_client_kwargs(self) -> dict[str, Any]:
        """Return kwargs for ``GNSSClient.from_defaults()``."""
        kwargs: dict[str, Any] = {"max_connections": self.max_connections}
        if self.base_dir is not None:
            kwargs["base_dir"] = self.base_dir
        return kwargs

    # ── Class-method constructors ─────────────────────────────────────────────

    @classmethod
    def defaults(cls) -> UserConfig:
        """Return a config object populated entirely from compiled defaults."""
        return cls()

    @classmethod
    def load(cls, project_dir: Path | None = None) -> UserConfig:
        """Load and resolve configuration from all sources.

        Args:
            project_dir: Directory to search for ``gnss-ppp-etl.toml``.

        Returns:
            Resolved :class:`UserConfig`.
        """
        cfg = cls()

        # 1. User config file
        user_path = _USER_CONFIG_PATH
        if user_path.exists():
            data = _read_toml(user_path)
            _apply_flat(cfg, data, source="user")

        # 2. Project config
        if project_dir is not None:
            project_file = Path(project_dir) / "gnss-ppp-etl.toml"
            if project_file.exists():
                data = _read_toml(project_file)
                _apply_flat(cfg, data, source="project")

        # 3. Environment variables
        _apply_env(cfg)

        return cfg

    # ── Persistence ───────────────────────────────────────────────────────────

    def save(self) -> None:
        """Persist current settings to the user config file."""
        data: dict[str, Any] = {}
        if self.log_level != "WARNING":
            data["log_level"] = self.log_level
        if self.base_dir is not None:
            data["base_dir"] = str(self.base_dir)
        if self.centers:
            data["centers"] = self.centers
        if self.max_connections != 4:
            data["max_connections"] = self.max_connections
        _write_toml(_USER_CONFIG_PATH, data)

    def set(self, key: str, value: Any) -> None:
        """Set a single key and persist to the user config file."""
        _SETTABLE = {"base_dir", "centers", "max_connections", "log_level"}
        if key not in _SETTABLE:
            raise KeyError(f"Unknown config key: {key!r}")

        if key == "centers":
            if isinstance(value, str):
                value = [c.strip() for c in value.split(",") if c.strip()]
            else:
                value = list(value)
        elif key == "max_connections":
            value = int(value)
        elif key == "base_dir":
            value = Path(value).expanduser() if value else None

        setattr(self, key, value)
        self.save()

    def reset(self) -> None:
        """Remove the user config file, reverting to defaults on next load."""
        if _USER_CONFIG_PATH.exists():
            _USER_CONFIG_PATH.unlink()

    # ── Class-level file operations (used by CLI subcommands) ─────────────────

    @classmethod
    def update_user_config(cls, updates: dict[str, Any]) -> None:
        """Deep-merge *updates* into the user config file."""
        data: dict[str, Any] = {}
        if _USER_CONFIG_PATH.exists():
            data = _read_toml(_USER_CONFIG_PATH)
        _deep_merge(data, updates)
        _write_toml(_USER_CONFIG_PATH, data)

    @classmethod
    def reset_user_config(cls) -> None:
        """Remove the user config file."""
        if _USER_CONFIG_PATH.exists():
            _USER_CONFIG_PATH.unlink()


# ConfigLoader is the public alias used by CLI commands.
ConfigLoader = UserConfig


# ── Internal helpers ──────────────────────────────────────────────────────────


def _read_toml(path: Path) -> dict[str, Any]:
    """Read a TOML file and return its contents as a dict."""
    if tomllib is None:
        raise RuntimeError(
            "No TOML reader available. Install 'tomli' for Python < 3.11, "
            "or upgrade to Python 3.11+."
        )
    with open(path, "rb") as fh:
        return tomllib.load(fh)


def _write_toml(path: Path, data: dict[str, Any]) -> None:
    """Write *data* to *path* in TOML format (flat keys only)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []
    for key, value in data.items():
        if isinstance(value, bool):
            lines.append(f"{key} = {str(value).lower()}")
        elif isinstance(value, (int, float)):
            lines.append(f"{key} = {value}")
        elif isinstance(value, str):
            escaped = value.replace("\\", "\\\\").replace('"', '\\"')
            lines.append(f'{key} = "{escaped}"')
        elif isinstance(value, list):
            items = ", ".join(f'"{v}"' for v in value)
            lines.append(f"{key} = [{items}]")
        elif isinstance(value, dict):
            lines.append(f"\n[{key}]")
            for k, v in value.items():
                if isinstance(v, bool):
                    lines.append(f"{k} = {str(v).lower()}")
                elif isinstance(v, (int, float)):
                    lines.append(f"{k} = {v}")
                elif isinstance(v, str):
                    escaped = v.replace("\\", "\\\\").replace('"', '\\"')
                    lines.append(f'{k} = "{escaped}"')
                elif isinstance(v, list):
                    items = ", ".join(f'"{i}"' for i in v)
                    lines.append(f"{k} = [{items}]")
    path.write_text("\n".join(lines) + "\n" if lines else "")


def _apply_flat(cfg: UserConfig, data: dict[str, Any], source: str) -> None:
    """Apply a flat or nested TOML dict to *cfg*, recording the source."""
    client = data.get("client", {})

    def _set(attr: str, val: Any, src_key: str) -> None:
        setattr(cfg, attr, val)
        cfg._sources[src_key] = source

    if "log_level" in data:
        _set("log_level", data["log_level"], "log_level")

    # base_dir
    raw = data.get("base_dir") or client.get("base_dir")
    if raw is not None:
        _set("base_dir", Path(raw).expanduser(), "base_dir")

    # centers
    raw = data.get("centers") or client.get("centers")
    if raw is not None:
        if isinstance(raw, str):
            raw = [c.strip() for c in raw.split(",") if c.strip()]
        _set("centers", list(raw), "centers")

    # max_connections
    raw = (
        data.get("max_connections") if "max_connections" in data else client.get("max_connections")
    )
    if raw is not None:
        _set("max_connections", int(raw), "max_connections")


def _apply_env(cfg: UserConfig) -> None:
    """Apply GNSS_* environment variables to *cfg*."""
    if val := os.environ.get("GNSS_BASE_DIR"):
        cfg.base_dir = Path(val).expanduser()
        cfg._sources["base_dir"] = "env"
    if val := os.environ.get("GNSS_CENTERS"):
        cfg.centers = [c.strip() for c in val.split(",") if c.strip()]
        cfg._sources["centers"] = "env"
    if val := os.environ.get("GNSS_MAX_CONNECTIONS"):
        try:
            cfg.max_connections = int(val)
            cfg._sources["max_connections"] = "env"
        except ValueError:
            pass
    if val := os.environ.get("GNSS_LOG_LEVEL"):
        cfg.log_level = val
        cfg._sources["log_level"] = "env"


def _deep_merge(base: dict[str, Any], updates: dict[str, Any]) -> None:
    """Recursively merge *updates* into *base* in place."""
    for k, v in updates.items():
        if isinstance(v, dict) and isinstance(base.get(k), dict):
            _deep_merge(base[k], v)
        else:
            base[k] = v
