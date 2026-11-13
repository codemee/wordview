// 檢視器：渲染 docx、縮放、頁碼
const container = document.getElementById("c");
let zoom = 1;

function pages() { return [...container.querySelectorAll("section.docx")]; }

async function renderDocx(b64) {
  const bin = atob(b64);
  const bytes = Uint8Array.from(bin, ch => ch.charCodeAt(0));
  container.innerHTML = "";
  const grid = await readDocGrid(bytes);
  await docx.renderAsync(bytes, container, null,
    { breakPages: true, inWrapper: true, ignoreLastRenderedPageBreak: IGNORE_HINTS });
  await document.fonts.ready;            // 等雲端字型載入完成，後續量測才準
  const latin = await readLatinFont(bytes);
  if (latin) applyLatinFont(latin);
  applySymbolFont(latin && latin.ea);
  compressPunct();
  if (grid) applyGrid(grid);
  applyLeftBorders(await readLeftBorderStyles(bytes));
  applyImageParagraphs();
  repaginate();
  setZoom(1);
  window.scrollTo(0, 0);
  return pages().length;
}

// 是否忽略 Word 存檔時記錄的分頁提示（lastRenderedPageBreak）
// （行高、空段落都模擬到與 Word 相同後，自行分頁的結果比沿用提示更準：33 頁 = Word 的頁數）
let IGNORE_HINTS = true;
const PX_PER_TWIP = 96 / 1440;

// 讀取 docGrid：Word 在 type=lines 時會把每行高度對齊到 linePitch 的倍數
async function readDocGrid(bytes) {
  try {
    const zip = await JSZip.loadAsync(bytes);
    const xml = await zip.file("word/document.xml").async("string");
    const m = xml.match(/<w:docGrid\b[^>]*>/);
    if (!m) return null;
    const type = (m[0].match(/w:type="([^"]+)"/) || [])[1];
    const pitch = +((m[0].match(/w:linePitch="(\d+)"/) || [])[1] || 0);
    if (!type || type === "default" || !pitch) return null;
    return { pitch: pitch * PX_PER_TWIP };
  } catch (e) { return null; }
}

// 模擬 Word 的「標點符號擠壓」：相鄰的全形標點只留一邊的空白。
// Chromium 的 text-spacing-trim 對新細明體無效，所以直接用負 margin 處理。
const P_CLOSE = "，。、；：！？）」』》〉】〕］｝";
const P_OPEN = "（「『《〈【〔［｛";
function compressPunct() {
  container.querySelectorAll("section.docx > article p").forEach(p => {
    const w = document.createTreeWalker(p, NodeFilter.SHOW_TEXT);
    const nodes = [];
    for (let n = w.nextNode(); n; n = w.nextNode()) if (n.nodeValue) nodes.push(n);
    // flags[n][i]：'R' = 縮掉該字右側空白、'L' = 縮掉該字左側空白
    const flags = nodes.map(n => new Array(n.nodeValue.length).fill(""));
    const at = (ni, i) => i < nodes[ni].nodeValue.length ? [ni, i]
      : (ni + 1 < nodes.length ? [ni + 1, 0] : null);
    nodes.forEach((n, ni) => {
      const s = n.nodeValue;
      for (let i = 0; i < s.length; i++) {
        const nx = at(ni, i + 1);
        if (!nx) continue;
        const c = s[i], d = nodes[nx[0]].nodeValue[nx[1]];
        if (P_CLOSE.includes(c) && (P_CLOSE.includes(d) || P_OPEN.includes(d))) flags[ni][i] = "R";
        else if (P_OPEN.includes(c) && P_OPEN.includes(d)) flags[nx[0]][nx[1]] = "L";
      }
    });
    nodes.forEach((n, ni) => {
      if (!flags[ni].some(Boolean)) return;
      const frag = document.createDocumentFragment();
      let buf = "";
      [...n.nodeValue].forEach((ch, i) => {
        if (!flags[ni][i]) { buf += ch; return; }
        if (buf) { frag.appendChild(document.createTextNode(buf)); buf = ""; }
        const sp = document.createElement("span");
        sp.textContent = ch;
        // 新細明體的全形標點置中於字格，縮半格會讓字形相碰；Word 實測約縮 3/8 格
        sp.style[flags[ni][i] === "R" ? "marginRight" : "marginLeft"] = "-0.375em";
        frag.appendChild(sp);   // 維持 inline，才不會影響禁則換行
      });
      if (buf) frag.appendChild(document.createTextNode(buf));
      n.parentNode.replaceChild(frag, n);
    });
  });
}

