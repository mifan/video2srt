from copy import deepcopy
from pathlib import Path

import yaml


DEFAULT_CONFIG = {
    "ffmpeg": {
        "path": "ffmpeg",
    },
    "device": "auto",
    "subtitle": {
        "format": "srt",
        "max_chars": 24,
        "max_duration_seconds": 6.0,
        "max_cps": 15,
    },
    "language": "auto",
    "output": {
        "directory": None,
        "overwrite": False,
    },
    "chunk": {
        "seconds": 300,
        "overlap_seconds": 2,
    },
}


class Config:

    def __init__(self, filename):

        path = Path(filename)

        if not path.exists():
            raise FileNotFoundError(
                f"Config not found: {filename}"
            )

        with open(
            path,
            "r",
            encoding="utf-8"
        ) as f:

            loaded = yaml.safe_load(f) or {}

        if not isinstance(loaded, dict):
            raise ValueError(
                "Config root must be a mapping"
            )

        self.path = path
        self.data = self._normalize(loaded)


    def _normalize(self, loaded):
        """Convert legacy keys to the schema consumed by Pipeline."""

        data = self._merge(DEFAULT_CONFIG, loaded)

        # Backward compatibility for the original config/config.yaml.
        legacy_models = loaded.get("model", {})
        if "models" not in loaded and isinstance(legacy_models, dict):
            data["models"] = deepcopy(legacy_models)

        ffmpeg_config = loaded.get("ffmpeg", {})
        if (
            isinstance(ffmpeg_config, dict)
            and "path" not in ffmpeg_config
            and "exe" in ffmpeg_config
        ):
            data["ffmpeg"]["path"] = ffmpeg_config["exe"]

        return data


    @staticmethod
    def _merge(defaults, overrides):
        """Recursively merge user values onto a copy of the defaults."""

        result = deepcopy(defaults)

        for key, value in overrides.items():
            if (
                isinstance(value, dict)
                and isinstance(result.get(key), dict)
            ):
                result[key] = Config._merge(result[key], value)
            else:
                result[key] = deepcopy(value)

        return result


    def get(self, *keys):

        value = self.data

        for key in keys:
            value = value[key]

        return value
