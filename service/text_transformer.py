import logging
import re
from typing import Dict


def process_punctuation(text: str, use_punctuation: bool) -> str:
    """句読点の有無に応じてテキストを処理する"""
    if use_punctuation:
        return text

    try:
        return text.replace('。', '').replace('、', '')
    except (AttributeError, TypeError) as e:
        logging.error(f'句読点処理中にタイプエラー: {str(e)}')
        return text
    except Exception as e:
        logging.error(f'句読点処理中に予期しないエラー: {str(e)}')
        return text


def load_replacements(replacements_path: str) -> Dict[str, str]:
    """置換辞書ファイルを読み込む"""
    replacements: Dict[str, str] = {}
    logging.info(f'置換辞書ファイルのパス: {replacements_path}')

    try:
        with open(replacements_path, encoding='utf-8') as f:
            for line_number, line in enumerate(f.readlines(), 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    old, new = line.split(',')
                    replacements[old.strip()] = new.strip()
                    logging.debug(f'置換辞書読み込み - {line_number}行目: \'{old.strip()}\' → \'{new.strip()}\'')
                except ValueError:
                    logging.error(f'置換ファイルの{line_number}行目に無効な行があります: {line}')

        logging.info(f'置換ルールの総数: {len(replacements)}')

    except IOError as e:
        logging.error(f'置換ファイルの読み込み中にエラーが発生しました: {e}')
        return {}
    except Exception as e:
        logging.error(f'予期せぬエラーが発生しました: {e}', exc_info=True)
        return {}

    return replacements


def remove_ja_en_spaces(text: str) -> str:
    """日本語文字と英数字の間の半角スペースを除去する"""
    text = re.sub(r'([぀-鿿＀-￯])\s+([A-Za-z0-9])', r'\1\2', text)
    text = re.sub(r'([A-Za-z0-9])\s+([぀-鿿＀-￯])', r'\1\2', text)
    return text


def replace_text(text: str, replacements: Dict[str, str]) -> str:
    """置換辞書に従ってテキストを変換する"""
    if not text:
        logging.error('入力テキストが空です')
        return ''

    if not replacements:
        logging.warning('置換辞書が空です')
        return text

    try:
        result = text
        logging.info(f'テキスト置換開始 - 文字数: {len(text)}')

        for old, new in replacements.items():
            if old in result:
                before_replace = result
                result = result.replace(old, new)
                if before_replace != result:
                    logging.debug(f'置換実行: \'{old}\' → \'{new}\'')

        logging.info('テキスト置換完了')
        return result

    except Exception as e:
        logging.error(f'テキスト置換中にエラーが発生: {str(e)}', exc_info=True)
        return text