// 全形符號（●、□、★、→ 等）在 Word 中對東亞文字使用東亞字型（新細明體）繪製，
// 外觀是滿格的大符號；瀏覽器會改用 Times New Roman 的小符號，這裡獨立包起來指定字型。
const SYMBOLS = /[←-↙①-⑳■-◿★☆※]+/g;
function applySymbolFont(ea) {
  if (!ea) return;
  container.querySelectorAll("section.docx > article p").forEach(p => {
    const w = document.createTreeWalker(p, NodeFilter.SHOW_TEXT);
    const nodes = [];
    for (let n = w.nextNode(); n; n = w.nextNode()) if (new RegExp(SYMBOLS.source).test(n.nodeValue)) nodes.push(n);
    nodes.forEach(n => {
      const frag = document.createDocumentFragment();
      let last = 0;
      for (const m of n.nodeValue.matchAll(SYMBOLS)) {
        if (m.index > last) frag.appendChild(document.createTextNode(n.nodeValue.slice(last, m.index)));
        const sp = document.createElement("span");
        sp.textContent = m[0];
        sp.style.fontFamily = `"${ea}"`;
        frag.appendChild(sp);
        last = m.index + m[0].length;
      }
      if (last < n.nodeValue.length) frag.appendChild(document.createTextNode(n.nodeValue.slice(last)));
      n.parentNode.replaceChild(frag, n);
    });
  });
}

// 段落左邊框：Word 的 doubleWave（雙波浪線）、與文字保持間距、相鄰段落的邊框連成一條。
const WAVE = "url(\"data:image/svg+xml;utf8," +
  "<svg xmlns='http://www.w3.org/2000/svg' width='6' height='8'>" +
  "<path d='M1 0Q2.6 2 1 4T1 8M4 0Q5.6 2 4 4T4 8' fill='none' stroke='%23808080' stroke-width='0.8'/></svg>\")";
const BORDER_GAP = 4 * 96 / 72;   // Word 的 w:space（此文件為 4pt）
// 找出「只有左邊框」的段落樣式：{ styleId: 邊框種類 }（doubleWave、dashed…）
async function readLeftBorderStyles(bytes) {
  const out = {};
  try {
    const zip = await JSZip.loadAsync(bytes);
    const xml = await zip.file("word/styles.xml").async("string");
    for (const m of xml.matchAll(/<w:style\b[^>]*w:styleId="([^"]+)"[\s\S]*?<\/w:style>/g)) {
      const bdr = m[0].match(/<w:pBdr>[\s\S]*?<\/w:pBdr>/);
      if (!bdr || /<w:(top|bottom|right)\b/.test(bdr[0])) continue;
      const left = bdr[0].match(/<w:left\b[^>]*w:val="([^"]+)"/);
      if (left) out[m[1]] = left[1];
    }
  } catch (e) { /* 讀不到就維持 docx-preview 的預設外觀 */ }
  return out;
}

// 虛線：Word 的 dashed 約為「長 5px、間隔 3px」，Chromium 的 1px dashed 看起來像實線
const DASH = "repeating-linear-gradient(to bottom,#808080 0,#808080 5px,transparent 5px,transparent 8px)";

