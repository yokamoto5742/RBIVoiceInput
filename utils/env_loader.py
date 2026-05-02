import os
import shutil
import subprocess
from pathlib import Path

APP_DIR_NAME = 'RBIVoiceInput'
ENV_FILE_NAME = '.env'


def _user_env_dir() -> Path:
    appdata = os.environ.get('APPDATA')
    base = Path(appdata) if appdata else Path.home() / 'AppData' / 'Roaming'
    return base / APP_DIR_NAME


def _project_env_path() -> Path:
    return Path(__file__).parent.parent / ENV_FILE_NAME


def _resolve_env_path() -> Path:
    user_env = _user_env_dir() / ENV_FILE_NAME
    if user_env.exists():
        return user_env

    project_env = _project_env_path()
    if project_env.exists():
        try:
            user_env.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(project_env, user_env)
            return user_env
        except OSError:
            return project_env

    return user_env


def _open_folder_and_notify(folder: Path) -> None:
    try:
        folder.mkdir(parents=True, exist_ok=True)
        subprocess.Popen(['explorer', str(folder)])
    except OSError:
        pass


def _parse_env_file(path: Path) -> dict[str, str]:
    env_vars: dict[str, str] = {}
    with open(path, encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                env_vars[key.strip()] = value.strip().strip('"\'')
    return env_vars


def load_env_variables() -> dict[str, str]:
    env_path = _resolve_env_path()
    if not env_path.exists():
        folder = _user_env_dir()
        print(f'警告: .envファイルが見つかりません。{folder} に .env を配置してください。')
        _open_folder_and_notify(folder)
        return {}
    return _parse_env_file(env_path)
