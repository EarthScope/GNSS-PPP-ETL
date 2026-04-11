"""ConfigLoader — resolves the full configuration chain for gnss-ppp-etl.

Resolution order (lowest → highest priority)
---------------------------------------------
1. Pydantic-compiled defaults (in :class:`.AppConfig`).
2. User-level config:    ``~/.config/gnss-ppp-etl/config.yaml``
3. Project-level config: ``gnss-ppp-etl.yaml``  (walks up from cwd)
4. Override file:        ``$GNSS_CONFIG``  (single env-var → explicit path)

All three YAML files share the same schema.  Later sources are **deep-merged**
into earlier ones (nested ``client:`` / ``processor:`` sections are merged
key-by-key, not replaced wholesale).

Environment variable
--------------------
``GNSS_CONFIG=/path/to/my-site.yaml``
    Points to any YAML file that follows the :class:`.AppConfig` schema.
    Values in that file override both the user and project configs.

Usage
-----
.. code-block:: python

    from gnss_ppp_etl.config import ConfigLoader, AppConfig

    cfg: AppConfig = ConfigLoader.load()
    client = GNSSClient.from_defaults(**cfg.to_client_kwargs())
"""

from __future__ import annotations

import copy
import os
from pathlib import Path
from typing import Any

import yaml

from gnss_ppp_etl.config.models import AppConfig

# ── well-known paths ──────────────────────────────────────────────────────────

USER_CONFIG_PATH = Path.home() / ".config" / "gnss-ppp-etl" / "config.yaml"
PROJECT_CONFIG_NAME = "gnss-ppp-etl.yaml"
ENV_VAR = "GNSS_CONFIG"
_MAX_WALK = 20  # max ancestor directories to check for project config


# ── internal helpers ──────────────────────────────────────────────────────────


def _load_yaml(path: Path) -> dict[str, Any]:
    """Return a dict from a YAML file, or ``{}`` if the file is missing/empty."""
    try:
        with path.open() as fh:
            data = yaml.safe_load(fh)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """Return a new dict that deep-merges *override* into *base*.

    Nested dicts are merged recursively; all other values are replaced.
    """
    result = copy.deepcopy(base)
    for key, val in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(val, dict):
            result[key] = _deep_merge(result[key], val)
        else:
            result[key] = copy.deepcopy(val)
    return result


def _find_project_config(start: Path | None = None) -> Path | None:
    """Walk up from *start* (default: cwd) until ``gnss-ppp-etl.yaml`` is found."""
    here = (start or Path.cwd()).resolve()
    home = Path.home().resolve()
    for _ in range(_MAX_WALK):
        candidate = here / PROJECT_CONFIG_NAME
        if candidate.exists():
            return candidate
        if here == home or here.parent == here:
            break
        here = here.parent
    return None


# ── ConfigLoader ──────────────────────────────────────────────────────────────


class ConfigLoader:
    """Resolve and load the full :class:`.AppConfig` from the priority chain.

    All methods are class-methods; there is no instance state.  This makes
    it easy to call ``ConfigLoader.load()`` from any CLI command without
    threading a context object through the call stack.

    Example
    -------
    .. code-block:: python

        cfg = ConfigLoader.load()
        cfg.client.centers        # e.g. ['COD', 'ESA']
        cfg.processor.cli.system  # e.g. 'GREC23J'
    """

    #: Path to the user-level config file (``~/.config/…``).
    user_config_path: Path = USER_CONFIG_PATH

    @classmethod
    def load(cls, project_dir: Path | None = None) -> AppConfig:
        """Load and merge all config sources, returning a validated :class:`AppConfig`.

        Parameters
        ----------
        project_dir:
            Override the start directory for project-config discovery.
            Defaults to ``cwd``.

        Returns
        -------
        AppConfig
            Fully validated configuration instance.  The private
            ``._sources`` dict records which YAML file each top-level
            section came from.
        """
        merged: dict[str, Any] = {}
        sources: dict[str, str] = {}

        # 1. User-level config
        if USER_CONFIG_PATH.exists():
            user_data = _load_yaml(USER_CONFIG_PATH)
            merged = _deep_merge(merged, user_data)
            for k in user_data:
                sources[k] = "user"

        # 2. Project-level config
        proj_path = _find_project_config(project_dir)
        if proj_path is not None:
            proj_data = _load_yaml(proj_path)
            merged = _deep_merge(merged, proj_data)
            for k in proj_data:
                sources[k] = f"project ({proj_path.name})"

        # 3. Override file via $GNSS_CONFIG
        if env_path_str := os.environ.get(ENV_VAR):
            env_path = Path(env_path_str).expanduser()
            if env_path.exists():
                env_data = _load_yaml(env_path)
                merged = _deep_merge(merged, env_data)
                for k in env_data:
                    sources[k] = f"$GNSS_CONFIG ({env_path.name})"

        cfg = AppConfig.model_validate(merged)
        cfg._sources = sources
        return cfg

    @classmethod
    def update_user_config(cls, updates: dict[str, Any]) -> None:
        """Deep-merge *updates* into the user config file and save.

        Parameters
        ----------
        updates:
            Partial config dict following the :class:`AppConfig` schema.
            Only the supplied keys are changed; everything else is
            preserved.
        """
        existing = _load_yaml(USER_CONFIG_PATH) if USER_CONFIG_PATH.exists() else {}
        merged = _deep_merge(existing, updates)
        # Validate the merged result before writing (catches bad values early)
        AppConfig.model_validate(merged)
        USER_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        USER_CONFIG_PATH.write_text(
            "# gnss-ppp-etl configuration — managed by `gnss config`\n"
            + yaml.dump(merged, default_flow_style=False, sort_keys=False, allow_unicode=True)
        )

    @classmethod
    def reset_user_config(cls) -> None:
        """Delete the user config file, reverting all settings to defaults."""
        if USER_CONFIG_PATH.exists():
            USER_CONFIG_PATH.unlink()
