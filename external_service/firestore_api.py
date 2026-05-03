import json
import logging
from typing import Optional

from google.cloud import firestore
from google.oauth2 import service_account

from utils.app_config import AppConfig
from utils.env_loader import load_env_variables


def _load_service_account_credentials(value: str) -> service_account.Credentials:
    stripped = value.strip()
    if stripped.startswith('{'):
        info = json.loads(stripped)
        return service_account.Credentials.from_service_account_info(info)
    return service_account.Credentials.from_service_account_file(stripped)


def setup_firestore_client(config: AppConfig) -> Optional[firestore.Client]:
    """サービスアカウントで Firestore クライアントを初期化する"""
    project_id = config.firestore_project_id
    if not project_id:
        logging.warning('FIRESTORE.PROJECT_ID が未設定のため Firestore を無効化します')
        return None

    env_vars = load_env_variables()
    credentials_value = env_vars.get('GOOGLE_CREDENTIALS_JSON')
    if not credentials_value:
        raise ValueError('GOOGLE_CREDENTIALS_JSONが未設定です')

    credentials = _load_service_account_credentials(credentials_value)
    return firestore.Client(project=project_id, credentials=credentials)
