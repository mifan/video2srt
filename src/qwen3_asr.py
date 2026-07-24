import logging
import torch

from qwen_asr import Qwen3ASRModel


class Qwen3Recognizer:


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
            f"Using device: {self.device}"
        )


        self.logger.info(
            "Loading Qwen3-ASR model..."
        )


        self.model = Qwen3ASRModel.from_pretrained(

            model_path,

            dtype=torch.float16,

            device_map=self.device

        )


        self.logger.info(
            "Qwen3-ASR loaded"
        )



    def detect_device(
        self,
        device
    ):

        if device != "auto":

            return device


        if torch.cuda.is_available():

            gpu = torch.cuda.get_device_name(
                0
            )

            self.logger.info(
                f"CUDA GPU detected: {gpu}"
            )


            return "cuda:0"


        return "cpu"



    def transcribe(
        self,
        audio_file
    ):

        self.logger.info(
            f"Recognizing: {audio_file}"
        )


        result = self.model.transcribe(

            audio=str(audio_file)

        )


        #
        # qwen-asr 返回 List
        #

        if isinstance(
            result,
            list
        ):

            return result


        return [
            result
        ]