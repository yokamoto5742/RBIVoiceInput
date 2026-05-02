import configparser

import pytest

from utils.app_config import AppConfig


def dict_to_config(config_dict: dict) -> configparser.ConfigParser:
    """辞書をConfigParserオブジェクトに変換する"""
    config = configparser.ConfigParser()
    string_dict: dict[str, dict[str, str]] = {}
    for section, options in config_dict.items():
        string_dict[section] = {key: str(value) for key, value in options.items()}
    config.read_dict(string_dict)
    return config


def dict_to_app_config(config_dict: dict) -> AppConfig:
    """辞書をAppConfigオブジェクトに変換する"""
    return AppConfig(dict_to_config(config_dict))


@pytest.fixture
def make_app_config():
    """辞書からAppConfigを生成するファクトリfixture"""
    def _factory(config_dict: dict) -> AppConfig:
        return dict_to_app_config(config_dict)
    return _factory
