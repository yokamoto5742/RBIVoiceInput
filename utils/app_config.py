import configparser
import os
import sys

from utils.config_manager import get_config_value


class AppConfig:
    """設定ファイルへの型安全なアクセスを提供するファサード(窓口)"""

    def __init__(self, config: configparser.ConfigParser):
        self._config = config

    @property
    def raw_config(self) -> configparser.ConfigParser:
        """内部の ConfigParser インスタンスを返す"""
        return self._config

    # --- AUDIO ---
    @property
    def audio_sample_rate(self) -> int:
        return get_config_value(self._config, 'AUDIO', 'SAMPLE_RATE', 16000)

    @property
    def audio_channels(self) -> int:
        return get_config_value(self._config, 'AUDIO', 'CHANNELS', 1)

    @property
    def audio_chunk(self) -> int:
        return get_config_value(self._config, 'AUDIO', 'CHUNK', 1024)

    # --- PATHS ---
    @property
    def temp_dir(self) -> str:
        return get_config_value(self._config, 'PATHS', 'TEMP_DIR', 'temp')

    @property
    def cleanup_minutes(self) -> int:
        return get_config_value(self._config, 'PATHS', 'CLEANUP_MINUTES', 30)

    @property
    def replacements_file(self) -> str:
        """置換ルールファイルのパスを返す。未設定時はデフォルトパスを返す"""
        configured = get_config_value(self._config, 'PATHS', 'REPLACEMENTS_FILE', '')
        if not configured:
            return os.path.join(self._default_data_dir(), 'replacements.txt')
        if os.path.isabs(configured):
            return configured
        return os.path.join(self._default_data_dir(), configured)

    # --- GOOGLE_STT ---
    @property
    def google_stt_model(self) -> str:
        return get_config_value(self._config, 'GOOGLE_STT', 'MODEL', 'chirp_3')

    @property
    def google_stt_language(self) -> list[str]:
        """認識対象の言語コード一覧。カンマ区切りで複数指定可"""
        raw = get_config_value(self._config, 'GOOGLE_STT', 'LANGUAGE', 'ja-JP,en-US')
        codes = [code.strip() for code in str(raw).split(',') if code.strip()]
        return codes if codes else ['ja-JP', 'en-US']

    @property
    def google_stt_phrase_set_file(self) -> str:
        """専門用語ファイル名。空文字なら無効"""
        configured = get_config_value(self._config, 'GOOGLE_STT', 'PHRASE_SET_FILE', '')
        if not configured:
            return ''
        if os.path.isabs(configured):
            return configured
        return os.path.join(self._default_data_dir(), configured)

    @property
    def google_stt_phrase_boost(self) -> float:
        return get_config_value(self._config, 'GOOGLE_STT', 'PHRASE_BOOST', 10.0)

    @property
    def google_stt_enable_automatic_punctuation(self) -> bool:
        """Google STT に句読点を自動挿入させるか"""
        return get_config_value(self._config, 'GOOGLE_STT', 'ENABLE_AUTOMATIC_PUNCTUATION', False)

    def _default_data_dir(self) -> str:
        if getattr(sys, 'frozen', False):
            return getattr(sys, '_MEIPASS', os.path.dirname(__file__))
        return os.path.normpath(os.path.join(os.path.dirname(__file__), '..', 'data'))

    # --- FORMATTING ---
    @property
    def use_punctuation(self) -> bool:
        return get_config_value(self._config, 'FORMATTING', 'USE_PUNCTUATION', False)

    @use_punctuation.setter
    def use_punctuation(self, value: bool) -> None:
        self._config['FORMATTING']['USE_PUNCTUATION'] = str(value)

    @property
    def use_comma(self) -> bool:
        return get_config_value(self._config, 'FORMATTING', 'USE_COMMA', False)

    @use_comma.setter
    def use_comma(self, value: bool) -> None:
        self._config['FORMATTING']['USE_COMMA'] = str(value)

    # --- KEYS ---
    @property
    def toggle_recording_key(self) -> str:
        return get_config_value(self._config, 'KEYS', 'TOGGLE_RECORDING', 'pause')

    @property
    def exit_app_key(self) -> str:
        return get_config_value(self._config, 'KEYS', 'EXIT_APP', 'esc')

    @property
    def reload_audio_key(self) -> str:
        return get_config_value(self._config, 'KEYS', 'RELOAD_AUDIO', 'f8')

    @property
    def toggle_punctuation_key(self) -> str:
        return get_config_value(self._config, 'KEYS', 'TOGGLE_PUNCTUATION', 'f9')

    # --- RECORDING ---
    @property
    def auto_stop_timer(self) -> int:
        return get_config_value(self._config, 'RECORDING', 'AUTO_STOP_TIMER', 60)

    # --- WINDOW ---
    @property
    def window_width(self) -> int:
        return get_config_value(self._config, 'WINDOW', 'WIDTH', 300)

    @property
    def window_height(self) -> int:
        return get_config_value(self._config, 'WINDOW', 'HEIGHT', 450)

    # --- GOOGLE_DOCS ---
    @property
    def google_docs_url(self) -> str:
        return get_config_value(self._config, 'GOOGLE_DOCS', 'DOCS_URL', '')

    @property
    def google_docs_placeholder_text(self) -> str:
        return get_config_value(self._config, 'GOOGLE_DOCS', 'PLACEHOLDER_TEXT', '音声入力中…(60秒以内)')

    @property
    def google_docs_placeholder_wait_timeout(self) -> int:
        return get_config_value(self._config, 'GOOGLE_DOCS', 'PLACEHOLDER_WAIT_TIMEOUT', 10)

    # --- OPTIONS ---
    @property
    def start_minimized(self) -> bool:
        return get_config_value(self._config, 'OPTIONS', 'START_MINIMIZED', True)

    # --- EDITOR ---
    @property
    def editor_width(self) -> int:
        return get_config_value(self._config, 'EDITOR', 'WIDTH', 400)

    @property
    def editor_height(self) -> int:
        return get_config_value(self._config, 'EDITOR', 'HEIGHT', 700)

    @property
    def editor_font_name(self) -> str:
        return get_config_value(self._config, 'EDITOR', 'FONT_NAME', 'MS Gothic')

    @property
    def editor_font_size(self) -> int:
        return get_config_value(self._config, 'EDITOR', 'FONT_SIZE', 12)
