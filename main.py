import logging
import traceback

from app import __version__
from app.application import Application
from app.error_handler import show_error_dialog, write_error_report


def main():
    app = Application()

    try:
        app.run()
        logging.info('アプリケーションが正常に終了しました')

    except FileNotFoundError as e:
        error_msg = f'必要なファイルが見つかりません:\n{str(e)}\n\n設定ファイルやリソースファイルを確認してください。'
        logging.error(error_msg)
        logging.debug(f'FileNotFoundError詳細: {traceback.format_exc()}')
        show_error_dialog(error_msg, 'ファイルエラー')

    except ValueError as e:
        error_msg = f'設定値エラー:\n{str(e)}\n\n設定ファイルや環境変数を確認してください。'
        logging.error(error_msg)
        logging.debug(f'ValueError詳細: {traceback.format_exc()}')
        show_error_dialog(error_msg, '設定エラー')

    except Exception as e:
        error_msg = f'予期せぬエラーが発生しました:\n{str(e)}\n\n詳細は error_log.txt をご確認ください。'
        logging.error(error_msg)
        logging.error(f'予期せぬエラーの詳細: {traceback.format_exc()}')
        write_error_report(__version__, e)
        show_error_dialog(error_msg, '予期せぬエラー')

    finally:
        app.close()


if __name__ == '__main__':
    main()
