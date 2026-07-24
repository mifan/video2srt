import logging


class Pipeline:


    def __init__(self):

        self.logger = logging.getLogger(
            "video2srt"
        )


    def run(self, video):

        self.logger.info(
            f"Input video: {video}"
        )


        self.logger.info(
            "Pipeline started"
        )


        #
        # 后面这里加入：
        #
        # 1. ffmpeg extract audio
        #
        # 2. Qwen3-ASR
        #
        # 3. ForcedAligner
        #
        # 4. SRT writer
        #


        self.logger.info(
            "Pipeline finished"
        )