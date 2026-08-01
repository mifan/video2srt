import logging
import unicodedata
from difflib import SequenceMatcher


class SubtitleSegmenter:

    SENTENCE_ENDINGS = frozenset("。！？!?；;…")

    def __init__(self, max_chars=24, max_duration=6.0, max_cps=15):
        self.logger = logging.getLogger("video2srt")
        # Used only by the legacy fallback when ASR text is unavailable.
        self.max_chars = max_chars
        self.max_duration = max_duration
        self.max_cps = max_cps

    def segment(self, align_result, asr_text=None):
        """Create ASR-sentence subtitles and obtain their times from alignment."""
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

    def split_sentences(self, text):
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

    def _segment_by_asr_sentences(self, items, sentences):
        if not items:
            self.logger.warning("Forced aligner returned no timestamp items")
            return []

        sentence_specs, source_text = self._build_sentence_specs(sentences)
        alignment_text, alignment_char_to_item = self._build_alignment_text(items)
        if not source_text or not alignment_text:
            self.logger.warning("ASR or alignment text is empty after normalization")
            return []

        source_to_alignment = self._match_source_to_alignment(
            source_text,
            alignment_text,
        )
        segments = []
        last_end_item = -1

        for sentence, source_start, source_end in sentence_specs:
            alignment_positions = [
                source_to_alignment[position]
                for position in range(source_start, source_end)
                if source_to_alignment[position] is not None
            ]

            if alignment_positions:
                alignment_start = min(alignment_positions)
                alignment_end = max(alignment_positions)
                if len(alignment_positions) != source_end - source_start:
                    self.logger.warning(
                        "ASR/alignment text differs near sentence boundary: %s",
                        sentence,
                    )
            else:
                self.logger.warning(
                    "No exact alignment text match for sentence: %s",
                    sentence,
                )
                alignment_start, alignment_end = self._estimate_alignment_span(
                    source_start,
                    source_end,
                    len(source_text),
                    len(alignment_text),
                )

            start_item = max(
                alignment_char_to_item[alignment_start],
                last_end_item + 1,
            )
            end_item = alignment_char_to_item[alignment_end]
            if start_item > end_item:
                self.logger.warning(
                    "Could not assign a distinct alignment range to sentence: %s",
                    sentence,
                )
                continue

            segments.append({
                "start": items[start_item].start_time,
                "end": items[end_item].end_time,
                "text": sentence,
            })
            last_end_item = end_item

        if last_end_item < len(items) - 1 and segments:
            # Preserve an unmatched tail without moving earlier cue boundaries.
            segments[-1]["end"] = items[-1].end_time

        return segments

    def _build_sentence_specs(self, sentences):
        specs = []
        source_parts = []
        source_position = 0

        for sentence in sentences:
            normalized = self._normalise_for_alignment(sentence)
            if not normalized:
                continue

            source_end = source_position + len(normalized)
            specs.append((sentence, source_position, source_end))
            source_parts.append(normalized)
            source_position = source_end

        return specs, "".join(source_parts)

    def _build_alignment_text(self, items):
        characters = []
        char_to_item = []

        for item_index, item in enumerate(items):
            normalized = self._normalise_for_alignment(item.text)
            characters.append(normalized)
            char_to_item.extend([item_index] * len(normalized))

        return "".join(characters), char_to_item

    @staticmethod
    def _match_source_to_alignment(source_text, alignment_text):
        source_to_alignment = [None] * len(source_text)
        matcher = SequenceMatcher(
            None,
            source_text,
            alignment_text,
            autojunk=False,
        )

        for block in matcher.get_matching_blocks():
            for offset in range(block.size):
                source_to_alignment[block.a + offset] = block.b + offset

        return source_to_alignment

    @staticmethod
    def _estimate_alignment_span(
        source_start,
        source_end,
        source_length,
        alignment_length,
    ):
        alignment_start = min(
            int(source_start / source_length * alignment_length),
            alignment_length - 1,
        )
        alignment_end = min(
            max(
                int(source_end / source_length * alignment_length) - 1,
                alignment_start,
            ),
            alignment_length - 1,
        )
        return alignment_start, alignment_end

    @staticmethod
    def _normalise_for_alignment(text):
        """Normalize comparison text without changing output subtitle text."""
        return "".join(
            char
            for char in str(text)
            if not char.isspace()
            and not unicodedata.category(char).startswith("P")
        ).casefold()

    def _segment_by_alignment(self, items):
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

    def _should_split(self, text, duration):
        if text.endswith(("。", "！", "？", ".", "!", "?")):
            return True
        if duration >= self.max_duration:
            return True
        if self._text_length(text) >= self.max_chars:
            return True
        return duration > 0 and self._text_length(text) / duration > self.max_cps

    def _text_length(self, text):
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
