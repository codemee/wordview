[English](README.en.md) | **繁體中文**

# Word Viewer

以 PySide6 + QtWebEngine + [docx-preview](https://github.com/VolodymyrBaydalka/docxjs) 製作的 `.docx` 檢視器。頁面尺寸、字型與版面盡量貼近 Word，可縮放、跳頁，並可匯出 PDF 或列印。

## 安裝與執行

需要 [uv](https://docs.astral.sh/uv/) 與 Python 3.12 以上。

```
uv sync
uv run python -m wordview [檔案.docx]
```

## 操作

| 功能 | 方式 |
|---|---|
| 開啟 | 工具列「開啟」、Ctrl+O，或把 `.docx` 拖進視窗（對話框預設為目前文件所在資料夾） |
| 匯出 PDF／列印 | 工具列按鈕、Ctrl+E／Ctrl+P（頁面大小依原檔） |
| 換頁 | 狀態列的上一頁／下一頁、PageUp／PageDown，或在頁碼框輸入後按 Enter |
| 縮放 | 狀態列的縮小／放大／比例下拉、Ctrl+滾輪、Ctrl+-／Ctrl+=；適合寬度、適合整頁；Ctrl+0 還原 100% |

## 與 Word 版面對齊的處理

docx-preview 以 HTML 近似 Word，本專案在渲染後額外補強（`src/wordview/assets/viewer.js`）：

- **行格線（docGrid）**：Word 在 `type="lines"` 時，每行高度會對齊 `linePitch` 的倍數；依此調整行高，空段落也佔一整行。
- **自動分頁**：依頁面內容高度自行分頁，段落可在行與行之間跨頁，與 Word 的總頁數一致。
- **字型**：依「Normal 樣式 → 主題字型 → docDefaults」解析西文與東亞字型；只指定東亞字型的樣式，西文改回 Normal 的字型。
- **雲端字型**：Windows 的雲端字型（如 Aptos）瀏覽器看不到，`fonts.py` 會把文件用到的字型轉成 `@font-face`（僅限這台電腦已下載過者）。
- **中英文間距**：套用 `text-autospace`；相鄰全形標點依 Word 的「標點符號擠壓」縮減空白。
- **段落邊框**：`doubleWave`（雙波浪線）與 `dashed`（虛線）左邊框，與文字保持間距且相鄰段落連成一條；表格儲存格內不畫段落左右邊框。
- **圖片段落**：圖下留白、圖片文字的底線（如點狀底線）畫在圖片下方；`●□★` 等符號改用東亞字型。

## 專案結構

```
src/wordview/
├─ __main__.py      入口
├─ main_window.py   主視窗：圖示工具列、狀態列（頁碼／縮放）、列印與匯出 PDF
├─ icons.py         向量圖示（SVG → QIcon）與應用程式圖示
├─ fonts.py         雲端字型 → @font-face
└─ assets/
   ├─ viewer.html / viewer.js   渲染、版面補強、縮放、頁碼
   ├─ icon.svg                  應用程式圖示
   ├─ docx-preview.min.js       docx-preview 0.3.3（Apache-2.0）
   └─ jszip.min.js              JSZip 3.10.1（MIT 或 GPL-3.0）
tests/test_smoke.py  產生 A4／Letter 檔 → 匯出 PDF → 檢查頁數與紙張大小
```

## 測試

```
uv run pytest
```

## 已知限制

- 以 HTML 近似 Word，複雜物件（文字方塊、SmartArt、部分域代碼）可能有差異；字形的繪製方式與 Word 不同，筆畫粗細略有差別。
- 中英文自動間距的寬度與 Word 不完全相同（瀏覽器約 1/8 字寬，Word 約 1/4），部分行的換行位置會有出入。
- 分頁是近似計算，個別頁面的分頁位置可能與 Word 略有差異。
- 僅支援 `.docx`；不支援舊版 `.doc`。目前以 Windows 為主要測試環境。
