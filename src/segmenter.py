import logging
import unicodedata
from difflib import SequenceMatcher


class SubtitleSegmenter:
    SENTENCE_ENDINGS = frozenset("。！？!?；;…")
    WEAK_BREAKS = frozenset("，,、:： \t\n")

    def __init__(
        self,
        max_chars=24,
        max_duration=6.0,
        max_cps=15,
        min_match_ratio=0.85,
        low_match_policy="error",
    ):
        self.logger = logging.getLogger("video2srt")
        self.max_chars = max_chars
        self.max_duration = max_duration
        self.max_cps = max_cps
        self.min_match_ratio = min_match_ratio
        self.low_match_policy = low_match_policy

    def segment(self, align_result, asr_text=None):
        items = list(align_result.items)
        if not asr_text:
            self.logger.warning("ASR text unavailable; using alignment-only fallback")
            return self._segment_by_alignment(items)

        sentences = self.split_sentences(asr_text)
        return self._segment_by_asr_sentences(items, sentences) if sentences else []

    def split_sentences(self, text):
        sentences, current = [], []
        for char in str(text):
            current.append(char)
            if char in self.SENTENCE_ENDINGS:
                sentence = "".join(current).strip()
                if sentence:
                    sentences.append(sentence)
                current = []
        if current and (sentence := "".join(current).strip()):
            sentences.append(sentence)
        return sentences

    def _segment_by_asr_sentences(self, items, sentences):
        if not items:
            self.logger.warning("Forced aligner returned no timestamp items")
            return []

        sentence_specs, source_text = self._build_sentence_specs(sentences)
        alignment_text, char_to_item = self._build_alignment_text(items)
        if not source_text or not alignment_text:
            self.logger.warning("ASR or alignment text is empty after normalization")
            return []

        source_to_alignment = self._match_source_to_alignment(
            source_text, alignment_text
        )
        match_ratio = sum(position is not None for position in source_to_alignment) / len(
            source_to_alignment
        )
        if match_ratio < self.min_match_ratio:
            message = (
                "ASR/alignment match ratio %.1f%% is below configured minimum %.1f%%"
                % (match_ratio * 100, self.min_match_ratio * 100)
            )
            if self.low_match_policy == "error":
                raise RuntimeError(message)
            self.logger.warning("%s; policy=%s", message, self.low_match_policy)
            if self.low_match_policy == "skip":
                return []
            source_to_alignment = [None] * len(source_to_alignment)

        segments = []
        last_end_item = -1
        for sentence, source_start, source_end in sentence_specs:
            item_range = self._item_range_for_source_span(
                source_start, source_end, source_to_alignment, char_to_item
            )
            if item_range is None:
                self.logger.warning("Estimating timestamp range for sentence: %s", sentence)
                item_range = self._estimate_item_range(
                    source_start,
                    source_end,
                    len(source_text),
                    len(items),
                )

            start_item, end_item = item_range
            start_item = max(start_item, last_end_item + 1)
            if start_item > end_item:
                self.logger.warning("No distinct timestamp range for sentence: %s", sentence)
                continue

            segments.extend(
                self._split_long_sentence(
                    sentence,
                    source_start,
                    source_end,
                    items,
                    start_item,
                    end_item,
                    source_to_alignment,
                    char_to_item,
                )
            )
            last_end_item = end_item

        if last_end_item < len(items) - 1 and segments:
            segments[-1]["end"] = items[-1].end_time
        return segments

    def _split_long_sentence(
        self,
        sentence,
        source_start,
        source_end,
        items,
        start_item,
        end_item,
        source_to_alignment,
        char_to_item,
    ):
        duration = items[end_item].end_time - items[start_item].start_time
        part_specs = self._split_text_at_natural_boundaries(sentence, duration)
        if len(part_specs) == 1:
            self._warn_if_fast(sentence, duration)

        segments = []
        last_part_end = start_item - 1
        sentence_length = max(source_end - source_start, 1)

        for text, relative_start, relative_end in part_specs:
            item_range = self._item_range_for_source_span(
                source_start + relative_start,
                source_start + relative_end,
                source_to_alignment,
                char_to_item,
            )
            if item_range is None:
                item_range = self._estimate_item_range(
                    relative_start,
                    relative_end,
                    sentence_length,
                    end_item - start_item + 1,
                    item_offset=start_item,
                )

            part_start, part_end = item_range
            part_start = max(part_start, last_part_end + 1)
            if part_start > part_end:
                self.logger.warning("No distinct timestamp range for subtitle part: %s", text)
                continue

            part_duration = items[part_end].end_time - items[part_start].start_time
            self._warn_if_fast(text, part_duration)
            segments.append({
                "start": items[part_start].start_time,
                "end": items[part_end].end_time,
                "text": text,
            })
            last_part_end = part_end

        return segments

    def _split_text_at_natural_boundaries(self, text, total_duration):
        parts, remaining = [], text.strip()
        full_length = max(self._text_length(remaining), 1)

        while remaining:
            remaining_length = self._text_length(remaining)
            remaining_duration = total_duration * remaining_length / full_length
            if self._fits_subtitle(remaining, remaining_duration):
                parts.append(remaining)
                break

            break_at = None
            current_length = 0
            for index, char in enumerate(remaining):
                current_length += self._text_length(char)
                estimated_duration = remaining_duration * current_length / remaining_length
                if char in self.WEAK_BREAKS:
                    break_at = index + 1
                if current_length >= self.max_chars or estimated_duration >= self.max_duration:
                    break

            cut_at = break_at or index + 1
            part = remaining[:cut_at].strip()
            if not part or cut_at >= len(remaining):
                parts.append(remaining)
                break
            parts.append(part)
            remaining = remaining[cut_at:].strip()

        specs, offset = [], 0
        for part in parts:
            length = len(self._normalise_for_alignment(part))
            specs.append((part, offset, offset + length))
            offset += length
        return specs

    @staticmethod
    def _item_range_for_source_span(start, end, source_to_alignment, char_to_item):
        positions = [
            source_to_alignment[index]
            for index in range(start, end)
            if source_to_alignment[index] is not None
        ]
        if not positions:
            return None
        return char_to_item[min(positions)], char_to_item[max(positions)]

    @staticmethod
    def _estimate_item_range(start, end, source_length, item_count, item_offset=0):
        range_start = item_offset + min(
            int(start / source_length * item_count), item_count - 1
        )
        range_end = item_offset + min(
            max(int(end / source_length * item_count) - 1, range_start - item_offset),
            item_count - 1,
        )
        return range_start, range_end

    def _build_sentence_specs(self, sentences):
        specs, source_parts, position = [], [], 0
        for sentence in sentences:
            normalized = self._normalise_for_alignment(sentence)
            if not normalized:
                continue
            end = position + len(normalized)
            specs.append((sentence, position, end))
            source_parts.append(normalized)
            position = end
        return specs, "".join(source_parts)

    def _build_alignment_text(self, items):
        characters, char_to_item = [], []
        for item_index, item in enumerate(items):
            normalized = self._normalise_for_alignment(item.text)
            characters.append(normalized)
            char_to_item.extend([item_index] * len(normalized))
        return "".join(characters), char_to_item

    @staticmethod
    def _match_source_to_alignment(source_text, alignment_text):
        mapping = [None] * len(source_text)
        matcher = SequenceMatcher(None, source_text, alignment_text, autojunk=False)
        for block in matcher.get_matching_blocks():
            for offset in range(block.size):
                mapping[block.a + offset] = block.b + offset
        return mapping

    @staticmethod
    def _normalise_for_alignment(text):
        return "".join(
            char
            for char in str(text)
            if not char.isspace() and not unicodedata.category(char).startswith("P")
        ).casefold()

    def _fits_subtitle(self, text, duration):
        return self._text_length(text) <= self.max_chars and duration <= self.max_duration

    def _warn_if_fast(self, text, duration):
        if duration > 0 and self._text_length(text) / duration > self.max_cps:
            self.logger.warning("Subtitle exceeds max CPS: %s", text)

    def _segment_by_alignment(self, items):
        segments, current, start = [], [], None
        for item in items:
            start = item.start_time if start is None else start
            current.append(item)
            text = "".join(entry.text for entry in current)
            if not self._fits_subtitle(text, item.end_time - start):
                segments.append(self._make_segment(current, start))
                current, start = [], None
        if current:
            segments.append(self._make_segment(current, start))
        return segments

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
