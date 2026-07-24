import subprocess
import logging
from pathlib import Path
import shutil


class FFmpegExtractor:


    def __init__(self, ffmpeg_path, temp_dir="temp"):

        self.logger = logging.getLogger(
            "video2srt"
        )

        self.ffmpeg = Path(
            ffmpeg_path
        )

        self.temp_dir = Path(
            temp_dir
        )


        self.temp_dir.mkdir(
            exist_ok=True
        )


    def check(self):

        """
        检查 ffmpeg 是否存在
        """

        if self.ffmpeg.exists():

            return True


        #
        # 如果配置的是 ffmpeg.exe
        # 但 PATH 中存在
        #

        if shutil.which(
            "ffmpeg"
        ):

            self.ffmpeg = Path(
                "ffmpeg"
            )

            return True


        raise RuntimeError(
            f"FFmpeg not found: {self.ffmpeg}"
        )



    def extract(
        self,
        video_file
    ):

        """
        提取音频

        video:
            xxx.mp4

        output:
            temp/xxx.wav
        """

        self.check()


        video_file = Path(
            video_file
        )


        if not video_file.exists():

            raise FileNotFoundError(
                video_file
            )


        output = (
            self.temp_dir /
            (
                video_file.stem
                +
                ".wav"
            )
        )


        self.logger.info(
            "Extract audio:"
        )

        self.logger.info(
            f"  {video_file}"
        )


        cmd = [

            str(self.ffmpeg),

            "-y",

            "-i",
            str(video_file),


            # 音频参数

            "-vn",

            "-ac",
            "1",

            "-ar",
            "16000",


            "-c:a",
            "pcm_s16le",


            str(output)

        ]


        self.logger.info(
            "Running ffmpeg..."
        )


        result = subprocess.run(

            cmd,

            stdout=subprocess.PIPE,

            stderr=subprocess.PIPE,

            text=True

        )


        if result.returncode != 0:


            self.logger.error(
                result.stderr
            )


            raise RuntimeError(
                "ffmpeg failed"
            )


        if not output.exists():

            raise RuntimeError(
                "Audio extraction failed"
            )


        self.logger.info(
            f"Audio ready: {output}"
        )


        return output