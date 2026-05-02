import json
import logging
import os
import traceback
import wave
from dataclasses import dataclass, field
from typing import Optional

from google.api_core.client_options import ClientOptions
from google.cloud.speech_v2 import SpeechClient
from google.oauth2 import service_account
from google.cloud.speech_v2.types import (
    ExplicitDecodingConfig,
    PhraseSet,
    RecognitionConfig,
    RecognitionFeatures,
    RecognizeRequest,
    SpeechAdaptation,
)

from utils.app_config import AppConfig
from utils.env_loader import load_env_variables


@dataclass
class GoogleSttClient:
    speech_client: SpeechClient
    project_id: str
    location: str
    phrases: tuple[str, ...] = field(default_factory=tuple)
    boost: float = 0.0


def _load_phrase_set(file_path: str) -> tuple[str, ...]:
    """専門用語のフレーズセットファイルを読み込む"""
    if not file_path or not os.path.exists(file_path):
        return ()
    try:
        with open(file_path, encoding='utf-8') as f:
            phrases = [
                line.strip()
                for line in f
                if line.strip() and not line.lstrip().startswith('#')
            ]
        logging.info(f'フレーズセット読込: {len(phrases)}件 ({file_path})')
        return tuple(phrases)
    except OSError as e:
        logging.error(f'フレーズセット読込エラー: {e}')
        return ()


def _load_service_account_credentials(value: str) -> service_account.Credentials:
    stripped = value.strip()
    if stripped.startswith('{'):
        info = json.loads(stripped)
        return service_account.Credentials.from_service_account_info(info)
    return service_account.Credentials.from_service_account_file(stripped)


def setup_google_stt_client(config: Optional[AppConfig] = None) -> GoogleSttClient:
    env_vars = load_env_variables()

    credentials_value = env_vars.get('GOOGLE_CREDENTIALS_JSON')
    if not credentials_value:
        raise ValueError('GOOGLE_CREDENTIALS_JSONが未設定です')

    project_id = env_vars.get('GOOGLE_PROJECT_ID')
    if not project_id:
        raise ValueError('GOOGLE_PROJECT_IDが未設定です')

    location = env_vars.get('GOOGLE_LOCATION', 'asia-northeast1')

    credentials = _load_service_account_credentials(credentials_value)

    speech_client = SpeechClient(
        credentials=credentials,
        client_options=ClientOptions(
            api_endpoint=f'{location}-speech.googleapis.com',
        ),
    )

    phrases: tuple[str, ...] = ()
    boost = 0.0
    if config is not None:
        phrases = _load_phrase_set(config.google_stt_phrase_set_file)
        boost = config.google_stt_phrase_boost

    return GoogleSttClient(
        speech_client=speech_client,
        project_id=project_id,
        location=location,
        phrases=phrases,
        boost=boost,
    )


def validate_audio_file(file_path: str) -> tuple[bool, Optional[str]]:
    if not file_path:
        return False, '音声ファイルパスが未指定です'

    if not os.path.exists(file_path):
        return False, f'音声ファイルが存在しません: {file_path}'

    if os.path.getsize(file_path) == 0:
        return False, '音声ファイルサイズが0バイトです'

    return True, None


def _build_adaptation(phrases: tuple[str, ...], boost: float) -> Optional[SpeechAdaptation]:
    if not phrases:
        return None
    phrase_set = PhraseSet(
        phrases=[PhraseSet.Phrase(value=word, boost=boost) for word in phrases]
    )
    return SpeechAdaptation(
        phrase_sets=[
            SpeechAdaptation.AdaptationPhraseSet(inline_phrase_set=phrase_set)
        ]
    )


def _build_recognition_config(
        config: AppConfig,
        client: GoogleSttClient,
        sample_rate: int,
        channels: int,
) -> RecognitionConfig:
    return RecognitionConfig(
        explicit_decoding_config=ExplicitDecodingConfig(
            encoding=ExplicitDecodingConfig.AudioEncoding.LINEAR16,
            sample_rate_hertz=sample_rate,
            audio_channel_count=channels,
        ),
        language_codes=config.google_stt_language,
        model=config.google_stt_model,
        adaptation=_build_adaptation(client.phrases, client.boost),
        features=RecognitionFeatures(
            enable_automatic_punctuation=config.google_stt_enable_automatic_punctuation,
        ),
    )


def transcribe_pcm(
        audio_bytes: bytes,
        sample_rate: int,
        config: AppConfig,
        client: GoogleSttClient,
        channels: int = 1,
) -> Optional[str]:
    """PCM(LINEAR16)のバイト列を文字起こしする"""
    if not audio_bytes:
        logging.warning('音声データが空です')
        return None

    try:
        recognizer = (
            f'projects/{client.project_id}/locations/{client.location}/recognizers/_'
        )
        recognition_config = _build_recognition_config(
            config, client, sample_rate, channels
        )
        request = RecognizeRequest(
            recognizer=recognizer,
            config=recognition_config,
            content=audio_bytes,
        )

        logging.info(f'文字起こしリクエスト送信: {len(audio_bytes)} bytes')
        response = client.speech_client.recognize(request=request)

        transcripts = [
            result.alternatives[0].transcript
            for result in response.results
            if result.alternatives
        ]
        text_result = ''.join(transcripts)

        if len(text_result) == 0:
            logging.warning('文字起こし結果が空です')
            return ''

        logging.info(f'文字起こし完了: {len(text_result)}文字')
        return text_result

    except Exception as e:
        logging.error(f'文字起こしエラー: {str(e)}')
        logging.error(f'エラーのタイプ: {type(e).__name__}')
        logging.debug(f'詳細: {traceback.format_exc()}')
        return None


def _read_pcm_from_wav(file_path: str) -> tuple[bytes, int, int]:
    with wave.open(file_path, 'rb') as wf:
        sample_rate = wf.getframerate()
        channels = wf.getnchannels()
        pcm = wf.readframes(wf.getnframes())
    return pcm, sample_rate, channels


def transcribe_audio(
        audio_file_path: str,
        config: AppConfig,
        client: GoogleSttClient
) -> Optional[str]:
    """保存済み音声ファイルを読み込んで文字起こしする"""
    is_valid, error_msg = validate_audio_file(audio_file_path)
    if not is_valid:
        logging.warning(error_msg) if '未指定' in str(error_msg) else logging.error(error_msg)
        return None

    try:
        pcm, sample_rate, channels = _read_pcm_from_wav(audio_file_path)
        logging.info(f'ファイル読み込み完了: {len(pcm)} bytes, {sample_rate}Hz, {channels}ch')
    except FileNotFoundError as e:
        logging.error(f'ファイルが見つかりません: {str(e)}')
        return None
    except PermissionError as e:
        logging.error(f'ファイルアクセス権限エラー: {str(e)}')
        return None
    except (OSError, wave.Error) as e:
        logging.error(f'音声ファイル読込エラー: {str(e)}')
        return None

    return transcribe_pcm(pcm, sample_rate, config, client, channels)
