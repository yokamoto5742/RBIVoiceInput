import logging
import time
from unittest.mock import Mock, mock_open, patch

import pytest

from service.text_transformer import load_replacements, process_punctuation, replace_text


class TestProcessPunctuation:
    """句読点処理のテストクラス"""

    def test_process_punctuation_with_punctuation_true(self):
        """正常系: use_punctuation=Trueの場合、句読点をそのまま保持"""
        result = process_punctuation("これは。テスト、です。", True)
        assert result == "これは。テスト、です。"

    def test_process_punctuation_with_punctuation_false(self):
        """正常系: use_punctuation=Falseの場合、句読点を削除"""
        result = process_punctuation("これは。テスト、です。", False)
        assert result == "これはテストです"
        assert "。" not in result
        assert "、" not in result

    def test_process_punctuation_empty_text(self):
        """境界値: 空文字列"""
        assert process_punctuation("", False) == ""

    def test_process_punctuation_only_punctuation(self):
        """境界値: 句読点のみの文字列"""
        assert process_punctuation("。、。、", False) == ""

    def test_process_punctuation_no_punctuation(self):
        """正常系: 句読点を含まない文字列"""
        assert process_punctuation("これはテストです", False) == "これはテストです"

    def test_process_punctuation_multiple_types(self):
        """正常系: 複数の句読点を含む"""
        result = process_punctuation("一つ目。二つ目、三つ目。最後、です。", False)
        assert result == "一つ目二つ目三つ目最後です"

    def test_process_punctuation_none_text(self, caplog):
        """異常系: Noneが渡された場合"""
        caplog.set_level(logging.ERROR)
        result = process_punctuation(None, False)  # type: ignore
        assert result is None
        assert "句読点処理中にタイプエラー" in caplog.text

    @pytest.mark.parametrize("use_punctuation,input_text,expected", [
        (True, "テスト。文字、起こし", "テスト。文字、起こし"),
        (False, "テスト。文字、起こし", "テスト文字起こし"),
        (False, "。、。、", ""),
        (True, "", ""),
        (False, "句読点なし", "句読点なし"),
    ])
    def test_process_punctuation_parametrized(self, use_punctuation, input_text, expected):
        """パラメータ化テスト"""
        assert process_punctuation(input_text, use_punctuation) == expected


class TestLoadReplacements:
    """置換ルール読み込みのテストクラス"""

    def test_load_replacements_success(self):
        """正常系: 標準フォーマットの置換ルールファイル"""
        file_content = "旧文字列1,新文字列1\n旧文字列2,新文字列2\n\n有効行,値\n"
        with patch('builtins.open', mock_open(read_data=file_content)):
            result = load_replacements('test_replacements.txt')
        assert result == {'旧文字列1': '新文字列1', '旧文字列2': '新文字列2', '有効行': '値'}

    def test_load_replacements_with_whitespace(self):
        """正常系: 空白を含む置換ルール"""
        file_content = "  旧文字列  ,  新文字列  \n前後空白,削除される\n"
        with patch('builtins.open', mock_open(read_data=file_content)):
            result = load_replacements('test.txt')
        assert result == {'旧文字列': '新文字列', '前後空白': '削除される'}

    def test_load_replacements_empty_file(self):
        """境界値: 空ファイル"""
        with patch('builtins.open', mock_open()):
            result = load_replacements('empty.txt')
        assert result == {}

    def test_load_replacements_only_empty_lines(self):
        """境界値: 空行のみのファイル"""
        with patch('builtins.open', mock_open(read_data="\n\n   \n\t\n")):
            result = load_replacements('empty_lines.txt')
        assert result == {}

    def test_load_replacements_invalid_format_lines(self, caplog):
        """異常系: 無効なフォーマットの行を含む"""
        caplog.set_level(logging.ERROR)
        file_content = "正常,置換\n無効な行\nカンマなし\n正常2,置換2\n"
        with patch('builtins.open', mock_open(read_data=file_content)):
            result = load_replacements('invalid.txt')
        assert result == {'正常': '置換', '正常2': '置換2'}
        assert "無効な行があります" in caplog.text

    def test_load_replacements_file_not_found(self, caplog):
        """異常系: ファイルが存在しない"""
        caplog.set_level(logging.ERROR)
        with patch('builtins.open', side_effect=FileNotFoundError("File not found")):
            result = load_replacements('nonexistent.txt')
        assert result == {}
        assert "置換ファイルの読み込み中にエラーが発生しました" in caplog.text

    def test_load_replacements_permission_error(self, caplog):
        """異常系: ファイルアクセス権限エラー"""
        caplog.set_level(logging.ERROR)
        with patch('builtins.open', side_effect=PermissionError("Permission denied")):
            result = load_replacements('protected.txt')
        assert result == {}
        assert "置換ファイルの読み込み中にエラーが発生しました" in caplog.text

    def test_load_replacements_logging(self, caplog):
        """ログ出力の確認"""
        caplog.set_level(logging.INFO)
        file_content = "テスト1,結果1\nテスト2,結果2\n"
        with patch('builtins.open', mock_open(read_data=file_content)):
            result = load_replacements('test.txt')
        assert len(result) == 2
        assert "置換ルールの総数: 2" in caplog.text

    def test_load_replacements_unicode(self):
        """正常系: Unicode文字を含む置換ルール"""
        file_content = "😀,😊\n漢字,ひらがな\n한글,カタカナ\n"
        with patch('builtins.open', mock_open(read_data=file_content)):
            result = load_replacements('unicode.txt')
        assert result == {'😀': '😊', '漢字': 'ひらがな', '한글': 'カタカナ'}


