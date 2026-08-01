import logging
import subprocess
from pathlib import Path



class AudioSplitter:


    def __init__(
        self,
        chunk_seconds=300,
        temp_dir="temp/chunks",
        ffmpeg_path="ffmpeg"
    ):

        self.logger = logging.getLogger(
            "video2srt"
        )


        self.chunk_seconds = chunk_seconds


        self.ffmpeg = str(
            ffmpeg_path
        )


        self.output_dir = Path(
            temp_dir
        )


        self.output_dir.mkdir(
            parents=True,
            exist_ok=True
        )



    def split(
        self,
        wav_file
    ):

        """
        split wav into chunks

        default:
            300 seconds = 5 minutes

        """


        wav_file = Path(
            wav_file
        )


        output_pattern = (
            self.output_dir /
            (
                wav_file.stem
                +
                "_%03d.wav"
            )
        )


        self.logger.info(
            f"Splitting audio: {wav_file}"
        )


        cmd = [

            self.ffmpeg,

            "-y",

            "-i",
            str(wav_file),

            "-f",
            "segment",

            "-segment_time",
            str(self.chunk_seconds),

            "-ac",
            "1",

            "-ar",
            "16000",

            "-c:a",
            "pcm_s16le",

            str(output_pattern)

        ]



        result = subprocess.run(

            cmd,

            stdout=subprocess.PIPE,

            stderr=subprocess.PIPE,

            text=True

        )



        if result.returncode != 0:

            raise RuntimeError(
                result.stderr
            )



        chunks = sorted(

            self.output_dir.glob(
                wav_file.stem + "_*.wav"
            )

        )


        if not chunks:

            raise RuntimeError(
                "No chunks generated"
            )


        self.logger.info(
            f"Generated chunks: {len(chunks)}"
        )


        return chunks



    def get_offset(
        self,
        chunk_index
    ):

        """
        calculate chunk start time

        """

        return (
            chunk_index *
            self.chunk_seconds
        )