function applyLeftBorders(kinds) {
  const kindOf = p => {
    for (const id in kinds) if (p.classList.contains("docx_" + id)) return kinds[id];
    return null;
  };
  const ps = [...container.querySelectorAll("section.docx > article > p")];
  const key = (p, kind) => kind + "|" + getComputedStyle(p).borderLeftWidth;
  ps.forEach((p, i) => {
    const kind = kindOf(p);
    if (kind !== "doubleWave" && kind !== "dashed") return;
    const cs = getComputedStyle(p);
    const bw = parseFloat(cs.borderLeftWidth);
    if (!bw) return;
    const next = ps[i + 1] === p.nextElementSibling ? ps[i + 1] : null;
    const joined = next && kindOf(next) === kind;
    p.style.marginLeft = (parseFloat(cs.marginLeft) - BORDER_GAP - bw) + "px";
    p.style.paddingLeft = (parseFloat(cs.paddingLeft) + BORDER_GAP) + "px";
    p.style.borderLeft = bw + "px solid transparent";   // 保留寬度，改由背景繪製
    p.style.backgroundRepeat = "repeat-y";
    p.style.backgroundPosition = "left top";
    p.style.backgroundOrigin = "border-box";
    if (kind === "doubleWave") p.style.backgroundImage = WAVE;
    else { p.style.backgroundImage = DASH; p.style.backgroundSize = Math.max(bw, 1.33) + "px 100%"; }
    if (joined) {   // 段落間距併入下方內距，讓邊框不斷開
      p.style.paddingBottom = (parseFloat(cs.paddingBottom) + parseFloat(cs.marginBottom)) + "px";
      p.style.marginBottom = "0";
    }
  });
}

// 只含圖片的段落：Word 的行高在圖片下方多留一段（約 6px），
// 且圖片所在文字若有底線（如點狀底線），Word 會把底線畫在圖片下方。
const IMG_EXTRA = 6;
function applyImageParagraphs() {
  container.querySelectorAll("section.docx > article > p").forEach(p => {
    const img = p.querySelector("img");
    if (!img || p.textContent.trim()) return;
    p.style.paddingBottom = (parseFloat(getComputedStyle(p).paddingBottom) + IMG_EXTRA) + "px";
    const span = img.closest("span");
    const sc = span && getComputedStyle(span);
    if (sc && sc.textDecorationLine.includes("underline")) {
      p.style.position = "relative";
      const pr = p.getBoundingClientRect(), ir = img.getBoundingClientRect();
      const line = document.createElement("div");
      line.style.cssText = `position:absolute;height:0;pointer-events:none;` +
        `left:${ir.left - pr.left}px;width:${ir.width}px;top:${ir.bottom - pr.top + 3}px;` +
        `border-top:1px dotted ${sc.textDecorationColor}`;
      p.appendChild(line);
    }
  });
}

