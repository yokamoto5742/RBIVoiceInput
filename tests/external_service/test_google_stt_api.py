from typing import cast
from unittest.mock import MagicMock, Mock, patch

import pytest

from external_service.google_stt_api import (
    GoogleSttClient,
    _build_adaptation,
    _load_phrase_set,
    setup_google_stt_client,
    transcribe_audio,
    transcribe_pcm,
    validate_audio_file,
)
from tests.conftest import dict_to_app_config

_BASE_CONFIG = {
    'GOOGLE_STT': {
        'MODEL': 'chirp_3',
        'LANGUAGE': 'ja-JP',
        'PHRASE_SET_FILE': '',
        'PHRASE_BOOST': '10.0',
    }
}


class TestSetupGoogleSttClient:

    @patch('external_service.google_stt_api.SpeechClient')
    @patch('external_service.google_stt_api._load_service_account_credentials')
    @patch('external_service.google_stt_api.load_env_variables')
    def test_setup_client_success(self, mock_load_env, mock_load_creds, mock_speech_client):
        """正常系: 必要な環境変数が設定されている場合"""
        mock_load_env.return_value = {
            'GOOGLE_CREDENTIALS_JSON': '/path/to/key.json',
            'GOOGLE_PROJECT_ID': 'my-project',
            'GOOGLE_LOCATION': 'asia-northeast1',
        }
        mock_load_creds.return_value = Mock()
        mock_client_instance = Mock()
        mock_speech_client.return_value = mock_client_instance

        result = setup_google_stt_client()

        assert isinstance(result, GoogleSttClient)
        assert result.speech_client == mock_client_instance
        assert result.project_id == 'my-project'
        assert result.location == 'asia-northeast1'
        assert result.phrases == ()
        assert result.boost == 0.0

    @patch('external_service.google_stt_api.SpeechClient')
    @patch('external_service.google_stt_api._load_service_account_credentials')
    @patch('external_service.google_stt_api.load_env_variables')
    def test_setup_client_default_location(self, mock_load_env, mock_load_creds, mock_speech_client):
        """正常系: GOOGLE_LOCATIONが未設定の場合はusを使用"""
        mock_load_env.return_value = {
            'GOOGLE_CREDENTIALS_JSON': '/path/to/key.json',
            'GOOGLE_PROJECT_ID': 'my-project',
        }
        mock_load_creds.return_value = Mock()
        mock_speech_client.return_value = Mock()

        result = setup_google_stt_client()

        assert result.location == 'asia-northeast1'

    @patch('external_service.google_stt_api._load_phrase_set')
    @patch('external_service.google_stt_api.SpeechClient')
    @patch('external_service.google_stt_api._load_service_account_credentials')
    @patch('external_service.google_stt_api.load_env_variables')
    def test_setup_client_with_config_loads_phrases(
            self, mock_load_env, mock_load_creds, mock_speech_client, mock_load_phrase
    ):
        """正常系: config指定時はフレーズセットとboostを読み込む"""
        mock_load_env.return_value = {
            'GOOGLE_CREDENTIALS_JSON': '/path/to/key.json',
            'GOOGLE_PROJECT_ID': 'my-project',
        }
        mock_load_creds.return_value = Mock()
        mock_speech_client.return_value = Mock()
        mock_load_phrase.return_value = ('網膜剥離', '黄斑変性')

        config = dict_to_app_config({
            'GOOGLE_STT': {
                'PHRASE_SET_FILE': 'dummy.txt',
                'PHRASE_BOOST': '15.0',
            }
        })
        result = setup_google_stt_client(config)

        assert result.phrases == ('網膜剥離', '黄斑変性')
        assert result.boost == 15.0

    @patch('external_service.google_stt_api.load_env_variables')
    def test_setup_client_no_credentials(self, mock_load_env):
        """異常系: GOOGLE_CREDENTIALS_JSONが未設定"""
        mock_load_env.return_value = {'GOOGLE_PROJECT_ID': 'my-project'}

        with pytest.raises(ValueError, match='GOOGLE_CREDENTIALS_JSONが未設定です'):
            setup_google_stt_client()

    @patch('external_service.google_stt_api.load_env_variables')
    def test_setup_client_no_project_id(self, mock_load_env):
        """異常系: GOOGLE_PROJECT_IDが未設定"""
        mock_load_env.return_value = {
            'GOOGLE_CREDENTIALS_JSON': '/path/to/key.json',
        }

        with pytest.raises(ValueError, match='GOOGLE_PROJECT_IDが未設定です'):
            setup_google_stt_client()


