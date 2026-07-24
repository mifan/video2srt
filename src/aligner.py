import logging
import torch

from qwen_asr import Qwen3ForcedAligner



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
            f"ForcedAligner device: {self.device}"
        )


        self.logger.info(
            "Loading Qwen3-ForcedAligner..."
        )


        self.model = Qwen3ForcedAligner.from_pretrained(

            model_path,

            device_map=self.device,

            dtype=torch.float16

        )


        self.logger.info(
            "Qwen3-ForcedAligner loaded"
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
        text,
        language="Chinese"
    ):

        """
        audio_file:
            wav path

        text:
            ASR output text

        language:
            Chinese / English
        """


        self.logger.info(
            "Running forced alignment..."
        )


        results = self.model.align(

            audio=str(audio_file),

            text=text,

            language=language

        )


        if not results:

            raise RuntimeError(
                "Forced alignment returned empty result"
            )


        return results[0]