class TestReplaceText:
    """テキスト置換のテストクラス"""

    def test_replace_text_single(self):
        """正常系: 単一の置換処理"""
        assert replace_text("これはテストです", {"テスト": "試験"}) == "これは試験です"

    def test_replace_text_multiple(self):
        """正常系: 複数の置換処理"""
        result = replace_text("テストとサンプルを実行", {"テスト": "試験", "サンプル": "例", "実行": "処理"})
        assert result == "試験と例を処理"

    def test_replace_text_multiple_occurrences(self):
        """正常系: 同じ単語の複数回置換"""
        assert replace_text("テストとテストのテスト", {"テスト": "試験"}) == "試験と試験の試験"

    def test_replace_text_no_matches(self):
        """正常系: 置換対象が見つからない場合"""
        assert replace_text("置換されないテキスト", {"存在しない": "置換"}) == "置換されないテキスト"

    def test_replace_text_empty_text(self):
        """境界値: 空文字列のテキスト"""
        assert replace_text("", {"何か": "置換"}) == ""

    def test_replace_text_none_text(self):
        """異常系: Noneのテキスト"""
        assert replace_text(None, {"何か": "置換"}) == ""  # type: ignore

    def test_replace_text_empty_replacements(self):
        """境界値: 空の置換辞書"""
        assert replace_text("置換ルールがないテキスト", {}) == "置換ルールがないテキスト"

    def test_replace_text_none_replacements(self):
        """異常系: Noneの置換辞書"""
        assert replace_text("テストテキスト", None) == "テストテキスト"  # type: ignore

    def test_replace_text_case_sensitive(self):
        """正常系: 大文字小文字の区別"""
        assert replace_text("testとTESTとTest", {"test": "試験"}) == "試験とTESTとTest"

    def test_replace_text_exception_handling(self, caplog):
        """異常系: 置換処理中の例外"""
        caplog.set_level(logging.ERROR)
        mock_replacements = Mock()
        mock_replacements.items.side_effect = Exception("置換処理エラー")
        result = replace_text("テストテキスト", mock_replacements)
        assert result == "テストテキスト"
        assert "テキスト置換中にエラーが発生" in caplog.text

    @pytest.mark.parametrize("text,replacements,expected", [
        ("", {}, ""),
        ("a", {"a": "b"}, "b"),
        ("abc", {"b": "x"}, "axc"),
        ("テスト", {"テスト": ""}, ""),
        ("前置換後", {"置換": "REPLACE"}, "前REPLACE後"),
    ])
    def test_replace_text_parametrized(self, text, replacements, expected):
        """パラメータ化テスト"""
        assert replace_text(text, replacements) == expected


class TestReplaceTextPerformance:
    """パフォーマンステスト"""

    def test_large_text_performance(self):
        """大きなテキストの置換処理性能"""
        large_text = "テスト " * 10000
        start_time = time.time()
        result = replace_text(large_text, {"テスト": "試験"})
        assert "試験" in result
        assert (time.time() - start_time) < 1.0

    def test_many_replacements_performance(self):
        """多数の置換ルールの処理性能"""
        text = "文字列1 文字列2 文字列3 " * 100
        replacements = {f"文字列{i}": f"置換{i}" for i in range(1, 101)}
        start_time = time.time()
        result = replace_text(text, replacements)
        assert "置換1" in result
        assert (time.time() - start_time) < 1.0
