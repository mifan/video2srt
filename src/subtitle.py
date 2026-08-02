import logging
import math
import tempfile
from pathlib import Path


class SRTWriter:

    def __init__(self):
        self.logger = logging.getLogger("video2srt")

    def format_time(self, seconds):
        """Convert seconds to an SRT timestamp."""
        milliseconds = int(round(seconds * 1000))
        hours, milliseconds = divmod(milliseconds, 3600000)
        minutes, milliseconds = divmod(milliseconds, 60000)
        secs, milliseconds = divmod(milliseconds, 1000)
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{milliseconds:03d}"

    @staticmethod
    def clean_text(text):
        if text is None:
            return ""
        return str(text).replace("\n", " ").strip()

    def validate_segments(self, segments):
        """Normalize, sort, and validate subtitle cues before writing SRT."""
        normalized = []

        for source_index, segment in enumerate(segments, start=1):
            text = self.clean_text(segment.get("text", ""))
            if not text:
                continue

            try:
                start = float(segment["start"])
                end = float(segment["end"])
            except (KeyError, TypeError, ValueError) as error:
                raise ValueError(
                    f"Subtitle cue {source_index} has invalid start/end values"
                ) from error

            if not math.isfinite(start) or not math.isfinite(end):
                raise ValueError(
                    f"Subtitle cue {source_index} has non-finite timestamps"
                )

            start_ms = round(start * 1000)
            end_ms = round(end * 1000)
            if start_ms < 0:
                raise ValueError(
                    f"Subtitle cue {source_index} starts before zero"
                )
            if end_ms <= start_ms:
                raise ValueError(
                    f"Subtitle cue {source_index} must end after it starts"
                )

            normalized.append({
                "start_ms": start_ms,
                "end_ms": end_ms,
                "text": text,
            })

        normalized.sort(key=lambda cue: (cue["start_ms"], cue["end_ms"]))

        validated = []
        for cue in normalized:
            if validated and cue["start_ms"] < validated[-1]["end_ms"]:
                original_start = cue["start_ms"]
                cue["start_ms"] = validated[-1]["end_ms"]
                self.logger.warning(
                    "Trimmed overlapping subtitle from %s to %s ms",
                    original_start,
                    cue["start_ms"],
                )

            if cue["end_ms"] <= cue["start_ms"]:
                self.logger.warning(
                    "Skipped subtitle fully covered by a previous cue: %s",
                    cue["text"],
                )
                continue

            validated.append(cue)

        if not validated:
            raise ValueError("No valid subtitle cues to write")

        return validated

    def write(self, segments, output_file, overwrite=False):
        """Validate cues and atomically write an SRT file."""
        output_file = Path(output_file)
        output_file.parent.mkdir(parents=True, exist_ok=True)

        if output_file.exists() and not overwrite:
            raise FileExistsError(
                f"Subtitle already exists: {output_file}. Use --overwrite to replace it."
            )

        validated = self.validate_segments(segments)
        lines = []

        for index, cue in enumerate(validated, start=1):
            lines.extend((
                str(index),
                f"{self.format_time(cue['start_ms'] / 1000)} --> "
                f"{self.format_time(cue['end_ms'] / 1000)}",
                cue["text"],
                "",
            ))

        self.logger.info("Writing %d SRT cues: %s", len(validated), output_file)
        temp_path = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                newline="\n",
                suffix=".srt.tmp",
                dir=output_file.parent,
                delete=False,
            ) as temporary_file:
                temporary_file.write("\n".join(lines))
                temp_path = Path(temporary_file.name)

            temp_path.replace(output_file)
        finally:
            if temp_path and temp_path.exists():
                temp_path.unlink()

        self.logger.info("SRT generated: %s", output_file)
        return output_file
