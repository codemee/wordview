"""煙霧測試：產生 A4/Letter 檔 → 無頭載入 → 匯出 PDF → 檢查頁數與尺寸"""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QTWEBENGINE_CHROMIUM_FLAGS", "--disable-gpu")
import sys

import pytest
from docx import Document
from docx.shared import Mm
from pypdf import PdfReader
from PySide6.QtCore import QEventLoop, QMarginsF, QTimer
from PySide6.QtGui import QPageLayout
from PySide6.QtWidgets import QApplication

from wordview.main_window import MainWindow


def make_docx(path, w_mm, h_mm):
    d = Document()
    s = d.sections[0]
    s.page_width, s.page_height = Mm(w_mm), Mm(h_mm)
    for i in range(3):
        d.add_paragraph(f"第 {i + 1} 頁 " + "測試文字 " * 30)
        if i < 2:
            d.add_page_break()
    d.save(path)


def wait(ms):
    loop = QEventLoop()
    QTimer.singleShot(ms, loop.quit)
    loop.exec()


@pytest.mark.parametrize("name,w,h", [("a4", 210, 297), ("letter", 215.9, 279.4)])
def test_export_matches_source_size(tmp_path, name, w, h):
    app = QApplication.instance() or QApplication(sys.argv)
    src, out = tmp_path / f"{name}.docx", tmp_path / f"{name}.pdf"
    make_docx(src, w, h)
    win = MainWindow()
    win.show()
    win.open_file(src)
    wait(3000)
    win._with_page_size(lambda ps: win.view.page().printToPdf(
        str(out), QPageLayout(ps, QPageLayout.Orientation.Portrait, QMarginsF(0, 0, 0, 0))))
    wait(4000)
    r = PdfReader(out)
    assert len(r.pages) >= 2
    pw, ph = float(r.pages[0].mediabox.width), float(r.pages[0].mediabox.height)
    assert abs(pw - w / 25.4 * 72) < 3 and abs(ph - h / 25.4 * 72) < 3

