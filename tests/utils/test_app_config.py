import os
from unittest.mock import patch

from tests.conftest import dict_to_app_config


class TestAppConfigAudio:
    """音声設定プロパティのテストクラス"""

    def test_audio_defaults(self):
        """正常系: デフォルト値"""
        config = dict_to_app_config({})
        assert config.audio_sample_rate == 16000
        assert config.audio_channels == 1
        assert config.audio_chunk == 1024

    def test_audio_custom_values(self):
        """正常系: カスタム値"""
        config = dict_to_app_config({'AUDIO': {'SAMPLE_RATE': '44100', 'CHANNELS': '2', 'CHUNK': '2048'}})
        assert config.audio_sample_rate == 44100
        assert config.audio_channels == 2
        assert config.audio_chunk == 2048


class TestAppConfigPaths:
    """パス設定プロパティのテストクラス"""

    def test_temp_dir_default(self):
        """正常系: デフォルト値"""
        assert dict_to_app_config({}).temp_dir == 'temp'

    def test_temp_dir_custom(self):
        """正常系: カスタム値"""
        config = dict_to_app_config({'PATHS': {'TEMP_DIR': '/custom/temp'}})
        assert config.temp_dir == '/custom/temp'

    def test_cleanup_minutes_default(self):
        """正常系: デフォルト値"""
        assert dict_to_app_config({}).cleanup_minutes == 30

    def test_replacements_file_configured(self):
        """正常系: 絶対パスが設定された場合はそのまま返す"""
        abs_path = os.path.abspath('/custom/replacements.txt')
        config = dict_to_app_config({'PATHS': {'REPLACEMENTS_FILE': abs_path}})
        assert config.replacements_file == abs_path

    def test_replacements_file_default_dev(self):
        """正常系: 未設定時はdata/replacements.txtを返す"""
        config = dict_to_app_config({})
        with patch('sys.frozen', False, create=True):
            path = config.replacements_file
        assert path.endswith('replacements.txt')
        assert 'data' in path

    def test_replacements_file_default_frozen(self):
        """正常系: 実行ファイル実行時のデフォルトパス"""
        import os
        config = dict_to_app_config({})
        with patch('sys.frozen', True, create=True), patch('sys._MEIPASS', '/mocked/meipass', create=True):
            path = config.replacements_file
        assert path == os.path.join('/mocked/meipass', 'replacements.txt')


class TestAppConfigFormatting:
    """フォーマット設定プロパティのテストクラス"""

    def test_use_punctuation_default(self):
        """正常系: デフォルト値"""
        assert dict_to_app_config({}).use_punctuation is False

    def test_use_punctuation_custom(self):
        """正常系: カスタム値"""
        config = dict_to_app_config({'FORMATTING': {'USE_PUNCTUATION': 'True'}})
        assert config.use_punctuation is True

    def test_use_punctuation_setter(self):
        """正常系: setterで変更可能"""
        config = dict_to_app_config({'FORMATTING': {'USE_PUNCTUATION': 'False'}})
        config.use_punctuation = True
        assert config.use_punctuation is True

    def test_use_comma_setter(self):
        """正常系: use_commaのsetter"""
        config = dict_to_app_config({'FORMATTING': {'USE_COMMA': 'False'}})
        config.use_comma = True
        assert config.use_comma is True


class TestAppConfigKeys:
    """キー設定プロパティのテストクラス"""

    def test_keys_defaults(self):
        """正常系: デフォルト値"""
        config = dict_to_app_config({})
        assert config.toggle_recording_key == 'pause'
        assert config.exit_app_key == 'esc'
        assert config.reload_audio_key == 'f8'
        assert config.toggle_punctuation_key == 'f9'

    def test_keys_custom(self):
        """正常系: カスタム値"""
        config = dict_to_app_config({'KEYS': {
            'TOGGLE_RECORDING': 'f1',
            'EXIT_APP': 'f2',
        }})
        assert config.toggle_recording_key == 'f1'
        assert config.exit_app_key == 'f2'


class TestAppConfigRecording:
    """録音設定プロパティのテストクラス"""

    def test_auto_stop_timer_default(self):
        """正常系: デフォルト値"""
        assert dict_to_app_config({}).auto_stop_timer == 60

    def test_auto_stop_timer_custom(self):
        """正常系: カスタム値"""
        config = dict_to_app_config({'RECORDING': {'AUTO_STOP_TIMER': '120'}})
        assert config.auto_stop_timer == 120


class TestAppConfigGoogleStt:
    """Google STT設定プロパティのテストクラス"""

    def test_google_stt_defaults(self):
        """正常系: デフォルト値"""
        config = dict_to_app_config({})
        assert config.google_stt_model == 'chirp_3'
        assert config.google_stt_language == ['ja-JP', 'en-US']

    def test_google_stt_custom(self):
        """正常系: カスタム値"""
        config = dict_to_app_config({'GOOGLE_STT': {'MODEL': 'chirp_2', 'LANGUAGE': 'en-US'}})
        assert config.google_stt_model == 'chirp_2'
        assert config.google_stt_language == ['en-US']

    def test_google_stt_multiple_languages(self):
        """正常系: カンマ区切りで複数言語"""
        config = dict_to_app_config({'GOOGLE_STT': {'LANGUAGE': 'ja-JP, en-US'}})
        assert config.google_stt_language == ['ja-JP', 'en-US']


class TestAppConfigRawConfig:
    """内部_configプロパティのテストクラス"""

    def test_raw_config_returns_configparser(self):
        """正常系: 内部_configはConfigParserオブジェクト"""
        import configparser
        config = dict_to_app_config({'AUDIO': {'SAMPLE_RATE': '16000'}})
        assert isinstance(config._config, configparser.ConfigParser)
        assert config._config['AUDIO']['SAMPLE_RATE'] == '16000'
