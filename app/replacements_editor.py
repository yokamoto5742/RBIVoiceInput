import logging
import os
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Optional

from utils.app_config import AppConfig


class ReplacementsEditor:
    def __init__(
            self,
            parent: tk.Tk,
            config: AppConfig,
            file_path: Optional[str] = None,
            title: Optional[str] = None,
    ):
        self.config = config
        self._file_path = file_path or config.replacements_file
        self.window = tk.Toplevel(parent)
        self.window.title(title or '置換辞書登録( 置換前 , 置換後 )')
        self.window.geometry(f'{config.editor_width}x{config.editor_height}')

        self.text_area = tk.Text(
            self.window,
            wrap=tk.WORD,
            width=50,
            height=20,
            font=(config.editor_font_name, config.editor_font_size)
        )
        self.text_area.pack(expand=True, fill='both', padx=10, pady=5)

        scrollbar = ttk.Scrollbar(self.window, command=self.text_area.yview)
        scrollbar.pack(side='right', fill='y')
        self.text_area['yscrollcommand'] = scrollbar.set

        button_frame = ttk.Frame(self.window)
        button_frame.pack(fill='x', padx=10, pady=5)

        save_button = ttk.Button(button_frame, text='保存', command=self.save_file)
        save_button.pack(side='left', padx=5)

        cancel_button = ttk.Button(button_frame, text='キャンセル', command=self.window.destroy)
        cancel_button.pack(side='left', padx=5)

        self.load_file()

        self.window.transient(parent)
        self.window.grab_set()

    def load_file(self) -> None:
        try:
            if os.path.exists(self._file_path):
                with open(self._file_path, encoding='utf-8') as f:
                    self.text_area.insert('1.0', f.read())
            else:
                logging.warning(f'ファイルが見つかりません: {self._file_path}')
                messagebox.showwarning(
                    '警告',
                    f'ファイルが見つかりません。新規作成します：\n{self._file_path}'
                )
        except Exception as e:
            logging.error(f'ファイルの読み込みに失敗しました: {str(e)}')
            messagebox.showerror('エラー', f'ファイルの読み込みに失敗しました：\n{str(e)}')

    def save_file(self) -> None:
        try:
            dir_path = os.path.dirname(self._file_path)
            if dir_path:
                os.makedirs(dir_path, exist_ok=True)

            content = self.text_area.get('1.0', 'end-1c')
            with open(self._file_path, 'w', encoding='utf-8') as f:
                f.write(content)

            messagebox.showinfo('保存完了', 'ファイルを保存しました')
            self.window.destroy()

        except Exception as e:
            logging.error(f'ファイルの保存に失敗しました: {str(e)}')
            messagebox.showerror('エラー', f'ファイルの保存に失敗しました：\n{str(e)}')

