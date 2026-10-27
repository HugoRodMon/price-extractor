"""Shared cleaning rules used by every supplier parser."""
import json
import re
from functools import lru_cache
from pathlib import Path

DATA = Path(__file__).parent / "data"


# ---------------------------------------------------------------- numbers

def to_number(text):
    """'10,0' -> 10, '4,5kg' -> 4.5, '13.6' -> 13.6. Returns None if there's no number."""
    if text is None:
        return None
    if isinstance(text, (int, float)):
        return int(text) if float(text).is_integer() else text
    m = re.search(r"\d+(?:[.,]\d+)?", str(text))
    if not m:
        return None
    value = float(m.group().replace(",", "."))
    return int(value) if value.is_integer() else value


PRICE_RES = [
    re.compile(r"€\s*(\d(?:\d| (?=\d))*(?:[.,]\d+)?)"),          # € 12,50 / € 1 3,25 / €22
    re.compile(r"(\d+[.,]\d{1,2})\s*(?:€|e\b|eur\b)", re.I),     # 12.50e / 9,50 €
]


def parse_price(text):
    """First price in the text, or None. Handles '€ 12,50', '€ 1 3,25', '12.50e', '€22', '9,50 €'.
    'On request', 'POR', 'P.O.R.', 'exp', dates... return None."""
    if text is None:
        return None
    if isinstance(text, (int, float)):
        return float(text)
    s = str(text)
    for rx in PRICE_RES:
        m = rx.search(s)
        if m:
            return float(m[1].replace(" ", "").replace(",", "."))
    return None


def parse_plain_price(text):
    """A cell that only holds a number like '12,50' or '9.50' (no € sign)."""
    if isinstance(text, (int, float)):
        return float(text)
    s = str(text or "").strip().replace("€", "").strip()
    if re.fullmatch(r"\d[\d ]*[.,]\d{1,2}|\d{1,3}", s):
        return float(s.replace(" ", "").replace(",", "."))
    return None


def parse_weight(text):
    """'4,5kg' -> 4.5, '10x500gr' -> 5, '12x125 gram' -> 1.5, '13 kg+' -> 13, '2x5 KG' -> 10."""
    if text is None or text == "":
        return None
    if isinstance(text, (int, float)):
        return to_number(text)
    s = str(text).lower().replace(",", ".")
    if re.search(PIECES, s):
        return None                                   # '10x2st' counts pieces, not weight
    m = re.search(r"(\d+)\s*[x*]\s*(\d+(?:\.\d+)?)\s*(kg|gr?|gram)?", s)
    if m:
        n, each, unit = int(m[1]), float(m[2]), m[3] or ("g" if float(m[2]) >= 50 else "kg")
        total = n * each / (1000 if unit.startswith("g") else 1)
        return to_number(round(total, 3))
    return to_number(s)


def find_weight(text):
    """Weight only when it's written as one: '4.5 Kg', '10 X 500 Gr', '15kg' (not the 10 of 'IFG10')."""
    s = str(text or "")
    m = re.search(r"(?i)(\d+)\s*[x*]\s*(\d+(?:[.,]\d+)?)\s*(kg|gr?|gram)\b", s)
    if m:
        return parse_weight(m.group())
    m = re.search(r"(?i)(?<![\w.,])(\d+(?:[.,]\d+)?)\s*kg\b", s)
    return to_number(m[1]) if m else None


PIECES = r"(?i)\d+\s*[x*]\s*\d+\s*(st|stuks|pcs|pc|pieces)\b"


def pack_detail(text):
    """'10x500gr' -> '10x500g', '12*100g' -> '12x100g', '10 X 500 Gr' -> '10x500g', '10x2st' -> '10x2st'.
    None if not a pack."""
    m = re.search(r"(?i)(\d+)\s*[x*]\s*(\d+)\s*(st|stuks|pcs|pc|pieces)\b", str(text or ""))
    if m:
        return f"{m[1]}x{m[2]}{'st' if m[3].lower().startswith('st') else 'pcs'}"
    m = re.search(r"(\d+)\s*[x*]\s*(\d+(?:[.,]\d+)?)\s*(kg|gr?|gram)?", str(text or ""), re.I)
    if not m:
        return None
    unit = (m[3] or ("g" if float(m[2].replace(",", ".")) >= 50 else "kg")).lower()
    unit = "kg" if unit == "kg" else "g"
    return f"{m[1]}x{m[2]}{unit}"


