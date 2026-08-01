import logging
from qwen_asr import Qwen3ForcedAligner
from src.runtime import resolve_inference_runtime



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


        self.logger.info(
            "Loading Qwen3-ForcedAligner..."
        )


        self.model = Qwen3ForcedAligner.from_pretrained(

            model_path,

            device_map=self.device,

            dtype=self.dtype

        )


        self.logger.info(
            "Qwen3-ForcedAligner loaded"
        )

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
