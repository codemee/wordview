"""雲端字型支援：Windows 的「雲端字型」（如 Aptos）只在 Office 等程式要用時才下載，
放在 %LOCALAPPDATA%\\Microsoft\\FontCache\\4\\CloudFonts，內嵌瀏覽器看不到。
這裡把文件用到的雲端字型轉成 @font-face，讓頁面也能使用。"""
import os
import re
import zipfile
from functools import lru_cache
from pathlib import Path

from fontTools.ttLib import TTFont

MAX_SIZE = 3 * 1024 * 1024   # 略過動輒十幾 MB 的 CJK 雲端字型


def _cloud_dir() -> Path | None:
    base = os.environ.get("LOCALAPPDATA")
    d = Path(base) / "Microsoft" / "FontCache" / "4" / "CloudFonts" if base else None
    return d if d and d.is_dir() else None


def docx_font_names(docx: Path) -> set[str]:
    """文件的 fontTable 與佈景主題中出現的字型名稱。"""
    names: set[str] = set()
    try:
        with zipfile.ZipFile(docx) as z:
            for part, pat in (("word/fontTable.xml", r'w:name="([^"]+)"'),
                              ("word/theme/theme1.xml", r'<a:latin typeface="([^"]+)"')):
                if part in z.namelist():
                    names |= set(re.findall(pat, z.read(part).decode("utf8", "ignore")))
    except (OSError, zipfile.BadZipFile):
        pass
    return names


@lru_cache(maxsize=None)
def _faces(family_dir: str) -> tuple:
    """讀取資料夾內每個字型檔的 (路徑, 家族名, 粗細, 是否斜體)。"""
    out = []
    for f in sorted(Path(family_dir).glob("*.[tT][tT][fF]")):
        if f.stat().st_size > MAX_SIZE:
            continue
        try:
            font = TTFont(f, lazy=True)
            name = font["name"]
            # 用 nameID 1（舊式家族名，如 "Aptos Display"）；nameID 16 會把 Display 也歸成 Aptos
            fam = name.getDebugName(1) or Path(family_dir).name
            weight = font["OS/2"].usWeightClass
            italic = bool(font["OS/2"].fsSelection & 1)
            out.append((f.as_posix(), fam, weight, italic))
        except Exception:
            continue
    return tuple(out)


def cloud_font_css(docx: Path) -> str:
    """產生文件用到、且位於雲端字型資料夾的字型之 @font-face 規則。"""
    root = _cloud_dir()
    if not root:
        return ""
    faces: dict[tuple, str] = {}    # 同家族、粗細、斜體只留一個（資料夾內常有新舊兩版）
    for fam_name in sorted(docx_font_names(docx)):
        d = root / fam_name
        if not d.is_dir():
            continue
        for path, fam, weight, italic in _faces(str(d)):
            faces[(fam, weight, italic)] = path
    return "\n".join(
        f'@font-face{{font-family:"{fam}";src:url("file:///{path}");'
        f'font-weight:{weight};font-style:{"italic" if italic else "normal"};}}'
        for (fam, weight, italic), path in faces.items())
