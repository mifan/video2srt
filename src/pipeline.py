import logging
from pathlib import Path

import torch


from src.ffmpeg_util import FFmpegExtractor
from src.audio_splitter import AudioSplitter

from src.qwen3_asr import Qwen3Recognizer
from src.aligner import Qwen3Aligner

from src.segmenter import SubtitleSegmenter
from src.subtitle import SRTWriter

from src.punctuation import PunctuationRestorer



class Pipeline:


    def __init__(
        self,
        config
    ):

        self.logger = logging.getLogger(
            "video2srt"
        )


        self.config = config



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

            max_chars=24,

            max_duration=6.0,

            max_cps=15

        )



        #
        # punctuation restore
        #

        self.punctuation = PunctuationRestorer()



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

                f"Chunk {index + 1}/{len(chunks)}: {chunk}"

            )



            #
            # chunk start time
            #

            offset = (

                index *

                self.splitter.chunk_seconds

            )



            #
            # --------------------------
            # ASR
            # --------------------------
            #

            asr_result = self.asr.transcribe(

                chunk

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

                chunk,

                original_text,

                self.detect_language(

                    original_text

                )

            )



            #
            # --------------------------
            # Generate subtitle blocks
            # --------------------------
            #

            segments = self.segmenter.segment(

                align_result

            )



            #
            # Restore punctuation
            #

            for seg in segments:


                seg["text"] = self.punctuation.restore(

                    seg["text"],

                    original_text

                )



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



    def cleanup_gpu(
        self
    ):


        if torch.cuda.is_available():

            torch.cuda.empty_cache()