class TestLoadPhraseSet:

    def test_empty_path(self):
        assert _load_phrase_set('') == ()

    def test_missing_file(self, tmp_path):
        assert _load_phrase_set(str(tmp_path / 'nope.txt')) == ()

    def test_reads_phrases_skipping_comments_and_blank(self, tmp_path):
        path = tmp_path / 'p.txt'
        path.write_text(
            '# 眼科用語\n'
            '網膜剥離\n'
            '\n'
            '  黄斑変性  \n'
            '# コメント\n'
            '硝子体出血\n',
            encoding='utf-8',
        )
        assert _load_phrase_set(str(path)) == (
            '網膜剥離', '黄斑変性', '硝子体出血',
        )


class TestBuildAdaptation:

    def test_empty_phrases_returns_none(self):
        assert _build_adaptation((), 10.0) is None

    def test_builds_inline_phrase_set(self):
        adaptation = _build_adaptation(('網膜剥離', '黄斑変性'), 12.0)
        assert adaptation is not None
        assert len(adaptation.phrase_sets) == 1
        inline = adaptation.phrase_sets[0].inline_phrase_set
        assert [p.value for p in inline.phrases] == ['網膜剥離', '黄斑変性']
        assert all(p.boost == 12.0 for p in inline.phrases)


class TestValidateAudioFile:

    def test_validate_empty_path(self):
        is_valid, error_msg = validate_audio_file('')
        assert is_valid is False
        assert error_msg == '音声ファイルパスが未指定です'

    @patch('external_service.google_stt_api.os.path.exists')
    def test_validate_file_not_exists(self, mock_exists):
        mock_exists.return_value = False
        file_path = '/test/path/audio.wav'
        is_valid, error_msg = validate_audio_file(file_path)
        assert is_valid is False
        assert error_msg == f'音声ファイルが存在しません: {file_path}'

    @patch('external_service.google_stt_api.os.path.getsize')
    @patch('external_service.google_stt_api.os.path.exists')
    def test_validate_zero_size_file(self, mock_exists, mock_getsize):
        mock_exists.return_value = True
        mock_getsize.return_value = 0
        is_valid, error_msg = validate_audio_file('/test/audio.wav')
        assert is_valid is False
        assert error_msg == '音声ファイルサイズが0バイトです'

    @patch('external_service.google_stt_api.os.path.getsize')
    @patch('external_service.google_stt_api.os.path.exists')
    def test_validate_success(self, mock_exists, mock_getsize):
        mock_exists.return_value = True
        mock_getsize.return_value = 1024
        is_valid, error_msg = validate_audio_file('/test/audio.wav')
        assert is_valid is True
        assert error_msg is None


def _make_client(
        project_id: str = 'my-project',
        location: str = 'global',
        phrases: tuple[str, ...] = (),
        boost: float = 0.0,
) -> GoogleSttClient:
    return GoogleSttClient(
        speech_client=Mock(),
        project_id=project_id,
        location=location,
        phrases=phrases,
        boost=boost,
    )


