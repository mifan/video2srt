import logging
from pathlib import Path

import torch


from src.audio_splitter import AudioSplitter
from src.ffmpeg_util import FFmpegExtractor

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
        # ffmpeg
        #

        self.extractor = FFmpegExtractor(

            config["ffmpeg"]["path"]

        )



        #
        # 音频切割
        #

        self.splitter = AudioSplitter(

            chunk_seconds=config
                .get(
                    "chunk",
                    {}
                )
                .get(
                    "seconds",
                    300
                )

        )



        #
        # ASR
        #

        self.asr = Qwen3Recognizer(

            model_path=config["models"]["asr"],

            device=config.get(
                "device",
                "cuda:0"
            )

        )



        #
        # Forced Align
        #

        self.aligner = Qwen3Aligner(

            model_path=config["models"]["aligner"],

            device=config.get(
                "device",
                "cuda:0"
            )

        )



        #
        # 字幕切分
        #

        self.segmenter = SubtitleSegmenter(

            max_chars=24,

            max_duration=6,

            max_cps=15

        )



        #
        # 标点恢复
        #

        self.punctuation = PunctuationRestorer()



        #
        # SRT
        #

        self.writer = SRTWriter()



    # =====================================================
    # 主入口
    # =====================================================


    def run(
        self,
        video_file
    ):


        video_file = Path(
            video_file
        )


        self.logger.info(

            f"Start processing: {video_file}"

        )



        #
        # 1. 提取音频
        #

        wav_file = self.extractor.extract(

            video_file

        )



        #
        # 2. 切 chunk
        #

        chunks = self.splitter.split(

            wav_file

        )



        all_segments = []



        #
        # 逐 chunk 处理
        #

        for index, chunk in enumerate(chunks):


            self.logger.info(

                f"Processing chunk "
                f"{index + 1}/{len(chunks)}"

            )



            offset = (

                index *
                self.splitter.chunk_seconds

            )



            #
            # --------------------
            # ASR
            # --------------------
            #

            asr_result = self.asr.transcribe(

                chunk

            )


            #
            # 原始带标点文本
            #

            original_text = (

                self.extract_text(
                    asr_result
                )

            )



            if not original_text.strip():

                continue



            self.logger.info(

                original_text[:100]

            )



            #
            # --------------------
            # Forced Align
            # --------------------
            #

            align_result = self.aligner.align(

                chunk,

                original_text,

                self.detect_language(
                    original_text
                )

            )



            #
            # --------------------
            # 字级 -> 字幕块
            # --------------------
            #

            segments = self.segmenter.segment(

                align_result

            )



            #
            # 标点恢复
            #

            for seg in segments:


                seg["text"] = (

                    self.punctuation.restore(

                        seg["text"],

                        original_text

                    )

                )



                #
                # chunk时间偏移
                #

                seg["start"] += offset

                seg["end"] += offset



                all_segments.append(

                    seg

                )



            #
            # 清理GPU
            #

            self.cleanup_gpu()



        #
        # 输出 SRT
        #

        srt_file = (

            video_file.parent /

            (
                video_file.stem
                +
                ".srt"
            )

        )



        self.writer.write(

            all_segments,

            srt_file

        )


        self.logger.info(

            f"Finished: {srt_file}"

        )


        return srt_file



    # =====================================================
    # 工具函数
    # =====================================================


    def extract_text(
        self,
        result
    ):


        text = ""



        #
        # qwen-asr 输出兼容
        #

        if isinstance(
            result,
            str
        ):

            return result



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


        return text



    def detect_language(
        self,
        text
    ):


        zh = 0

        en = 0



        for c in text:


            if (
                '\u4e00'
                <= c
                <=
                '\u9fff'
            ):

                zh += 1


            elif c.isalpha():

                en += 1



        if zh >= en:

            return "Chinese"


        return "English"



    def cleanup_gpu(
        self
    ):


        if torch.cuda.is_available():

            torch.cuda.empty_cache()