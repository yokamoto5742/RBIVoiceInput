"""UI に表示する文字列を一元管理する"""

MSG_IDLE_STATUS = '{key}キーで音声入力開始/停止'
MSG_RECORDING = '音声入力中... ({key}キーで停止)'
MSG_TRANSCRIBING = 'テキスト出力中...'
MSG_AUDIO_FILE_PROCESSING = '音声ファイル処理中...'
MSG_PUNCTUATION_ON = '【現在句読点あり】'
MSG_PUNCTUATION_OFF = '【現在句読点なし】'
MSG_AUDIO_FILE_NOT_FOUND = '音声ファイルが見つかりません'

TITLE_ERROR = 'エラー'
TITLE_WARNING = '警告'


def idle_status(toggle_recording_key: str) -> str:
    """アイドル時のステータスラベル文字列を返す"""
    return MSG_IDLE_STATUS.format(key=toggle_recording_key)


def punctuation_status(use_punctuation: bool) -> str:
    """句読点の有無を示すラベル文字列を返す"""
    return MSG_PUNCTUATION_ON if use_punctuation else MSG_PUNCTUATION_OFF
