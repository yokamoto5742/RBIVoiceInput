import configparser
import os
import sys
from typing import Any


_config_path_cache = None


def get_config_path():
    global _config_path_cache
    if _config_path_cache is None:
        if getattr(sys, 'frozen', False):
            base_path = getattr(sys, '_MEIPASS', os.path.dirname(__file__))
        else:
            base_path = os.path.dirname(__file__)
        _config_path_cache = os.path.join(base_path, 'config.ini')
    return _config_path_cache


def get_config_value(config: configparser.ConfigParser, section: str, key: str, default: Any) -> Any:
    try:
        value = config[section][key]
        if isinstance(default, bool):
            return value.lower() in ('true', '1', 'yes', 'on')
        return type(default)(value)
    except (KeyError, ValueError, TypeError):
        return default


def load_config() -> configparser.ConfigParser:
    config = configparser.ConfigParser()
    config_path = get_config_path()
    try:
        with open(config_path, encoding='utf-8') as f:
            config.read_file(f)
    except FileNotFoundError:
        print(f"設定ファイルが見つかりません。デフォルト設定で起動します: {config_path}")
    except PermissionError:
        print(f"設定ファイルを読み取る権限がありません: {config_path}")
        raise
    except configparser.Error as e:
        print(f"設定ファイルの解析中にエラーが発生しました: {e}")
        raise
    return config


def save_config(config: configparser.ConfigParser):
    config_path = get_config_path()
    try:
        with open(config_path, 'w', encoding='utf-8') as configfile:
            config.write(configfile)
    except PermissionError:
        print(f"設定ファイルを書き込む権限がありません: {config_path}")
        raise
    except IOError as e:
        print(f"設定ファイルの保存中にエラーが発生しました: {e}")
        raise
