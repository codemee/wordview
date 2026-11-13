"""向量圖示：以 SVG 字串定義，執行時轉成 QIcon（支援高 DPI 與停用狀態）。"""
from pathlib import Path

from PySide6.QtCore import QByteArray, Qt
from PySide6.QtGui import QIcon, QImage, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

ASSETS = Path(__file__).parent / "assets"

# 24x24、線寬 2 的線條圖示（風格類似 Lucide）
_PATHS = {
    "open": '<path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/>',
    "pdf": ('<path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z"/>'
            '<path d="M14 3v5h5"/><path d="M12 11v6"/><path d="m9.5 14.5 2.5 2.5 2.5-2.5"/>'),
    "print": ('<path d="M7 9V3h10v6"/><rect x="3" y="9" width="18" height="8" rx="2"/>'
              '<path d="M7 14h10v7H7z"/>'),
    "prev": '<path d="m15 18-6-6 6-6"/>',
    "next": '<path d="m9 18 6-6-6-6"/>',
    "minus": '<path d="M5 12h14"/>',
    "plus": '<path d="M12 5v14M5 12h14"/>',
    "fit_width": '<path d="M3 12h18"/><path d="m7 8-4 4 4 4"/><path d="m17 8 4 4-4 4"/>',
    "fit_page": ('<path d="M8 3H5a2 2 0 0 0-2 2v3"/><path d="M21 8V5a2 2 0 0 0-2-2h-3"/>'
                 '<path d="M3 16v3a2 2 0 0 0 2 2h3"/><path d="M16 21h3a2 2 0 0 0 2-2v-3"/>'),
    "reset": '<path d="M3 12a9 9 0 1 0 3-6.7L3 8"/><path d="M3 3v5h5"/>',
}

_SIZES = (16, 20, 24, 32, 48)


def _render(svg: str, size: int) -> QPixmap:
    img = QImage(size, size, QImage.Format.Format_ARGB32_Premultiplied)
    img.fill(Qt.GlobalColor.transparent)
    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    QSvgRenderer(QByteArray(svg.encode())).render(p)
    p.end()
    return QPixmap.fromImage(img)


def icon(name: str, color: str = "#475569", disabled: str = "#cbd5e1") -> QIcon:
    """依名稱建立線條圖示；停用狀態自動換成較淺的顏色。"""
    ic = QIcon()
    for mode, c in ((QIcon.Mode.Normal, color), (QIcon.Mode.Disabled, disabled)):
        svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" '
               f'stroke="{c}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
               f'{_PATHS[name]}</svg>')
        for s in _SIZES:
            ic.addPixmap(_render(svg, s * 2), mode)   # 2 倍解析度，高 DPI 螢幕才清晰
    return ic


def app_icon() -> QIcon:
    """應用程式圖示（視窗標題列、工作列）。"""
    svg = (ASSETS / "icon.svg").read_text(encoding="utf-8")
    ic = QIcon()
    for s in (16, 24, 32, 48, 64, 128, 256):
        ic.addPixmap(_render(svg, s))
    return ic
