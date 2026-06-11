"""Test that Arabic digit sequences get Japanese phonetic readings."""

from typing import List, Tuple

from strange_uta_game.backend.infrastructure.parsers.ruby_analyzer import (
    _arabic_to_kanji,
    _replace_digits_with_kanji,
    _map_results_to_original,
    RubyResult,
    KanaDistributingAnalyzer,
)


class TestArabicToKanji:
    def test_zero(self):
        assert _arabic_to_kanji("0") == "\u96f6"

    def test_single_digits(self):
        assert _arabic_to_kanji("1") == "\u4e00"
        assert _arabic_to_kanji("5") == "\u4e94"
        assert _arabic_to_kanji("9") == "\u4e5d"

    def test_tens(self):
        assert _arabic_to_kanji("10") == "\u5341"
        assert _arabic_to_kanji("20") == "\u4e8c\u5341"
        assert _arabic_to_kanji("99") == "\u4e5d\u5341\u4e5d"

    def test_hundreds(self):
        assert _arabic_to_kanji("100") == "\u767e"
        assert _arabic_to_kanji("200") == "\u4e8c\u767e"
        assert _arabic_to_kanji("999") == "\u4e5d\u767e\u4e5d\u5341\u4e5d"

    def test_thousands(self):
        assert _arabic_to_kanji("1000") == "\u5343"
        assert _arabic_to_kanji("2024") == "\u4e8c\u5343\u4e8c\u5341\u56db"

    def test_man(self):
        assert _arabic_to_kanji("10000") == "\u4e00\u4e07"
        assert _arabic_to_kanji("12345") == (
            "\u4e00\u4e07\u4e8c\u5343\u4e09\u767e\u56db\u5341\u4e94"
        )


class TestReplaceDigitsWithKanji:
    def test_no_digits(self):
        text = "\u3053\u3093\u306b\u3061\u306f"  # こんにちは
        mod, reps = _replace_digits_with_kanji(text)
        assert mod == text
        assert reps == []

    def test_single_number(self):
        text = "abc999xyz"
        mod, reps = _replace_digits_with_kanji(text)
        assert mod == "abc\u4e5d\u767e\u4e5d\u5341\u4e5dxyz"
        assert reps == [(3, 6, 3, 8)]  # orig(3,6), kanji(3,8) - 5 chars for kanji

    def test_multiple_numbers(self):
        text = "a12b34c"
        mod, reps = _replace_digits_with_kanji(text)
        # 12 → 十二 (2 chars), 34 → 三十四 (3 chars)
        assert mod == "a\u5341\u4e8cb\u4e09\u5341\u56dbc"
        assert len(reps) == 2
        assert reps[0] == (1, 3, 1, 3)  # orig(1,3), kanji "十二" at (1,3) in modified
        assert reps[1] == (4, 6, 4, 7)  # orig(4,6), kanji "三十四" at (4,7) in modified

    def test_number_with_japanese_suffix(self):
        text = "20\u65e5"  # 20日
        mod, reps = _replace_digits_with_kanji(text)
        assert mod == "\u4e8c\u5341\u65e5"  # 二十日
        assert reps == [(0, 2, 0, 2)]  # SAME length: 二十 = 2 chars, 20 = 2 chars

    def test_number_longer_in_kanji(self):
        text = "999\u5e74\u524d"  # 999年前
        mod, reps = _replace_digits_with_kanji(text)
        assert mod == "\u4e5d\u767e\u4e5d\u5341\u4e5d\u5e74\u524d"  # 九百九十九年前
        assert reps == [(0, 3, 0, 5)]  # "999" (3 chars) → "九百九十九" (5 chars)