// 讀取預設段落樣式（Normal）的西文字型，例如 Times New Roman
// 解析順序：Normal 樣式明確指定 → Normal 的主題字型 → docDefaults 明確指定 → docDefaults 的主題字型
async function readLatinFont(bytes) {
  try {
    const zip = await JSZip.loadAsync(bytes);
    const read = async n => zip.file(n) ? await zip.file(n).async("string") : "";
    const styles = await read("word/styles.xml");
    const theme = await read("word/theme/theme1.xml");
    const settings = await read("word/settings.xml");
    const defTag = ((styles.match(/<w:docDefaults>[\s\S]*?<\/w:docDefaults>/) || [""])[0]).match(/<w:rFonts\b[^>]*>/);
    const normal = styles.match(/<w:style\b[^>]*w:type="paragraph"[^>]*w:default="1"[\s\S]*?<\/w:style>/);
    const nTag = normal && normal[0].match(/<w:rFonts\b[^>]*>/);
    const get = (tag, a) => tag ? ((tag[0].match(new RegExp(`w:${a}="([^"]+)"`)) || [])[1] || null) : null;
    const themeFont = key => {            // key 例如 minorHAnsi、majorEastAsia
      const re = key.startsWith("major") ? /<a:majorFont>[\s\S]*?<\/a:majorFont>/ : /<a:minorFont>[\s\S]*?<\/a:minorFont>/;
      const block = (theme.match(re) || [""])[0];
      if (!/EastAsia/.test(key)) return (block.match(/<a:latin typeface="([^"]+)"/) || [])[1] || null;
      const ea = (block.match(/<a:ea typeface="([^"]*)"/) || [])[1];
      if (ea) return ea;
      // 主題的 ea 是空的：依文件的東亞語言挑對應文字的字型（zh-TW → Hant → 新細明體）
      const lang = (settings.match(/<w:themeFontLang\b[^>]*w:eastAsia="([^"]+)"/) || [])[1] || "";
      const script = { "zh-TW": "Hant", "zh-HK": "Hant", "zh-CN": "Hans", "ja-JP": "Jpan", "ko-KR": "Hang" }[lang];
      return script ? ((block.match(new RegExp(`<a:font script="${script}" typeface="([^"]+)"`)) || [])[1] || null) : null;
    };
    const resolve = (attr, themeAttr) => get(nTag, attr)
      || (get(nTag, themeAttr) && themeFont(get(nTag, themeAttr)))
      || get(defTag, attr)
      || (get(defTag, themeAttr) && themeFont(get(defTag, themeAttr)))
      || null;
    const latin = resolve("ascii", "asciiTheme");
    const ea = resolve("eastAsia", "eastAsiaTheme");
    return latin ? { latin, ea } : null;
  } catch (e) { return null; }
}

// 由 Python 傳入的 @font-face（雲端字型，如 Aptos）
function injectFonts(css) {
  let st = document.getElementById("cloudfonts");
  if (!st) { st = document.createElement("style"); st.id = "cloudfonts"; document.head.appendChild(st); }
  st.textContent = css || "";
}

