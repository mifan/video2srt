from copy import deepcopy
from pathlib import Path
import shutil

import yaml

from src.languages import normalize_forced_alignment_language


DEFAULT_CONFIG = {
    "ffmpeg": {"path": "ffmpeg"},
    "device": "auto",
    "language": "auto",
    "alignment": {
        "min_match_ratio": 0.85,
        "low_match_policy": "error",
    },
    "subtitle": {
        "format": "srt",
        "max_chars": 24,
        "max_duration_seconds": 6.0,
        "max_cps": 15,
    },
    "output": {"directory": None, "overwrite": False},
    "workspace": {"temp_dir": "temp", "keep_temp": False},
    "chunk": {"seconds": 300, "overlap_seconds": 2},
}


class Config:

    def __init__(self, filename):
        path = Path(filename)
        if not path.exists():
            raise FileNotFoundError(f"Config not found: {filename}")

        with path.open("r", encoding="utf-8") as file:
            loaded = yaml.safe_load(file) or {}

        if not isinstance(loaded, dict):
            raise ValueError("Config root must be a mapping")

        self.path = path
        self.data = self._normalize(loaded)
        self.validate()

    def _normalize(self, loaded):
        data = self._merge(DEFAULT_CONFIG, loaded)

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

    def validate(self):
        self._validate_model_paths()
        self._validate_ffmpeg()
        self._validate_chunk()
        self._validate_subtitle()
        self._validate_language()
        self._validate_alignment()
        self._validate_output_and_workspace()

    def _validate_model_paths(self):
        models = self.data.get("models")
        if not isinstance(models, dict):
            raise ValueError("models.asr and models.aligner must be configured")

        for name in ("asr", "aligner"):
            path = models.get(name)
            if not isinstance(path, str) or not path.strip():
                raise ValueError(f"models.{name} must be a non-empty local path")
            if not Path(path).is_dir():
                raise FileNotFoundError(f"Model directory not found: models.{name}={path}")

    def _validate_ffmpeg(self):
        ffmpeg_path = self.get("ffmpeg", "path")
        if not isinstance(ffmpeg_path, str) or not ffmpeg_path.strip():
            raise ValueError("ffmpeg.path must be a non-empty path or command")
        if not Path(ffmpeg_path).exists() and not shutil.which(ffmpeg_path):
            raise FileNotFoundError(f"FFmpeg not found: {ffmpeg_path}")

    def _validate_chunk(self):
        seconds = self._positive_number("chunk.seconds")
        overlap = self._non_negative_number("chunk.overlap_seconds")
        if overlap >= seconds:
            raise ValueError("chunk.overlap_seconds must be smaller than chunk.seconds")

    def _validate_subtitle(self):
        self._positive_number("subtitle.max_chars")
        self._positive_number("subtitle.max_duration_seconds")
        self._positive_number("subtitle.max_cps")

    def _validate_language(self):
        language = self.get("language")
        if not isinstance(language, str) or not language.strip():
            raise ValueError("language must be 'auto' or a supported language name")
        if language.casefold() == "auto":
            return

        normalized = normalize_forced_alignment_language(language)
        if not normalized:
            raise ValueError(f"Unsupported ForcedAligner language: {language}")
        self.data["language"] = normalized

    def _validate_alignment(self):
        ratio = self._positive_number("alignment.min_match_ratio")
        if ratio > 1:
            raise ValueError("alignment.min_match_ratio must be between 0 and 1")

        policy = self.get("alignment", "low_match_policy")
        if policy not in {"error", "skip", "fallback"}:
            raise ValueError(
                "alignment.low_match_policy must be error, skip, or fallback"
            )

    def _validate_output_and_workspace(self):
        for section, key in (("output", "overwrite"), ("workspace", "keep_temp")):
            if not isinstance(self.get(section, key), bool):
                raise ValueError(f"{section}.{key} must be true or false")

        for section, key in (("output", "directory"), ("workspace", "temp_dir")):
            value = self.get(section, key)
            if value is not None and (not isinstance(value, str) or not value.strip()):
                raise ValueError(f"{section}.{key} must be null or a non-empty path")

    def _positive_number(self, dotted_key):
        value = self._number(dotted_key)
        if value <= 0:
            raise ValueError(f"{dotted_key} must be greater than 0")
        return value

    def _non_negative_number(self, dotted_key):
        value = self._number(dotted_key)
        if value < 0:
            raise ValueError(f"{dotted_key} must be greater than or equal to 0")
        return value

    def _number(self, dotted_key):
        value = self.get(*dotted_key.split("."))
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f"{dotted_key} must be a number")
        return float(value)

    @staticmethod
    def _merge(defaults, overrides):
        result = deepcopy(defaults)
        for key, value in overrides.items():
            if isinstance(value, dict) and isinstance(result.get(key), dict):
                result[key] = Config._merge(result[key], value)
            else:
                result[key] = deepcopy(value)
        return result

    def get(self, *keys):
        value = self.data
        for key in keys:
            value = value[key]
        return value
