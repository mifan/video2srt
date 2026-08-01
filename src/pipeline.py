import logging
from pathlib import Path

import torch


from src.ffmpeg_util import FFmpegExtractor
from src.audio_splitter import AudioSplitter

from src.qwen3_asr import Qwen3Recognizer
from src.aligner import Qwen3Aligner

from src.segmenter import SubtitleSegmenter
from src.subtitle import SRTWriter

class Pipeline:


    def __init__(
        self,
        config
    ):

        self.logger = logging.getLogger(
            "video2srt"
        )


        self.config = config

        self.language = config.get(

            "language"

        )



        #
        # FFmpeg
        #

        self.extractor = FFmpegExtractor(

            config.get(
                "ffmpeg",
                "path"
            )

        )



        #
        # Audio chunk splitter
        #

        self.splitter = AudioSplitter(

            chunk_seconds=config.get(

                "chunk",
                "seconds"

            ),

            overlap_seconds=config.get(

                "chunk",
                "overlap_seconds"

            ),

            ffmpeg_path=config.get(

                "ffmpeg",
                "path"

            )

        )



        #
        # Qwen3-ASR
        #

        self.asr = Qwen3Recognizer(

            model_path=config.get(

                "models",
                "asr"

            ),

            device=config.get(

                "device"

            )

        )



        #
        # Qwen3 ForcedAligner
        #

        self.aligner = Qwen3Aligner(

            model_path=config.get(

                "models",
                "aligner"

            ),

            device=config.get(

                "device"

            )

        )



        #
        # Smart subtitle segmenter
        #

        self.segmenter = SubtitleSegmenter(

            max_chars=config.get(

                "subtitle",
                "max_chars"

            ),

            max_duration=config.get(

                "subtitle",
                "max_duration_seconds"

            ),

            max_cps=config.get(

                "subtitle",
                "max_cps"

            )

        )

        #
        # SRT writer
        #

        self.writer = SRTWriter()



    # ==================================================
    # Main pipeline
    # ==================================================

    def run(
        self,
        video_file
    ):


        video_file = Path(
            video_file
        )


        self.logger.info(

            f"Processing: {video_file}"

        )



        #
        # Step 1
        # Extract audio
        #

        wav_file = self.extractor.extract(

            video_file

        )



        #
        # Step 2
        # Split audio
        #

        chunks = self.splitter.split(

            wav_file

        )



        all_segments = []



        #
        # Step 3
        # Process chunks
        #

        for index, chunk in enumerate(chunks):


            self.logger.info(

                f"Chunk {index + 1}/{len(chunks)}: {chunk.path}"

            )



            #
            # chunk start time
            #

            offset = chunk.start_time



            #
            # --------------------------
            # ASR
            # --------------------------
            #

            asr_result = self.asr.transcribe(

                chunk.path,

                self.language

            )



            original_text = self.extract_text(

                asr_result

            )



            if not original_text.strip():

                self.logger.warning(

                    "Empty ASR result, skip"

                )

                continue



            self.logger.info(

                "ASR: "
                +
                original_text[:100]

            )



            #
            # --------------------------
            # Forced Alignment
            # --------------------------
            #

            align_result = self.aligner.align(

                chunk.path,

                original_text,

                self.resolve_language(

                    asr_result,

                    original_text

                )

            )



            #
            # --------------------------
            # Generate subtitle blocks
            # --------------------------
            #

            segments = self.segmenter.segment(

                align_result,

                original_text

            )



            for seg in segments:



                #
                # add chunk offset
                #

                seg["start"] += offset

                seg["end"] += offset



                all_segments.append(

                    seg

                )



            #
            # Release CUDA memory
            #

            self.cleanup_gpu()



        #
        # Step 4
        # Write SRT
        #

        output_file = (

            video_file.parent /

            (
                video_file.stem

                +

                ".srt"

            )

        )


        all_segments = self._deduplicate_overlap_segments(

            all_segments

        )



        self.writer.write(

            all_segments,

            output_file

        )


        self.logger.info(

            f"Finished: {output_file}"

        )


        return output_file



    # ==================================================
    # Helpers
    # ==================================================


    def extract_text(
        self,
        result
    ):

        """
        Compatible with qwen-asr outputs
        """


        if isinstance(
            result,
            str
        ):

            return result



        text = ""



        if isinstance(
            result,
            list
        ):


            for item in result:


                if hasattr(

                    item,

                    "text"

                ):

                    text += item.text



                elif isinstance(

                    item,

                    dict

                ):

                    text += item.get(

                        "text",

                        ""

                    )



        elif hasattr(
            result,
            "text"
        ):

            text = result.text



        return text


    @staticmethod
    def _deduplicate_overlap_segments(segments):
        """Remove duplicate cues produced by neighboring overlapping chunks."""

        deduplicated = []

        for segment in segments:
            if not deduplicated:
                deduplicated.append(segment)
                continue

            previous = deduplicated[-1]
            same_text = (
                "".join(previous["text"].split())
                == "".join(segment["text"].split())
            )
            overlaps = (
                min(previous["end"], segment["end"])
                > max(previous["start"], segment["start"])
            )

            if same_text and overlaps:
                previous_duration = previous["end"] - previous["start"]
                segment_duration = segment["end"] - segment["start"]
                if segment_duration > previous_duration:
                    deduplicated[-1] = segment
                continue

            deduplicated.append(segment)

        return deduplicated



    def detect_language(
        self,
        text
    ):


        chinese = 0

        english = 0



        for c in text:


            if (

                '\u4e00'

                <=

                c

                <=

                '\u9fff'

            ):

                chinese += 1



            elif c.isalpha():

                english += 1



        if chinese >= english:

            return "Chinese"


        return "English"


    def resolve_language(
        self,
        asr_result,
        text
    ):
        """Prefer explicit configuration, then Qwen3-ASR language detection."""

        if self.language and self.language.lower() != "auto":
            return self.language

        detected = self.extract_result_language(asr_result)
        if detected:
            self.logger.info(
                f"ASR detected language: {detected}"
            )
            return detected

        fallback = self.detect_language(text)
        self.logger.warning(
            f"ASR language unavailable; using heuristic: {fallback}"
        )
        return fallback


    @staticmethod
    def extract_result_language(result):
        """Read the language field from qwen-asr object or dictionary results."""

        candidates = result if isinstance(result, list) else [result]

        for item in candidates:
            if isinstance(item, dict):
                language = item.get("language")
            else:
                language = getattr(item, "language", None)

            if language:
                return str(language)

        return None



    def cleanup_gpu(
        self
    ):


        if torch.cuda.is_available():

            torch.cuda.empty_cache()
