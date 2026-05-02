import os
import sys
import tkinter as tk
import traceback
from tkinter import messagebox


def show_error_dialog(message: str, title: str = 'エラー') -> None:
    try:
        try:
            root = tk.Misc._default_root  # type: ignore[attr-defined]
            if root:
                root.withdraw()
        except Exception:
            pass

        error_root = tk.Tk()
        error_root.withdraw()
        messagebox.showerror(title, message)
        error_root.destroy()

    except Exception as dialog_error:
        print(f'{title}: {message}', file=sys.stderr)
        print(f'ダイアログ表示エラー: {str(dialog_error)}', file=sys.stderr)


def write_error_report(version: str, exc: Exception) -> None:
    """エラーレポートを出力する"""
    try:
        report = (
            f'=== RBIVoiceInput エラーレポート ===\n'
            f'バージョン: {version}\n'
            f'エラータイプ: {type(exc).__name__}\n'
            f'エラーメッセージ: {str(exc)}\n\n'
            f'=== スタックトレース ===\n'
            f'{traceback.format_exc()}\n'
        )
        with open('error_log.txt', 'w', encoding='utf-8') as f:
            f.write(report)
        try:
            os.startfile('error_log.txt')
        except Exception:
            pass

    except Exception as log_error:
        print(f'エラーログの作成に失敗しました: {str(log_error)}', file=sys.stderr)
        print(f'元のエラー: {str(exc)}', file=sys.stderr)