# ---------------------------------------------------------------- sizes

def clean_size(value):
    """Numbers become numbers, everything else stays text."""
    if value is None:
        return ""
    if isinstance(value, (int, float)):
        return to_number(value)
    s = str(value).strip().strip(".")
    if re.fullmatch(r"\d+", s):
        return int(s)
    return s


def split_sizes(size, species=None):
    """Grouped sizes become one row per size:
    '6/7' -> [6, 7], '8-9-10' -> [8, 9, 10], '12 & 14' -> [12, 14].
    A range of two sizes follows the species' size series (data/species.json, "size_series"):
    mangoes '6-12' -> [6, 7, 8, 9, 10, 12], avocados '10--24' -> [10, 12, ..., 24].
    '01/10/2020' is a range written '10-20' that Excel turned into a date -> 10 to 20.
    Kept as one size: 'Mix 12-16', '2-105' (a count, not a range), '1XX', '250+', '12x100'."""
    if isinstance(size, (int, float)) or size in ("", None):
        return [clean_size(size)]
    s = str(size).strip()
    s = re.sub(r"(?i)^(\d+)\s*(?:g|gr|gram|grams)?\s*\+\s*(?:g|gr|gram|grams)?$", r"\1+", s)   # 250g + -> 250+
    if re.match(r"(?i)mix\b", s):
        return [("Mix " + re.sub(r"(?i)^mix\s*", "", s)).strip()]
    m = re.fullmatch(r"0?1[/.-](\d{1,2})[/.-](\d{4})", s)     # 01/10/2020 -> 10 to 20
    if m and int(m[1]) < int(m[2]) % 100:
        return size_range(int(m[1]), int(m[2]) % 100, species)
    m = re.fullmatch(r"(\d+)\s*(?:-{1,2}|–)\s*(\d+)", s)      # 6-12, 10--24
    if m and int(m[1]) < int(m[2]) <= 3 * int(m[1]):
        return size_range(int(m[1]), int(m[2]), species, full="--" in s)
    parts = re.split(r"\s*(?:/|-|–|&)\s*", s)
    if len(parts) > 1 and all(re.fullmatch(r"\d+", p) for p in parts):
        nums = [int(p) for p in parts]
        # "2-105" or "3-126" (count after a size code) is not a group of sizes
        if max(nums) <= 3 * max(min(nums), 1) and nums == sorted(nums):
            return nums
        return [s]
    if len(parts) > 1 and all(re.fullmatch(r"(?i)[smlx]{1,4}|j{1,2}|xxl", p) for p in parts):
        return [p.upper() for p in parts]                     # S/M/L, S-M-L-XL
    return [clean_size(s)]


def size_range(lo, hi, species=None, full=False):
    """Sizes from lo to hi. Uses the species' size series when there is one (mangoes skip 11 and 13,
    avocados go in steps of 2); otherwise '10--24' counts every even/odd size and '6-8' is just both ends."""
    series = _species_data()[3].get(species or "")
    if series:
        inside = [n for n in series if lo <= n <= hi]
        return sorted(set(inside) | {lo, hi})
    if full:
        step = 2 if lo % 2 == 0 and hi % 2 == 0 else 1
        return list(range(lo, hi + 1, step))
    return [lo, hi]


# ---------------------------------------------------------------- species

@lru_cache(maxsize=None)
def _species_data():
    data = json.loads((DATA / "species.json").read_text(encoding="utf-8"))
    alias = {}
    for name, words in data["species"].items():
        alias[name.lower()] = name
        for w in words:
            alias[w.lower()] = name
    return (alias, {k.lower(): v for k, v in data["varieties"].items()}, [w.lower() for w in data["ignore"]],
            data.get("size_series", {}))


def _simplify(text):
    return re.sub(r"[^a-zà-ÿ0-9/ ]+", " ", str(text).lower()).split()


