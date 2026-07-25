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



        self.extractor = FFmpegExtractor(

            self.config.get(
                "ffmpeg",
                "exe"
            )

        )



        self.splitter = AudioSplitter(

            chunk_seconds=300

        )



        self.asr = Qwen3Recognizer(

            self.config.get(
                "model",
                "asr"
            ),

            self.config.get(
                "device"
            )

        )



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




    def run(
        self,
        video_file
    ):


        video_file = Path(
            video_file
        )


        self.logger.info(
            f"Processing {video_file}"
        )



        #
        # Step 1
        #
        # extract wav
        #

        wav = self.extractor.extract(
            video_file
        )



        #
        # Step 2
        #
        # split wav
        #

        chunks = self.splitter.split(
            wav
        )



        all_segments = []



        #
        # Step 3
        #
        # process chunk one by one
        #

        for index, chunk in enumerate(chunks):


            self.logger.info(
                f"Processing chunk {index+1}/{len(chunks)}"
            )


            offset = (
                index *
                self.splitter.chunk_seconds
            )



            #
            # ASR
            #

            asr_result = self.asr.transcribe(

                chunk

            )



            text = self.build_text(
                asr_result
            )



            if not text.strip():

                continue



            #
            # Forced Align
            #

            align_result = self.aligner.align(

                chunk,

                text,

                self.detect_language(
                    text
                )

            )



            #
            # 字级时间
            # 转字幕段
            #

            segments = self.segmenter.segment(

                align_result

            )



            #
            # 修正时间偏移
            #

            for seg in segments:


                seg["start"] += offset

                seg["end"] += offset


                all_segments.append(
                    seg
                )



            #
            # 清理显存
            #

            if torch.cuda.is_available():

                torch.cuda.empty_cache()



        #
        # Step 4
        #
        # write srt
        #

        output = (

            video_file.parent /

            (
                video_file.stem
                +
                ".srt"
            )

        )



        self.writer.write(

            all_segments,

            output

        )


        return output




    def build_text(
        self,
        result
    ):

        text = ""


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

                text += item["text"]


        return text



    def detect_language(
        self,
        text
    ):


        zh = sum(

            1 for c in text

            if '\u4e00' <= c <= '\u9fff'

        )


        en = sum(

            1 for c in text

            if c.isalpha()

        )


        if zh >= en:

            return "Chinese"


        return "English"