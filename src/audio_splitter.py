import logging
import subprocess
import wave
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class AudioChunk:
    """One temporary audio file and its position in the source WAV."""

    path: Path
    start_time: float
    end_time: float


class AudioSplitter:


    def __init__(
        self,
        chunk_seconds=300,
        overlap_seconds=2,
        temp_dir="temp/chunks",
        ffmpeg_path="ffmpeg"
    ):

        self.logger = logging.getLogger(
            "video2srt"
        )
        self.chunk_seconds = float(chunk_seconds)
        self.overlap_seconds = float(overlap_seconds)
        self.ffmpeg = str(ffmpeg_path)
        self.output_dir = Path(temp_dir)

        self._validate_settings()


    def _validate_settings(self):
        if self.chunk_seconds <= 0:
            raise ValueError("chunk.seconds must be greater than 0")

        if self.overlap_seconds < 0:
            raise ValueError("chunk.overlap_seconds must be greater than or equal to 0")

        if self.overlap_seconds >= self.chunk_seconds:
            raise ValueError("chunk.overlap_seconds must be smaller than chunk.seconds")


    def split(
        self,
        wav_file,
        output_dir=None
    ):
        """Split a WAV into overlapping chunks with their real source offsets."""

        wav_file = Path(wav_file)
        duration = self._get_wav_duration(wav_file)
        specs = self._build_chunk_specs(duration)
        run_dir = Path(output_dir) if output_dir else self.output_dir / wav_file.stem

        run_dir.mkdir(parents=True, exist_ok=True)
        for old_chunk in run_dir.glob("*.wav"):
            old_chunk.unlink()

        self.logger.info(
            "Splitting audio into %d chunks (%.2fs with %.2fs overlap)",
            len(specs),
            self.chunk_seconds,
            self.overlap_seconds,
        )

        chunks = []
        for index, (start_time, end_time) in enumerate(specs):
            output = run_dir / f"{wav_file.stem}_{index:03d}.wav"
            self._extract_chunk(wav_file, output, start_time, end_time - start_time)
            chunks.append(AudioChunk(output, start_time, end_time))

        return chunks


    @staticmethod
    def _get_wav_duration(wav_file):
        try:
            with wave.open(str(wav_file), "rb") as audio:
                if audio.getframerate() <= 0:
                    raise RuntimeError("WAV file has an invalid sample rate")
                return audio.getnframes() / audio.getframerate()
        except wave.Error as error:
            raise RuntimeError(f"Could not read WAV duration: {wav_file}") from error


    def _build_chunk_specs(self, duration):
        if duration <= 0:
            raise RuntimeError("Input WAV is empty")

        step = self.chunk_seconds - self.overlap_seconds
        specs = []
        start_time = 0.0

        while start_time < duration:
            end_time = min(start_time + self.chunk_seconds, duration)
            specs.append((start_time, end_time))
            start_time += step

        return specs


    def _extract_chunk(
        self,
        wav_file,
        output_file,
        start_time,
        duration
    ):
        cmd = [
            self.ffmpeg,
            "-y",
            "-ss",
            f"{start_time:.6f}",
            "-t",
            f"{duration:.6f}",
            "-i",
            str(wav_file),
            "-ac",
            "1",
            "-ar",
            "16000",
            "-c:a",
            "pcm_s16le",
            str(output_file),
        ]

        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        if result.returncode != 0:
            raise RuntimeError(
                f"ffmpeg failed to create chunk at {start_time:.2f}s:\n{result.stderr}"
            )

        if not output_file.exists():
            raise RuntimeError(f"ffmpeg did not create chunk: {output_file}")
