"""Word Viewer：以 PySide6 + QtWebEngine + docx-preview 檢視 .docx。"""


def main() -> None:
    # 延遲匯入：避免 `python -m wordview` 時 __main__ 被重複載入而出現 RuntimeWarning
    from .__main__ import main as _main
    _main()