// docx-preview 會把「只有東亞字型」的樣式當成整段字型，西文字母因而變成新細明體；
// 主題字型（如 Aptos）也可能未安裝。這裡一律讓西文字型回到 Normal 指定的字型。
function applyLatinFont({ latin, ea }) {
  const stack = ea ? `"${latin}", "${ea}"` : `"${latin}"`;
  container.querySelectorAll("section.docx > article p, section.docx > article span").forEach(el => {
    const fam = getComputedStyle(el).fontFamily;
    if (!fam) return;
    if (fam.includes(latin)) {            // 已有西文字型但沒有東亞字型：中文會落到系統備用字型
      if (ea && !fam.includes(ea)) el.style.fontFamily = `${fam}, "${ea}"`;
      return;
    }
    const first = fam.split(",")[0].replace(/["']/g, "").trim();
    if (first === "Aptos") el.style.fontFamily = stack;          // 主題字型：西文＋東亞都補上
    else if (/[^\x00-\x7F]/.test(first)) el.style.fontFamily = `"${latin}", ${fam}`;
  });
}

// 模擬行格線：行高向上取整到 pitch 的倍數
function applyGrid(grid) {
  container.querySelectorAll("section.docx > article p").forEach(p => {
    const cs = getComputedStyle(p);
    let fs = parseFloat(cs.fontSize) || 16;
    p.querySelectorAll("span").forEach(s => {          // 取段內最大字級
      fs = Math.max(fs, parseFloat(getComputedStyle(s).fontSize) || 0);
    });
    const lh = parseFloat(cs.lineHeight);
    // 新細明體等 CJK 字型的自然行高約為字級的 1.3 倍（14pt 會超過一格而佔兩格）
    const natural = Math.max(isNaN(lh) ? 0 : lh, fs * 1.3);
    const h = Math.max(1, Math.ceil(natural / grid.pitch - 0.01)) * grid.pitch;
    p.style.lineHeight = h + "px";
    p.style.minHeight = h + "px";   // 空段落也要佔一整行
  });
}

// 跨頁的純文字段落在「行與行之間」切開：原段落截短留在本頁，
// 複本裁掉已顯示的行後放到下一頁（行高已對齊格線，每行等高）。
function splitParagraph(k, base, contentH) {
  if (k.tagName !== "P" || k.querySelector("img,svg,table")) return null;
  const cs = getComputedStyle(k);
  const lh = parseFloat(cs.lineHeight);
  const r = k.getBoundingClientRect();
  if (!lh || isNaN(lh)) return null;
  const lines = Math.round((r.height - parseFloat(cs.paddingTop) - parseFloat(cs.paddingBottom)) / lh);
  const fit = Math.floor((contentH - (r.top - base) + 0.5) / lh);
  if (lines < 2 || fit < 1 || fit >= lines) return null;
  const mb = cs.marginBottom;
  const rest = k.cloneNode(true);
  k.style.height = fit * lh + "px";
  k.style.overflow = "hidden";
  k.style.marginBottom = "0";
  k.style.paddingBottom = "0";
  rest.style.marginTop = -(fit * lh) + "px";
  rest.style.marginBottom = "0";
  const wrap = document.createElement("div");
  wrap.style.height = (r.height - fit * lh) + "px";
  wrap.style.overflow = "hidden";
  wrap.style.marginBottom = mb;
  wrap.appendChild(rest);
  return wrap;
}

// 內容超出頁面高度時，把後面的區塊移到新頁
function repaginate() {
  for (let sec of pages()) {
    const art = sec.querySelector(":scope > article");
    if (!art) continue;
    const cs = getComputedStyle(sec);
    const contentH = parseFloat(cs.minHeight) - parseFloat(cs.paddingTop) - parseFloat(cs.paddingBottom);
    window.__dbg = window.__dbg || [];
    window.__dbg.push([Math.round(contentH), Math.round(art.getBoundingClientRect().height)]);
    let cur = sec, curArt = art;
    while (true) {
      const base = curArt.getBoundingClientRect().top;
      const kids = [...curArt.children];
      let idx = -1;
      for (let i = 1; i < kids.length; i++) {
        const r = kids[i].getBoundingClientRect();
        const mb = parseFloat(getComputedStyle(kids[i]).marginBottom) || 0;
        if (r.bottom - base > contentH + 0.5) { idx = i; break; }
      }
      if (idx < 0) break;
      const next = cur.cloneNode(false);
      for (const c of cur.children) if (c.tagName !== "ARTICLE") next.appendChild(c.cloneNode(true));
      const nextArt = curArt.cloneNode(false);
      let moved = kids.slice(idx);
      const part = splitParagraph(kids[idx], base, contentH);
      if (part) moved = [part, ...moved.slice(1)];
      moved.forEach(k => nextArt.appendChild(k));
      next.appendChild(nextArt);
      cur.after(next);
      cur = next; curArt = nextArt;
    }
  }
}

function setZoom(z) {
  zoom = Math.max(0.1, Math.min(5, z));
  container.style.zoom = zoom;
  return zoom;
}

function pageSizePx() {
  const p = pages()[0];
  if (!p) return null;
  return JSON.stringify([p.offsetWidth, p.offsetHeight]);
}

function fitWidth() {
  const s = pageSizePx();
  if (!s) return zoom;
  return setZoom((window.innerWidth - 48) / s[0]);
}

function fitPage() {
  const s = pageSizePx();
  if (!s) return zoom;
  return setZoom(Math.min((window.innerWidth - 48) / s[0], (window.innerHeight - 32) / s[1]));
}

function currentPage() {
  const mid = window.innerHeight / 2;
  const ps = pages();
  let cur = 0;
  ps.forEach((p, i) => { if (p.getBoundingClientRect().top <= mid) cur = i; });
  return cur + 1;
}

function gotoPage(n) {
  const p = pages()[n - 1];
  if (p) window.scrollTo(0, window.scrollY + p.getBoundingClientRect().top - 8);
}

function state() { return JSON.stringify([currentPage(), pages().length, zoom]); }

