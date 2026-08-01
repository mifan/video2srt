import logging
import unicodedata


class SubtitleSegmenter:


    SENTENCE_ENDINGS = frozenset("。！？!?；;…")


    def __init__(
        self,
        max_chars=24,
        max_duration=6.0,
        max_cps=15
    ):

        self.logger = logging.getLogger(
            "video2srt"
        )

        # Retained for callers that use the legacy, alignment-only fallback.
        self.max_chars = max_chars
        self.max_duration = max_duration
        self.max_cps = max_cps


    def segment(
        self,
        align_result,
        asr_text=None
    ):
        """Create subtitle cues from ASR sentences and alignment timestamps.

        Qwen3-ASR supplies punctuation and sentence boundaries.  The forced
        aligner is deliberately used only to locate the start and end of each
        ASR sentence, so it never changes the sentence text shown in subtitles.
        """

        items = list(align_result.items)

        if not asr_text:
            self.logger.warning(
                "ASR text unavailable; falling back to alignment-based splitting"
            )
            return self._segment_by_alignment(items)

        sentences = self.split_sentences(asr_text)

        if not sentences:
            return []

        return self._segment_by_asr_sentences(items, sentences)


    def split_sentences(
        self,
        text
    ):
        """Split Qwen3-ASR text while retaining its punctuation verbatim."""

        sentences = []
        current = []

        for char in str(text):
            current.append(char)

            if char in self.SENTENCE_ENDINGS:
                sentence = "".join(current).strip()
                if sentence:
                    sentences.append(sentence)
                current = []

        sentence = "".join(current).strip()
        if sentence:
            sentences.append(sentence)

        return sentences


    def _segment_by_asr_sentences(
        self,
        items,
        sentences
    ):
        segments = []
        item_index = 0

        for sentence in sentences:
            target = self._normalise_for_alignment(sentence)
            if not target:
                continue

            start_index = item_index
            aligned_text = ""

            while item_index < len(items):
                item = items[item_index]
                aligned_text += self._normalise_for_alignment(item.text)
                item_index += 1

                if len(aligned_text) >= len(target):
                    break

            if start_index == item_index:
                self.logger.warning(
                    "No alignment timestamps for ASR sentence: %s",
                    sentence
                )
                break

            if aligned_text != target:
                self.logger.warning(
                    "ASR/alignment text differs near sentence boundary: %s",
                    sentence
                )

            segments.append({
                "start": items[start_index].start_time,
                "end": items[item_index - 1].end_time,
                "text": sentence,
            })

        if item_index < len(items) and segments:
            # Preserve all aligned audio if normalization differences left a tail.
            segments[-1]["end"] = items[-1].end_time

        return segments


    @staticmethod
    def _normalise_for_alignment(text):
        """Remove whitespace and punctuation before comparing ASR and aligner text."""

        return "".join(
            char
            for char in str(text)
            if not char.isspace()
            and not unicodedata.category(char).startswith("P")
        )


    def _segment_by_alignment(
        self,
        items
    ):
        """Legacy fallback used only when no ASR text is supplied."""

        segments = []
        current = []
        start = None

        for item in items:
            if start is None:
                start = item.start_time

            current.append(item)
            text = "".join(x.text for x in current)
            duration = item.end_time - start

            if self._should_split(text, duration):
                segments.append(self._make_segment(current, start))
                current = []
                start = None

        if current:
            segments.append(self._make_segment(current, start))

        return segments


    def _should_split(
        self,
        text,
        duration
    ):
        if text.endswith(("。", "！", "？", ".", "!", "?")):
            return True

        if duration >= self.max_duration:
            return True

        if self._text_length(text) >= self.max_chars:
            return True

        return duration > 0 and self._text_length(text) / duration > self.max_cps


    def _text_length(
        self,
        text
    ):
        return sum(1 if self._is_chinese(char) else 0.5 for char in text)


    @staticmethod
    def _is_chinese(char):
        return "\u4e00" <= char <= "\u9fff"


    @staticmethod
    def _make_segment(items, start):
        return {
            "start": start,
            "end": items[-1].end_time,
            "text": "".join(item.text for item in items).strip(),
        }
