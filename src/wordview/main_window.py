"""主視窗：圖示工具列、狀態列（頁碼與縮放）、列印與匯出 PDF"""
import base64
import json
from pathlib import Path

from PySide6.QtCore import QMarginsF, QSizeF, QTimer, QUrl, Qt
from PySide6.QtGui import QAction, QKeySequence, QPageLayout, QPageSize
from PySide6.QtPrintSupport import QPrintDialog, QPrinter
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import (QComboBox, QFileDialog, QFrame, QLabel, QLineEdit,
                               QMainWindow, QMessageBox, QToolBar, QToolButton, QWidget)

from .fonts import cloud_font_css
from .icons import app_icon, icon

ASSETS = Path(__file__).parent / "assets"
TOOLBAR_HEIGHT = 34
ZOOMS = ["50%", "75%", "100%", "125%", "150%", "200%", "300%"]

# 現代扁平風格（淺色）
STYLE = f"""
QMainWindow {{ background: #f8fafc; }}
QToolBar {{ background: #f8fafc; border: 0; border-bottom: 1px solid #e2e8f0;
            padding: 0px; spacing: 4px; }}
QToolBar QToolButton {{ border: 0; border-radius: 6px; padding: 4px; background: transparent;
                        margin: 2px 2px 1px 2px; }}   /* 20px 圖示 + 內外距 → 工具列剛好 34px */
QStatusBar QToolButton {{ border: 0; border-radius: 5px; padding: 3px; background: transparent; }}
QToolButton {{ background: transparent; }}
QToolButton:hover {{ background: #e2e8f0; }}
QToolButton:pressed {{ background: #cbd5e1; }}
QToolButton:disabled {{ background: transparent; }}
QToolTip {{ background: #1e293b; color: #f8fafc; border: 0; padding: 4px 8px; }}
QStatusBar {{ background: #f8fafc; border-top: 1px solid #e2e8f0; color: #64748b; }}
QStatusBar::item {{ border: 0; }}
QStatusBar QLabel {{ color: #64748b; }}
QStatusBar QToolButton {{ padding: 3px; border-radius: 5px; }}
QLineEdit {{ background: #fff; border: 1px solid #e2e8f0; border-radius: 5px;
             padding: 2px 4px; color: #334155; selection-background-color: #bfdbfe;
             selection-color: #1e3a8a; }}
QLineEdit:focus {{ border-color: #3b82f6; }}
QComboBox {{ background: #fff; border: 1px solid #e2e8f0; border-radius: 5px;
             padding: 2px 4px; color: #334155; }}
QComboBox:focus, QComboBox:on {{ border-color: #3b82f6; }}
QComboBox::drop-down {{ border: 0; width: 18px; }}
QComboBox::down-arrow {{ image: url({(ASSETS / 'chevron-down.svg').as_posix()}); width: 12px; height: 12px; }}
QComboBox QAbstractItemView {{ background: #fff; border: 1px solid #e2e8f0; color: #334155;
             selection-background-color: #dbeafe; selection-color: #1e3a8a; outline: 0; }}
QFrame#sep {{ background: #e2e8f0; max-width: 1px; min-width: 1px; }}
"""


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Word Viewer")
        self.setWindowIcon(app_icon())
        self.setStyleSheet(STYLE)
        self.resize(1000, 800)
        self.setAcceptDrops(True)
        self.path: Path | None = None
        self.loaded = False
        self.pending: Path | None = None

        self.view = QWebEngineView()
        self.view.loadFinished.connect(self._on_loaded)
        self.view.load(QUrl.fromLocalFile(str(ASSETS / "viewer.html")))
        self.setCentralWidget(self.view)

        self._build_toolbar()
        self._build_statusbar()
        self.statusBar().showMessage("拖放 .docx 檔案或按 Ctrl+O 開啟")

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._poll)
        self.timer.start(200)

    # ---- UI ----
    def _action(self, name, tip, slot, key=None) -> QAction:
        a = QAction(icon(name), tip, self)
        a.setToolTip(f"{tip} ({key})" if key else tip)
        if key:
            a.setShortcut(QKeySequence(key))
        a.triggered.connect(slot)
        self.addAction(a)
        return a

    def _build_toolbar(self) -> None:
        tb = QToolBar()
        tb.setMovable(False)
        tb.setFloatable(False)
        tb.setFixedHeight(TOOLBAR_HEIGHT)
        # 注意：QSS 的 padding 不可寫成「0 8px」——Qt 會把 8px 也套到上下，
        # 擠扁按鈕、讓圖示跟著縮小。左側邊距改用間隔元件。
        gap = QWidget()
        gap.setFixedWidth(6)
        tb.addWidget(gap)
        tb.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
        tb.setIconSize(tb.iconSize().__class__(20, 20))
        tb.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)
        self.addToolBar(tb)
        tb.addAction(self._action("open", "開啟", self.open_dialog, "Ctrl+O"))
        tb.addAction(self._action("pdf", "匯出 PDF", self.export_pdf, "Ctrl+E"))
        tb.addAction(self._action("print", "列印", self.print_doc, "Ctrl+P"))

    def _tool(self, name, tip, slot, key=None) -> QToolButton:
        b = QToolButton()
        b.setDefaultAction(self._action(name, tip, slot, key))
        b.setAutoRaise(True)
        b.setIconSize(b.iconSize().__class__(18, 18))
        return b

    @staticmethod
    def _sep() -> QFrame:
        f = QFrame()
        f.setObjectName("sep")
        f.setFixedHeight(16)
        return f

    def _build_statusbar(self) -> None:
        sb = self.statusBar()
        sb.setSizeGripEnabled(False)

        # 換頁：上一頁、頁碼輸入、總頁數、下一頁
        sb.addPermanentWidget(self._tool("prev", "上一頁", lambda: self._step(-1), "PgUp"))
        self.page_edit = QLineEdit("0")
        self.page_edit.setFixedWidth(44)
        self.page_edit.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.page_edit.setToolTip("輸入頁碼後按 Enter 跳頁")
        self.page_edit.returnPressed.connect(self._goto_page)
        sb.addPermanentWidget(self.page_edit)
        self.total_label = QLabel("/ 0")
        self.total_label.setMinimumWidth(36)
        sb.addPermanentWidget(self.total_label)
        sb.addPermanentWidget(self._tool("next", "下一頁", lambda: self._step(1), "PgDown"))
        sb.addPermanentWidget(self._sep())

        # 縮放：縮小、比例、放大、適合寬度、適合整頁、還原
        sb.addPermanentWidget(self._tool("minus", "縮小", lambda: self._zoom_by(-0.1), "Ctrl+-"))
        self.zoom_box = QComboBox()
        self.zoom_box.setEditable(True)
        self.zoom_box.addItems(ZOOMS)
        self.zoom_box.setCurrentText("100%")
        self.zoom_box.setFixedWidth(84)
        self.zoom_box.setToolTip("縮放比例")
        self.zoom_box.textActivated.connect(self._zoom_text)
        sb.addPermanentWidget(self.zoom_box)
        sb.addPermanentWidget(self._tool("plus", "放大", lambda: self._zoom_by(0.1), "Ctrl+="))
        sb.addPermanentWidget(self._tool("fit_width", "適合寬度", lambda: self._zoom_text("適合寬度")))
        sb.addPermanentWidget(self._tool("fit_page", "適合整頁", lambda: self._zoom_text("適合整頁")))
        sb.addPermanentWidget(self._tool("reset", "還原 100%", lambda: self._zoom_text("100%"), "Ctrl+0"))

    # ---- 載入 ----
    def _on_loaded(self, ok: bool) -> None:
        self.loaded = ok
        if ok and self.pending:
            self.open_file(self.pending)

    def open_dialog(self) -> None:
        # 預設資料夾：目前開啟文件所在的資料夾；尚未開啟文件時用使用者家目錄
        start = str(self.path.parent) if self.path else str(Path.home())
        f, _ = QFileDialog.getOpenFileName(self, "開啟檔案", start, "Word 文件 (*.docx)")
        if f:
            self.open_file(f)

    def open_file(self, f) -> None:
        p = Path(f)
        if not self.loaded:
            self.pending = p
            return
        self.pending = None
        if p.suffix.lower() != ".docx":
            QMessageBox.warning(self, "不支援的格式", "僅支援 .docx 檔案。")
            return
        b64 = base64.b64encode(p.read_bytes()).decode()
        self.path = p
        self.setWindowTitle(f"{p.name} - Word Viewer")
        self.statusBar().showMessage(str(p))
        # 先注入文件用到的雲端字型（如 Aptos），再渲染
        self.view.page().runJavaScript(f"injectFonts({json.dumps(cloud_font_css(p))})")
        self.view.page().runJavaScript(f'renderDocx("{b64}")')

    def dragEnterEvent(self, e) -> None:
        if e.mimeData().hasUrls():
            e.acceptProposedAction()

    def dropEvent(self, e) -> None:
        for u in e.mimeData().urls():
            self.open_file(u.toLocalFile())
            break

    # ---- 縮放 / 頁碼 ----
    def _zoom_text(self, t: str) -> None:
        js = {"適合寬度": "fitWidth()", "適合整頁": "fitPage()"}.get(t)
        if js is None:
            try:
                js = f"setZoom({float(t.strip().rstrip('%')) / 100})"
            except ValueError:
                return
        self.view.page().runJavaScript(js)

    def _zoom_by(self, d: float) -> None:
        self.view.page().runJavaScript(f"setZoom(zoom + ({d}))")

    def _step(self, d: int) -> None:
        self.view.page().runJavaScript(f"gotoPage(currentPage() + ({d}))")

    def _goto_page(self) -> None:
        try:
            n = int(self.page_edit.text())
        except ValueError:
            return
        self.view.page().runJavaScript(f"gotoPage({n})")
        self.view.setFocus()

    def _poll(self) -> None:
        if self.loaded:
            self.view.page().runJavaScript("state()", self._on_state)

    def _on_state(self, s) -> None:
        if not s:
            return
        cur, total, z = json.loads(s)
        if not self.page_edit.hasFocus():
            self.page_edit.setText(str(cur))
        self.total_label.setText(f"/ {total}")
        if not self.zoom_box.lineEdit().hasFocus() and not self.zoom_box.view().isVisible():
            self.zoom_box.setEditText(f"{round(z * 100)}%")

    def wheelEvent(self, e) -> None:
        if e.modifiers() & Qt.KeyboardModifier.ControlModifier:
            self._zoom_by(0.1 if e.angleDelta().y() > 0 else -0.1)
            e.accept()
        else:
            super().wheelEvent(e)

    # ---- 列印 / PDF（頁面尺寸依原檔）----
    def _with_page_size(self, cb) -> None:
        def got(raw):
            size = json.loads(raw) if raw else None
            if not size:
                self.statusBar().showMessage("尚未開啟文件")
                return
            w, h = size[0] * 25.4 / 96, size[1] * 25.4 / 96  # px → mm
            cb(QPageSize(QSizeF(w, h), QPageSize.Unit.Millimeter))
        self.view.page().runJavaScript("pageSizePx()", got)

    def export_pdf(self) -> None:
        if not self.path:
            return
        out, _ = QFileDialog.getSaveFileName(
            self, "匯出 PDF", str(self.path.with_suffix(".pdf")), "PDF (*.pdf)")
        if not out:
            return

        def go(ps: QPageSize) -> None:
            layout = QPageLayout(ps, QPageLayout.Orientation.Portrait, QMarginsF(0, 0, 0, 0))
            self.view.page().printToPdf(out, layout)
            self.view.page().pdfPrintingFinished.connect(
                lambda p, ok: self.statusBar().showMessage(
                    f"已匯出：{p}" if ok else "匯出失敗"))
        self._with_page_size(go)

    def print_doc(self) -> None:
        def go(ps: QPageSize) -> None:
            printer = QPrinter(QPrinter.PrinterMode.HighResolution)
            printer.setPageLayout(QPageLayout(ps, QPageLayout.Orientation.Portrait, QMarginsF(0, 0, 0, 0)))
            if QPrintDialog(printer, self).exec():
                self.view.page().print(printer, lambda ok: self.statusBar().showMessage(
                    "已送出列印" if ok else "列印失敗"))
        self._with_page_size(go)
