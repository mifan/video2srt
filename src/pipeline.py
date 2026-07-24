import logging
from pathlib import Path


from src.ffmpeg_util import FFmpegExtractor
from src.qwen3_asr import Qwen3Recognizer
from src.aligner import Qwen3Aligner
from src.subtitle import SRTWriter
from src.segmenter import SubtitleSegmenter

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
        # 初始化 FFmpeg
        #

        self.extractor = FFmpegExtractor(

            self.config.get(
                "ffmpeg",
                "exe"
            )

        )


        #
        # 初始化 ASR
        #

        self.asr = Qwen3Recognizer(

            self.config.get(
                "model",
                "asr"
            ),

            self.config.get(
                "device"
            )

        )


        #
        # 初始化 ForcedAligner
        #

        self.aligner = Qwen3Aligner(

            self.config.get(
                "model",
                "aligner"
            ),

            self.config.get(
                "device"
            )

        )

        self.segmenter = SubtitleSegmenter()

        self.writer = SRTWriter()


        self.logger.info(
            "Pipeline initialized"
        )



    def run(
        self,
        video_file
    ):

        """
        主处理流程

        input:

            video.mp4


        output:

            subtitle segments

        """


        video_file = Path(
            video_file
        )


        self.logger.info(
            "=" * 60
        )

        self.logger.info(
            f"Processing: {video_file}"
        )



        #
        # Step 2
        #
        # Extract audio
        #

        wav_file = self.extractor.extract(

            video_file

        )


        self.logger.info(
            f"Audio extracted: {wav_file}"
        )



        #
        # Step 3
        #
        # ASR
        #

        self.logger.info(
            "Running ASR..."
        )


        asr_result = self.asr.transcribe(

            wav_file

        )


        if not asr_result:

            raise RuntimeError(
                "ASR returned empty result"
            )


        self.logger.info(
            "ASR finished"
        )



        #
        # 合并 ASR 文本
        #

        text = self.build_text(

            asr_result

        )


        self.logger.info(
            "Recognized text:"
        )


        self.logger.info(
            text[:200]
        )



        #
        # Step 4
        #
        # Forced Alignment
        #

        self.logger.info(
            "Running ForcedAligner..."
        )


        segments = self.aligner.align(
            wav_file,
            text,
            language=self.detect_language(text)
        )


        if not segments:

            raise RuntimeError(
                "Alignment failed"
            )


        self.logger.info(
            "Alignment finished"
        )


        self.logger.info(
            f"Segments: {len(segments)}"
        )

        #
        # Step 5
        # generate srt
        #

        srt_file = (
        video_file.parent /
            (
                video_file.stem
                +
                ".srt"
            )
        )


        subtitle_segments = self.segmenter.segment(
            segments
        )


        self.writer.write(
            subtitle_segments,
            srt_file
        )


        return srt_file





    def detect_language(self, text):

        chinese = 0
        english = 0


        for c in text:

            if '\u4e00' <= c <= '\u9fff':
                chinese += 1
            elif c.isalpha():
                english += 1


        if chinese >= english:
            return "Chinese"
        return "English"



    def build_text(
        self,
        asr_result
    ):

        """
        把 ASR 输出转换为纯文本

        兼容:

        [
          Result(text="xxx"),
          Result(text="yyy")
        ]

        或:

        [
          {
            text:"xxx"
          }
        ]

        """


        texts = []


        for item in asr_result:


            if hasattr(
                item,
                "text"
            ):

                texts.append(
                    item.text
                )


            elif isinstance(
                item,
                dict
            ):

                texts.append(
                    item.get(
                        "text",
                        ""
                    )
                )


            else:

                texts.append(
                    str(item)
                )



        return "".join(
            texts
        )