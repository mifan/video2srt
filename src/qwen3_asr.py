import logging
from qwen_asr import Qwen3ASRModel
from src.runtime import resolve_inference_runtime


class Qwen3Recognizer:


    def __init__(
        self,
        model_path,
        device="auto"
    ):

        self.logger = logging.getLogger(
            "video2srt"
        )


        runtime = resolve_inference_runtime(
            device
        )

        self.device = runtime.device
        self.dtype = runtime.dtype


        self.logger.info(
            f"Using device: {self.device} ({self.dtype})"
        )


        self.logger.info(
            "Loading Qwen3-ASR model..."
        )


        self.model = Qwen3ASRModel.from_pretrained(

            model_path,

            dtype=self.dtype,

            device_map=self.device

        )


        self.logger.info(
            "Qwen3-ASR loaded"
        )

    def transcribe(
        self,
        audio_file,
        language=None
    ):

        self.logger.info(
            f"Recognizing: {audio_file}"
        )


        options = {
            "audio": str(audio_file),
        }

        if language and language.lower() != "auto":
            options["language"] = language

        result = self.model.transcribe(

            **options

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
