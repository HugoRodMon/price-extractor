"""Read price lists that arrive as pictures (png, jpg, webp...).

Uses the OCR built into Windows 10/11, so nothing extra has to be installed.
Small or compressed pictures are hard to read, so:
  1. the picture is read several times (enlarged x3/x4/x5, plain and sharpened) and the words are
     combined by their position: a word one reading misses is usually caught by another;
  2. misread words are corrected against the words we know (species, varieties, countries, column
     names, data/ocr_words.txt): 'Pabner' -> Palmer, 'Vtetram' -> Vietnam;
  3. letters read inside numbers are fixed ('10,so' -> 10,50).
The result is the same as for a pdf: lines of words with their position on the page.
"""
import asyncio
import difflib
import json
import re
from functools import lru_cache
from pathlib import Path

DATA = Path(__file__).parent / "data"
READINGS = [(3, True), (3, False), (4, True), (5, True)]       # (enlarge, sharpen)


def read_picture(path):
    """Main reading + second reading of a picture, both as [(text, x0, x1, top, height)].
    Main: RapidOCR (reads names, sizes and table cells best). Second: Windows OCR (reads the numbers
    best), used by parsers to double-check prices and sizes. Without RapidOCR, Windows is the main one."""
    second = ocr_words(path)
    try:
        main = rapid_words(path)
    except ImportError:
        return second, []
    return main, second


@lru_cache(maxsize=1)
def _rapid():
    from rapidocr_onnxruntime import RapidOCR
    return RapidOCR()


def rapid_words(path):
    """RapidOCR finds whole cells ('Green skin avocado', '8/9/10/11'); they are split into words with
    positions spread over the cell so they fall into the right columns."""
    import numpy as np
    from PIL import Image

    img = Image.open(path).convert("RGB")
    result, _ = _rapid()(np.array(img))
    words = []
    for box, text, _conf in result or []:
        xs = [p[0] for p in box]
        ys = [p[1] for p in box]
        x0, x1, top, h = min(xs), max(xs), min(ys), max(ys) - min(ys)
        text = re.sub(r"^[EeCc€]\s*(?=\d+[.,]\d{2}$)", "€ ", text.strip())     # 'E9,00' -> '€ 9,00'
        parts = text.split()
        total = max(1, sum(len(p) for p in parts) + len(parts) - 1)
        pos = x0
        for p in parts:
            width = (x1 - x0) * len(p) / total
            words.append((fix_word(p), pos, pos + width, top, h))
            pos += width + (x1 - x0) / total
    return words