class TestTranscribePcm:

    def setup_method(self):
        self.mock_config = dict_to_app_config(_BASE_CONFIG)
        self.mock_client = _make_client()

    def test_empty_bytes(self):
        assert transcribe_pcm(b'', 16000, self.mock_config, self.mock_client) is None

    def test_success(self):
        mock_alternative = Mock()
        mock_alternative.transcript = '文字起こし結果'
        mock_result = Mock()
        mock_result.alternatives = [mock_alternative]
        mock_response = Mock()
        mock_response.results = [mock_result]
        speech_client = cast(MagicMock, self.mock_client.speech_client)
        speech_client.recognize.return_value = mock_response

        result = transcribe_pcm(b'pcm_bytes', 16000, self.mock_config, self.mock_client)

        assert result == '文字起こし結果'
        speech_client.recognize.assert_called_once()

    def test_multiple_results_concatenated(self):
        def _make_result(text: str) -> Mock:
            alt = Mock()
            alt.transcript = text
            r = Mock()
            r.alternatives = [alt]
            return r

        mock_response = Mock()
        mock_response.results = [_make_result('こんにちは'), _make_result('世界')]
        speech_client = cast(MagicMock, self.mock_client.speech_client)
        speech_client.recognize.return_value = mock_response

        result = transcribe_pcm(b'pcm', 16000, self.mock_config, self.mock_client)
        assert result == 'こんにちは世界'

    def test_empty_results_returns_empty_string(self):
        mock_response = Mock()
        mock_response.results = []
        speech_client = cast(MagicMock, self.mock_client.speech_client)
        speech_client.recognize.return_value = mock_response

        result = transcribe_pcm(b'pcm', 16000, self.mock_config, self.mock_client)
        assert result == ''

    def test_recognizer_path(self):
        mock_response = Mock()
        mock_response.results = []
        client = _make_client(project_id='test-proj', location='asia-northeast1')
        speech_client = cast(MagicMock, client.speech_client)
        speech_client.recognize.return_value = mock_response

        transcribe_pcm(b'pcm', 16000, self.mock_config, client)

        request = speech_client.recognize.call_args.kwargs['request']
        assert request.recognizer == 'projects/test-proj/locations/asia-northeast1/recognizers/_'

    def test_explicit_decoding_config_is_used(self):
        mock_response = Mock()
        mock_response.results = []
        speech_client = cast(MagicMock, self.mock_client.speech_client)
        speech_client.recognize.return_value = mock_response

        transcribe_pcm(b'pcm', 16000, self.mock_config, self.mock_client, channels=1)

        request = speech_client.recognize.call_args.kwargs['request']
        assert request.config.explicit_decoding_config.sample_rate_hertz == 16000
        assert request.config.explicit_decoding_config.audio_channel_count == 1

    def test_adaptation_is_included_when_phrases_present(self):
        mock_response = Mock()
        mock_response.results = []
        client = _make_client(phrases=('網膜剥離',), boost=10.0)
        speech_client = cast(MagicMock, client.speech_client)
        speech_client.recognize.return_value = mock_response

        transcribe_pcm(b'pcm', 16000, self.mock_config, client)

        request = speech_client.recognize.call_args.kwargs['request']
        inline = request.config.adaptation.phrase_sets[0].inline_phrase_set
        assert [p.value for p in inline.phrases] == ['網膜剥離']

    def test_api_exception_returns_none(self):
        speech_client = cast(MagicMock, self.mock_client.speech_client)
        speech_client.recognize.side_effect = Exception('API エラー')
        result = transcribe_pcm(b'pcm', 16000, self.mock_config, self.mock_client)
        assert result is None


class TestTranscribeAudio:
    """WAVファイル経由（F8再実行）での文字起こし"""

    def setup_method(self):
        self.mock_config = dict_to_app_config(_BASE_CONFIG)
        self.mock_client = _make_client()

    def test_empty_file_path(self):
        assert transcribe_audio('', self.mock_config, self.mock_client) is None

    @patch('external_service.google_stt_api.os.path.exists')
    def test_file_not_exists(self, mock_exists):
        mock_exists.return_value = False
        assert transcribe_audio('/nope.wav', self.mock_config, self.mock_client) is None

    @patch('external_service.google_stt_api.os.path.getsize')
    @patch('external_service.google_stt_api.os.path.exists')
    def test_zero_size_file(self, mock_exists, mock_getsize):
        mock_exists.return_value = True
        mock_getsize.return_value = 0
        assert transcribe_audio('/empty.wav', self.mock_config, self.mock_client) is None

    @patch('external_service.google_stt_api.transcribe_pcm')
    @patch('external_service.google_stt_api._read_pcm_from_wav')
    @patch('external_service.google_stt_api.os.path.getsize')
    @patch('external_service.google_stt_api.os.path.exists')
    def test_delegates_to_transcribe_pcm(
            self, mock_exists, mock_getsize, mock_read, mock_transcribe
    ):
        mock_exists.return_value = True
        mock_getsize.return_value = 1024
        mock_read.return_value = (b'pcm_bytes', 16000, 1)
        mock_transcribe.return_value = '結果'

        result = transcribe_audio('/test/audio.wav', self.mock_config, self.mock_client)

        assert result == '結果'
        mock_transcribe.assert_called_once_with(
            b'pcm_bytes', 16000, self.mock_config, self.mock_client, 1
        )

    @patch('external_service.google_stt_api._read_pcm_from_wav')
    @patch('external_service.google_stt_api.os.path.getsize')
    @patch('external_service.google_stt_api.os.path.exists')
    def test_read_error_returns_none(
            self, mock_exists, mock_getsize, mock_read
    ):
        mock_exists.return_value = True
        mock_getsize.return_value = 1024
        mock_read.side_effect = OSError('broken')

        assert transcribe_audio('/bad.wav', self.mock_config, self.mock_client) is None
