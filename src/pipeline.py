import logging

from src.ffmpeg_util import FFmpegExtractor
from src.qwen3_asr import Qwen3Recognizer



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



    def run(
        self,
        video
    ):


        self.logger.info(
            "Pipeline started"
        )


        #
        # Step 2
        #

        extractor = FFmpegExtractor(

            self.config.get(
                "ffmpeg",
                "exe"
            )

        )


        wav = extractor.extract(
            video
        )



        #
        # Step 3
        #

        result = self.asr.transcribe(
            wav
        )


        self.logger.info(
            "Recognition finished"
        )


        for item in result:

            self.logger.info(
                item.text
            )


        return result