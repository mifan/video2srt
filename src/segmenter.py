import logging
import unicodedata
from difflib import SequenceMatcher


class SubtitleSegmenter:

    SENTENCE_ENDINGS = frozenset("。！？!?；;…")
    WEAK_BREAKS = frozenset("，,、:： \t\n")

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

            segments.extend(
                self._split_long_sentence(
                    sentence,
                    items,
                    start_item,
                    end_item,
                )
            )
            last_end_item = end_item

        if last_end_item < len(items) - 1 and segments:
            # Preserve an unmatched tail without moving earlier cue boundaries.
            segments[-1]["end"] = items[-1].end_time

        return segments

    def _split_long_sentence(self, sentence, items, start_item, end_item):
        """Apply a second split only when one ASR sentence is too long."""
        duration = items[end_item].end_time - items[start_item].start_time
        if (
            self._text_length(sentence) <= self.max_chars
            and duration <= self.max_duration
        ):
            self._warn_if_fast(sentence, duration)
            return [{
                "start": items[start_item].start_time,
                "end": items[end_item].end_time,
                "text": sentence,
            }]

        parts = self._split_text_at_natural_boundaries(sentence, duration)
        if len(parts) == 1:
            self.logger.warning(
                "Long ASR sentence has no natural split point: %s",
                sentence,
            )

        available_items = end_item - start_item + 1
        while len(parts) > available_items:
            parts[-2] = f"{parts[-2]}{parts[-1]}"
            parts.pop()

        segments = []
        item_index = start_item

        for part_index, part in enumerate(parts):
            if part_index == len(parts) - 1:
                part_end_item = end_item
            else:
                target_length = max(1, len(self._normalise_for_alignment(part)))
                part_start_item = item_index
                collected_length = 0
                last_assignable_item = end_item - (
                    len(parts) - part_index - 1
                )

                while item_index <= last_assignable_item:
                    collected_length += len(
                        self._normalise_for_alignment(items[item_index].text)
                    )
                    item_index += 1
                    if collected_length >= target_length:
                        break

                part_end_item = max(part_start_item, item_index - 1)

            part_duration = (
                items[part_end_item].end_time
                - items[item_index if part_index == len(parts) - 1 else part_start_item]
                .start_time
            )
            self._warn_if_fast(part, part_duration)
            segments.append({
                "start": items[
                    item_index if part_index == len(parts) - 1 else part_start_item
                ].start_time,
                "end": items[part_end_item].end_time,
                "text": part,
            })
            item_index = part_end_item + 1

        return segments

    def _split_text_at_natural_boundaries(self, text, total_duration):
        parts = []
        remaining = text.strip()
        full_length = max(self._text_length(remaining), 1)

        while remaining:
            remaining_length = self._text_length(remaining)
            remaining_duration = total_duration * remaining_length / full_length

            if not self._needs_secondary_split(remaining, remaining_duration):
                parts.append(remaining)
                break

            break_at = None
            current_length = 0
            total_length = max(remaining_length, 1)

            for index, char in enumerate(remaining):
                current_length += self._text_length(char)
                estimated_duration = (
                    remaining_duration * current_length / total_length
                )

                if char in self.WEAK_BREAKS:
                    break_at = index + 1

                if (
                    current_length >= self.max_chars
                    or estimated_duration >= self.max_duration
                ):
                    break

            cut_at = break_at or index + 1
            part = remaining[:cut_at].strip()
            if not part or cut_at >= len(remaining):
                parts.append(remaining)
                break

            parts.append(part)
            remaining = remaining[cut_at:].strip()

        return parts

    def _needs_secondary_split(self, text, duration):
        return (
            self._text_length(text) > self.max_chars
            or duration > self.max_duration
        )

    def _warn_if_fast(self, text, duration):
        if duration > 0 and self._text_length(text) / duration > self.max_cps:
            self.logger.warning(
                "Subtitle exceeds max CPS (%.1f > %.1f): %s",
                self._text_length(text) / duration,
                self.max_cps,
                text,
            )

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
