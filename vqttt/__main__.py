import sys
import logging

import qtpy


if not qtpy.PYQT5 and not qtpy.PYSIDE2:
    if sys.platform == 'linux':
        sys.exit("Error: a compatible Qt library couldn't be imported.\n"
                 "Please install python3-pyqt5 (or just python-pyqt5) from your package manager.")
    else:
        sys.exit("Error: a compatible Qt library couldn't be imported.\n"
                 "Please install it by running `pip install pyqt5")


def init_logging():
    log = logging.getLogger('VQ')
    term_handler = logging.StreamHandler()

    try:
        import colorlog
        fmt = colorlog.ColoredFormatter('%(asctime)s %(log_color)s[%(name)12s:%(lineno)3s'
                                        ' %(funcName)18s ]\t%(levelname)-.6s  %(message)s', '%H:%M:%S')
    except ImportError:
        fmt = logging.Formatter('%(asctime)s [%(name)12s:%(lineno)3s '
                                '%(funcName)18s ]\t%(levelname)-.6s  %(message)s', '%H:%M:%S')

    term_handler.setFormatter(fmt)
    log.addHandler(term_handler)
    log.setLevel(logging.DEBUG)
    return log


def main():
    import signal
    from vqttt.main_window import MainWindow
    from vqttt.resources import qCleanupResources
    from qtpy.QtGui import QIcon
    from qtpy.QtWidgets import QApplication

    if sys.platform == 'win32':
        import ctypes
        appid = 'bus1111.vqttt'
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(appid)

    app = QApplication(sys.argv)
    app.setWindowIcon(QIcon(':/vqttt_icon.png'))
    LOG = init_logging()
    mw = MainWindow(LOG, app)
    signal.signal(signal.SIGINT, mw.signal_handler)

    sys.exit(app.exec_())
    qCleanupResources()


if __name__ == '__main__':
    main()
