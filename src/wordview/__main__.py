"""入口：uv run python -m wordview [file.docx]"""
import sys

from PySide6.QtWidgets import QApplication

from .icons import app_icon
from .main_window import MainWindow


def main() -> None:
    if sys.platform == "win32":   # 讓工作列使用本程式自己的圖示，而不是 python.exe 的
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("wordview.viewer")
    app = QApplication(sys.argv)
    app.setStyle("Fusion")        # 搭配 QSS，各平台外觀一致
    app.setWindowIcon(app_icon())
    win = MainWindow()
    win.show()
    if len(sys.argv) > 1:
        win.open_file(sys.argv[1])
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
