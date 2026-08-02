import logging
from qwen_asr import Qwen3ForcedAligner
from src.runtime import release_accelerator_memory, resolve_inference_runtime



class Qwen3Aligner:


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
            f"ForcedAligner device: {self.device} ({self.dtype})"
        )


        self.model_path = model_path
        self.model = None


    def load(self):
        if self.model is not None:
            return

        self.logger.info("Loading Qwen3-ForcedAligner...")
        self.model = Qwen3ForcedAligner.from_pretrained(
            self.model_path,
            device_map=self.device,
            dtype=self.dtype,
        )
        self.logger.info("Qwen3-ForcedAligner loaded")


    def release(self):
        if self.model is None:
            return

        self.logger.info("Releasing Qwen3-ForcedAligner model")
        self.model = None
        release_accelerator_memory()

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


        self.load()

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
