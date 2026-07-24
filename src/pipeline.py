import logging

from src.ffmpeg_util import FFmpegExtractor


class Pipeline:


    def __init__(
        self,
        config
    ):

        self.logger = logging.getLogger(
            "video2srt"
        )


        self.config = config



    def run(
        self,
        video
    ):


        self.logger.info(
            "Pipeline started"
        )


        #
        # Step 2:
        # extract audio
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


        self.logger.info(
            f"WAV file: {wav}"
        )


        #
        # Step 3:
        # Qwen3-ASR
        #


        self.logger.info(
            "ASR not implemented yet"
        )



        return wav