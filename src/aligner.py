import logging
import torch

from transformers import AutoModelForSpeechSeq2Seq


class Qwen3Aligner:


    def __init__(
        self,
        model_path,
        device="auto"
    ):

        self.logger = logging.getLogger(
            "video2srt"
        )


        self.device = self.detect_device(
            device
        )


        self.logger.info(
            f"Aligner device: {self.device}"
        )


        self.logger.info(
            "Loading Qwen3 ForcedAligner..."
        )


        self.model = (
            AutoModelForSpeechSeq2Seq
            .from_pretrained(

                model_path,

                torch_dtype=torch.float16,

                device_map=self.device

            )
        )


        self.logger.info(
            "ForcedAligner loaded"
        )



    def detect_device(
        self,
        device
    ):

        if device != "auto":

            return device


        if torch.cuda.is_available():

            return "cuda:0"


        return "cpu"



    def align(
        self,
        audio_file,
        text
    ):

        """
        输入:

            wav
            text


        输出:

            [
              {
                start: float,
                end: float,
                text: str
              }
            ]
        """


        self.logger.info(
            "Running alignment..."
        )


        #
        # 注意：
        #
        # Qwen3 ForcedAligner
        # 官方接口可能随版本变化
        #
        # 这里封装接口，
        # 后续只需要调整内部调用。
        #


        result = self.model.align(

            audio=str(audio_file),

            text=text

        )


        return result