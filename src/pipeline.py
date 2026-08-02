import logging
import shutil
import uuid
from pathlib import Path

from src.aligner import Qwen3Aligner
from src.audio_splitter import AudioSplitter
from src.ffmpeg_util import FFmpegExtractor
from src.languages import normalize_forced_alignment_language
from src.qwen3_asr import Qwen3Recognizer
from src.segmenter import SubtitleSegmenter
from src.subtitle import SRTWriter


class Pipeline:
    def __init__(self, config):
        self.logger = logging.getLogger("video2srt")
        self.config = config
        self.language = config.get("language")
        self.extractor = FFmpegExtractor(config.get("ffmpeg", "path"))
        self.splitter = AudioSplitter(
            chunk_seconds=config.get("chunk", "seconds"),
            overlap_seconds=config.get("chunk", "overlap_seconds"),
            ffmpeg_path=config.get("ffmpeg", "path"),
        )
        self.asr = Qwen3Recognizer(
            model_path=config.get("models", "asr"),
            device=config.get("device"),
        )
        self.aligner = Qwen3Aligner(
            model_path=config.get("models", "aligner"),
            device=config.get("device"),
        )
        self.segmenter = SubtitleSegmenter(
            max_chars=config.get("subtitle", "max_chars"),
            max_duration=config.get("subtitle", "max_duration_seconds"),
            max_cps=config.get("subtitle", "max_cps"),
            min_match_ratio=config.get("alignment", "min_match_ratio"),
            low_match_policy=config.get("alignment", "low_match_policy"),
        )
        self.writer = SRTWriter()

    def run(self, video_file, output_file=None, overwrite=None):
        video_file = Path(video_file)
        work_dir = self._create_work_dir(video_file)

        try:
            self.logger.info("Processing: %s", video_file)
            wav_file = self.extractor.extract(
                video_file,
                work_dir / f"{video_file.stem}.wav",
            )
            chunks = self.splitter.split(wav_file, work_dir / "chunks")
            transcripts = self._transcribe_chunks(chunks)
            segments = self._align_transcripts(transcripts)
            output_file, overwrite = self._resolve_output(
                video_file, output_file, overwrite
            )
            self.writer.write(
                self._deduplicate_overlap_segments(segments),
                output_file,
                overwrite=overwrite,
            )
            self.logger.info("Finished: %s", output_file)
            return output_file
        finally:
            self._cleanup_work_dir(work_dir)

    def _transcribe_chunks(self, chunks):
        transcripts = []
        try:
            for index, chunk in enumerate(chunks, start=1):
                self.logger.info("ASR chunk %d/%d: %s", index, len(chunks), chunk.path)
                result = self.asr.transcribe(chunk.path, self.language)
                text = self.extract_text(result)
                if not text.strip():
                    self.logger.warning("Empty ASR result, skipping chunk %d", index)
                    continue
                transcripts.append((chunk, text, self.resolve_language(result, text)))
        finally:
            self.asr.release()
        return transcripts

    def _align_transcripts(self, transcripts):
        segments = []
        try:
            for chunk, text, language in transcripts:
                align_result = self.aligner.align(chunk.path, text, language)
                for segment in self.segmenter.segment(align_result, text):
                    segment["start"] += chunk.start_time
                    segment["end"] += chunk.start_time
                    segments.append(segment)
        finally:
            self.aligner.release()
        return segments

    def _create_work_dir(self, video_file):
        temp_root = Path(self.config.get("workspace", "temp_dir"))
        work_dir = temp_root / f"{video_file.stem}-{uuid.uuid4().hex}"
        work_dir.mkdir(parents=True, exist_ok=False)
        self.logger.info("Working directory: %s", work_dir)
        return work_dir

    def _cleanup_work_dir(self, work_dir):
        if self.config.get("workspace", "keep_temp"):
            self.logger.info("Keeping working directory: %s", work_dir)
            return
        shutil.rmtree(work_dir, ignore_errors=True)

    def _resolve_output(self, video_file, output_file, overwrite):
        if output_file is None:
            directory = self.config.get("output", "directory")
            output_file = Path(directory) if directory else video_file.parent
            output_file = output_file / f"{video_file.stem}.srt"
        else:
            output_file = Path(output_file)

        if overwrite is None:
            overwrite = self.config.get("output", "overwrite")
        return output_file, overwrite

    @staticmethod
    def extract_text(result):
        if isinstance(result, str):
            return result
        candidates = result if isinstance(result, list) else [result]
        return "".join(
            item.get("text", "") if isinstance(item, dict) else getattr(item, "text", "")
            for item in candidates
        )

    def resolve_language(self, asr_result, text):
        if self.language.casefold() != "auto":
            return self.language

        detected = self.extract_result_language(asr_result)
        if detected:
            normalized = normalize_forced_alignment_language(detected)
            if not normalized:
                raise ValueError(
                    "ASR detected a language unsupported by Qwen3-ForcedAligner: "
                    f"{detected}"
                )
            self.logger.info("ASR detected language: %s", normalized)
            return normalized

        fallback = self.detect_language(text)
        self.logger.warning("ASR language unavailable; using heuristic: %s", fallback)
        return fallback

    @staticmethod
    def extract_result_language(result):
        candidates = result if isinstance(result, list) else [result]
        for item in candidates:
            language = item.get("language") if isinstance(item, dict) else getattr(item, "language", None)
            if language:
                return str(language)
        return None

    @staticmethod
    def detect_language(text):
        chinese = sum("\u4e00" <= char <= "\u9fff" for char in text)
        english = sum(char.isalpha() for char in text)
        return "Chinese" if chinese >= english else "English"

    @staticmethod
    def _deduplicate_overlap_segments(segments):
        deduplicated = []
        for segment in segments:
            if not deduplicated:
                deduplicated.append(segment)
                continue
            previous = deduplicated[-1]
            same_text = "".join(previous["text"].split()) == "".join(
                segment["text"].split()
            )
            overlaps = min(previous["end"], segment["end"]) > max(
                previous["start"], segment["start"]
            )
            if same_text and overlaps:
                if segment["end"] - segment["start"] > previous["end"] - previous["start"]:
                    deduplicated[-1] = segment
                continue
            deduplicated.append(segment)
        return deduplicated