def ocr_words(path):
    """All words of the picture with positions in the picture's own pixels: [(text, x0, x1, top, height)]."""
    from PIL import Image, ImageFilter

    base = Image.open(path).convert("L")
    engine = _engine()
    merged = []
    for scale, sharpen in READINGS:
        scale = max(1, min(scale, 9000 // max(base.size)))
        img = base.resize((base.width * scale, base.height * scale), Image.LANCZOS)
        if sharpen:
            img = img.filter(ImageFilter.UnsharpMask(2, 150, 3))
        words = [(t, x / scale, (x + w) / scale, y / scale, h / scale) for t, x, y, w, h in _read(engine, img)]
        merged = _merge(merged, words)
    return [(fix_word(t), x0, x1, top, h) for t, x0, x1, top, h in merged]


# ---------------------------------------------------------------- Windows OCR

def _engine():
    from winrt.windows.globalization import Language
    from winrt.windows.media.ocr import OcrEngine

    for tag in ("en-US", "en-GB", "es-ES", "nl-NL"):
        lang = Language(tag)
        if OcrEngine.is_language_supported(lang):
            return OcrEngine.try_create_from_language(lang)
    engine = OcrEngine.try_create_from_user_profile_languages()
    if engine is None:
        raise RuntimeError("Windows has no OCR language installed (Settings > Time & language > Language)")
    return engine


def _read(engine, img):
    from winrt.windows.graphics.imaging import BitmapPixelFormat, SoftwareBitmap
    from winrt.windows.storage.streams import DataWriter

    img = img.convert("RGBA")
    writer = DataWriter()
    writer.write_bytes(img.tobytes())
    bitmap = SoftwareBitmap.create_copy_from_buffer(writer.detach_buffer(), BitmapPixelFormat.RGBA8,
                                                    img.width, img.height)

    async def run():
        return await engine.recognize_async(bitmap)

    result = asyncio.run(run())
    out = []
    for line in result.lines:
        for w in line.words:
            r = w.bounding_rect
            out.append((w.text, r.x, r.y, r.width, r.height))
    return out


# ---------------------------------------------------------------- combining readings

def _overlap(a, b):
    """How much two word boxes overlap (0..1, relative to the smaller one)."""
    ax0, ax1, at, ah = a[1], a[2], a[3], a[4]
    bx0, bx1, bt, bh = b[1], b[2], b[3], b[4]
    w = min(ax1, bx1) - max(ax0, bx0)
    h = min(at + ah, bt + bh) - max(at, bt)
    if w <= 0 or h <= 0:
        return 0
    return (w * h) / max(1e-6, min((ax1 - ax0) * ah, (bx1 - bx0) * bh))


def _merge(have, new):
    """Add the words of another reading: new places are added; where both readings found a word,
    the one that is a known word (or a clean number) wins."""
    out = list(have)
    for w in new:
        hits = [i for i, h in enumerate(out) if _overlap(h, w) > 0.35]
        if not hits:
            out.append(w)
            continue
        i = hits[0]
        if _quality(w[0]) > _quality(out[i][0]):
            out[i] = w
    return out


def _quality(text):
    t = text.strip()
    if re.fullmatch(r"\d+([.,]\d{2})?|\d+(/\d+)+|€", t):
        return 3
    if t.lower() in vocabulary():
        return 3
    if re.fullmatch(r"[A-Za-z]+", t):
        return 2
    return 1


# ---------------------------------------------------------------- word fixes

@lru_cache(maxsize=None)
def vocabulary():
    """Known words: species & aliases, varieties, countries & codes, column names, data/ocr_words.txt."""
    words = set()
    sp = json.loads((DATA / "species.json").read_text(encoding="utf-8"))
    for name, aliases in sp["species"].items():
        for a in [name] + aliases:
            words.update(a.lower().split())
    for v in list(sp["varieties"]) + list(sp.get("variety_codes", {}).values()):
        words.update(v.lower().split())
    for name, codes in json.loads((DATA / "origins.json").read_text(encoding="utf-8"))["countries"].items():
        words.update(name.lower().split())
        words.update(c for c in codes if len(c) >= 3)
    templates = DATA / "templates.json"                  # varieties typed in the final files
    if templates.exists():
        for sup in json.loads(templates.read_text(encoding="utf-8")).values():
            for v in sup.get("varieties", []):
                words.update(w for w in re.split(r"[\s/]+", v.lower()) if w.isalpha())
    extra = DATA / "ocr_words.txt"
    if extra.exists():
        for line in extra.read_text(encoding="utf-8").splitlines():
            if line.strip() and not line.startswith("#"):
                words.update(line.lower().split())
    return {w for w in words if len(w) >= 3}


SLIPS = {"alr": "air", "ey": "By", "8y": "By", "bv": "By", "lime": "Lime", "kg.": "kg"}
NUMBER_FIXES =str.maketrans({"s": "5", "S": "5", "o": "0", "O": "0", "l": "1", "I": "1", "B": "8"})


def fix_word(text):
    t = text.replace("�", "€").strip()
    # a pack with the 'x' misread: '20~450g', '20€100gr', '12*100g' -> '20x450g'
    m = re.fullmatch(r"(\d+)[^\w.,/+\s]+(\d+)\s*(g|gr|kg|gram)", t, re.I)
    if m:
        return f"{m[1]}x{m[2]}{m[3]}"
    # a number with letters read into it: '10,so' -> '10,50', '2O' -> '20'
    if re.search(r"\d", t) and re.fullmatch(r"[\dsSoOlIB.,/+-]+", t):
        t = t.translate(NUMBER_FIXES)
    if t.lower() in SLIPS:                               # short words OCR often gets wrong
        return SLIPS[t.lower()]
    if "/" in t:                                         # 'Red/White', 'CH/COL/GUA': leave compounds alone
        return t
    letters = re.sub(r"[^A-Za-zÀ-ÿ]", "", t)
    if len(letters) >= 4 and not re.search(r"\d", t) and letters.lower() not in vocabulary():
        match = closest(letters.lower(), vocabulary(), 0.72)
        if match:
            return match.capitalize() if letters[:1].isupper() else match
    return t


def closest(word, words, cutoff):
    """Closest known word of a similar length ('Braril' -> brazil), or None."""
    near = [w for w in words if abs(len(w) - len(word)) <= (1 if len(word) <= 5 else 2)]
    match = difflib.get_close_matches(word, near, n=1, cutoff=cutoff)
    return match[0] if match else None


def known(text):
    """Is every word of the text a word we know (variety, species, country...)?"""
    words = [w for w in re.split(r"[\s/]+", str(text).lower()) if w.isalpha()]
    return bool(words) and all(w in vocabulary() for w in words)