class TestMapResultsToOriginal:
    def _make_result(self, text, reading, start, end):
        return RubyResult(text=text, reading=reading, start_idx=start, end_idx=end)

    def test_no_replacements_unchanged(self):
        results = [self._make_result("a", "a", 0, 1)]
        mapped = _map_results_to_original(results, [], "a")
        assert len(mapped) == 1
        assert mapped[0].text == "a"

    def test_number_merged_from_multiple_kanji(self):
        """Analyzer splits kanji number into multiple results → merge to one."""
        # "999" → "九百九十九", analyzer returns 3 kanji results
        results = [
            self._make_result("\u4e5d\u767e", "kyuu1", 0, 2),  # 九百
            self._make_result("\u4e5d\u5341", "kyuu2", 2, 4),  # 九十
            self._make_result("\u4e5d", "kyuu3", 4, 5),  # 九
        ]
        replacements = [(0, 3, 0, 5)]  # orig(0,3), kanji(0,5)
        mapped = _map_results_to_original(results, replacements, "999")

        assert len(mapped) == 1
        assert mapped[0].text == "999"
        assert mapped[0].start_idx == 0
        assert mapped[0].end_idx == 3
        assert mapped[0].reading == "kyuu1kyuu2kyuu3"

    def test_number_merged_single_kanji_block(self):
        """Analyzer returns entire kanji number as one block → maps back."""
        results = [
            self._make_result("\u4e5d\u767e\u4e5d\u5341\u4e5d",
                              "kyuuhyakukyuujuukyuu", 0, 5),
        ]
        replacements = [(0, 3, 0, 5)]
        mapped = _map_results_to_original(results, replacements, "999")
        assert len(mapped) == 1
        assert mapped[0].text == "999"
        assert mapped[0].start_idx == 0
        assert mapped[0].end_idx == 3

    def test_japanese_suffix_indices_adjusted(self):
        """Results after a number replacement should have adjusted indices."""
        # "20日" → "二十日" (same length in this case, so no adjustment needed)
        # "999年前" → "九百九十九年前": "年" at kanji(5,6) → original(3,4)
        results = [
            self._make_result("\u4e5d\u767e\u4e5d\u5341\u4e5d", "reading", 0, 5),
            self._make_result("\u5e74", "nen", 5, 6),  # 年 at kanji index 5
            self._make_result("\u524d", "mae", 6, 7),  # 前 at kanji index 6
        ]
        replacements = [(0, 3, 0, 5)]  # "999" (3) → "九百九十九" (5)
        mapped = _map_results_to_original(results, replacements, "\u0039\u0039\u0039\u5e74\u524d")

        # Find non-number results
        others = [r for r in mapped if r.text.isdigit() is False or len(r.text) > 1]
        numbers = [r for r in mapped if r.text == "999"]

        assert len(numbers) == 1
        assert numbers[0].text == "999"
        assert numbers[0].start_idx == 0
        assert numbers[0].end_idx == 3

        # 年 should be at original index 3 (was at kanji index 5, offset=2)
        nen = [r for r in mapped if r.text == "\u5e74"]
        assert len(nen) == 1
        assert nen[0].start_idx == 3
        assert nen[0].end_idx == 4

        # 前 should be at original index 4
        mae = [r for r in mapped if r.text == "\u524d"]
        assert len(mae) == 1
        assert mae[0].start_idx == 4
        assert mae[0].end_idx == 5

    def test_same_length_replacement_no_index_shift(self):
        """When kanji is same length as digits, subsequent indices unchanged."""
        # "20日" → "二十日" (both "20" and "二十" are 2 chars)
        results = [
            self._make_result("\u4e8c\u5341\u65e5", "hatsuka", 0, 3),  # 二十日
        ]
        replacements = [(0, 2, 0, 2)]
        mapped = _map_results_to_original(results, replacements, "20\u65e5")

        # The analyzer merged 二十+日 into one result "二十日"
        # Since "二十日" spans kanji(0,3), and replacement is only (0,2)→(0,2),
        # "二十日" at (0,3) overlaps with replacement (0,2) but extends beyond (end=3 > kanji_end=2)
        # So it goes to other_results, and its indices are adjusted:
        # kanji_e(2) <= adj_start(0)? No. So no shift. But text is still "二十日".
        assert len(mapped) == 1


class TestKanaDistributingAnalyzerPreprocess:
    """Test that KanaDistributingAnalyzer.analyze() pre-processes numbers."""

    def test_analyze_converts_digits(self):
        """analyze() should convert digits to kanji, analyze, and map back."""
        # Mock analyzer that records what text it receives
        class MockAnalyzer(KanaDistributingAnalyzer):
            def __init__(self):
                self._pykakasi_conv = None
                self.received_text = None

            def _get_pairs(self, text):
                self.received_text = text
                # Return per-char self-ruby pairs
                return [(c, c) for c in text]

            def get_reading(self, text):
                return text

        analyzer = MockAnalyzer()
        results = analyzer.analyze("abc999")

        # Analyzer should have received kanji version
        assert analyzer.received_text == "abc\u4e5d\u767e\u4e5d\u5341\u4e5d"

        # Results should map back to original text positions
        assert len(results) == 4  # a, b, c, 999 (merged from 5 kanji chars)
        digits = [r for r in results if r.text == "999"]
        assert len(digits) == 1
        assert digits[0].start_idx == 3
        assert digits[0].end_idx == 6
