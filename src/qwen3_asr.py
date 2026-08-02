import logging
from qwen_asr import Qwen3ASRModel
from src.runtime import release_accelerator_memory, resolve_inference_runtime


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


        self.model_path = model_path
        self.model = None


    def load(self):
        if self.model is not None:
            return

        self.logger.info("Loading Qwen3-ASR model...")
        self.model = Qwen3ASRModel.from_pretrained(
            self.model_path,
            dtype=self.dtype,
            device_map=self.device,
        )
        self.logger.info("Qwen3-ASR loaded")


    def release(self):
        if self.model is None:
            return

        self.logger.info("Releasing Qwen3-ASR model")
        self.model = None
        release_accelerator_memory()

    def transcribe(
        self,
        audio_file,
        language=None
    ):

        self.load()

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