def find_species(text):
    """Species named anywhere in the text (longest match wins), else None. 'Avocado Greenskin' -> Avocados."""
    alias, _, _, _ = _species_data()
    words = _simplify(text)
    joined = " " + " ".join(words) + " "
    best = None
    for a, name in alias.items():
        if f" {a} " in joined and (best is None or len(a) > len(best[0])):
            best = (a, name)
    return best[1] if best else None


def species_from_variety(text):
    _, varieties, _, _ = _species_data()
    joined = " " + " ".join(_simplify(text)) + " "
    best = None
    for v, name in varieties.items():
        if f" {v} " in joined and (best is None or len(v) > len(best[0])):
            best = (v, name)
    return best[1] if best else None


def is_ignored(text):
    _, _, ignore, _ = _species_data()
    joined = " " + " ".join(_simplify(text)) + " "
    return any(f" {w} " in joined for w in ignore)


# ---------------------------------------------------------------- origins

@lru_cache(maxsize=None)
def _origins():
    data = json.loads((DATA / "origins.json").read_text(encoding="utf-8"))["countries"]
    lookup = {}
    for name, codes in data.items():
        lookup[name.lower()] = name
        for c in codes:
            lookup[c.lower()] = name
    return lookup, {name: codes[0].upper() for name, codes in data.items()}


def origin_name(text):
    """'RSA' -> 'South Africa', 'Brasil' -> 'Brazil'. Unknown text comes back as written."""
    if not text:
        return ""
    lookup, _ = _origins()
    s = str(text).strip()
    parts = re.split(r"\s*/\s*", s)
    if len(parts) > 1 and all(p.lower() in lookup for p in parts):
        return "/".join(lookup[p.lower()] for p in parts)
    return lookup.get(s.lower().strip("."), lookup.get(s.lower(), s))


def origin_code(text):
    """'South Africa' -> 'ZA', 'Brasil' -> 'BR'."""
    lookup, codes = _origins()
    name = origin_name(text)
    return codes.get(name, str(text).strip())


def is_origin(text):
    lookup, _ = _origins()
    return str(text).strip().lower().strip(".") in lookup


def split_origins(text):
    """'Dom. Rep. / Colombia' -> ['Dom. Rep.', 'Colombia'], 'CH/COL/GUA' -> 3 origins.
    Only split when every part is a known country, so unknown text stays as written."""
    s = str(text or "").strip()
    parts = [p.strip() for p in re.split(r"\s*(?:/|&|,|\+)\s*", s) if p.strip()]
    if len(parts) > 1 and all(is_origin(p) for p in parts):
        return parts
    return [s]


def format_origin(text, style, overrides=None):
    """style: 'source' (as the supplier wrote it), 'name' (Brazil), 'NAME' (BRAZIL), 'code' (BR)."""
    if not text:
        return ""
    if overrides:
        name = origin_name(text)
        if name in overrides:
            return overrides[name]
    if style == "name":
        return origin_name(text)
    if style == "NAME":
        return origin_name(text).upper()
    if style == "code":
        return origin_code(text)
    return str(text).strip()


# ---------------------------------------------------------------- packaging

def packaging_from(text, weight=None, default="Carton"):
    """'Plastic' / 'Carton' / 'Bags' from text; 10 kg avocados & co. usually come in plastic."""
    s = str(text or "").lower()
    if "plastic" in s or "polycote" in s:
        return "Plastic"
    if "bag" in s and "carrybag" not in s and "paperbag" not in s:
        return "Bags"
    return default


def box_type(text):
    """OT -> Open Top, TC -> Telescopic."""
    s = " " + str(text or "").lower().replace(".", "") + " "
    if " ot " in s or "open top" in s:
        return "Open Top"
    if " tc " in s or "telescop" in s:
        return "Telescopic"
    return ""


def title(text):
    """'GALIA melons' -> 'Galia Melons' but keeps codes like 'IFG 11' and 'RTE'."""
    words = str(text or "").split()
    return " ".join(w if (w.isupper() and len(w) <= 4) or any(c.isdigit() for c in w) else w.capitalize() for w in words)
