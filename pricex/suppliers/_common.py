"""Helpers shared by several supplier parsers (files starting with _ are not suppliers)."""
import re

from .. import normalize as N

EMOJI_RE = re.compile("[\U0001F000-\U0001FAFF☀-➿️‍⬀-⯿]+")
SIZE_WORDS = {"small": "S", "medium": "M", "large": "L", "extra large": "XL"}
COMMON = {"in", "do", "es", "it", "ma", "co", "ch", "per", "col", "dom", "mar", "sa", "ar", "us"}


def clean(text):
    """Remove emojis, WhatsApp *bold* marks and repeated spaces."""
    t = EMOJI_RE.sub(" ", str(text or ""))
    t = t.replace("*", " ").replace("_", " ").replace(" ", " ").replace("–", "-").replace("—", "-")
    return re.sub(r"\s+", " ", t).strip()


def clean_size(text):
    s = clean(text).strip(" .:-")
    s = re.sub(r"(?i)^size\s*", "", s).strip()
    s = re.sub(r"(?i)(\d+\+?)\s*(gr|g)$", r"\1", s)           # 250+gr -> 250+
    s = re.sub(r"(?i)^x(\d)", r"\1", s)                        # X14 -> 14
    return SIZE_WORDS.get(s.lower(), s)


def remove_alias(text, species):
    """Remove the words naming the species ('Mango', 'Avocado'...) from the text."""
    import json
    data = json.loads((N.DATA / "species.json").read_text(encoding="utf-8"))
    aliases = sorted([species] + data["species"].get(species, []), key=len, reverse=True)
    for a in aliases:
        new = re.sub(rf"(?i)(?<![\w]){re.escape(a)}(?![\w])", " ", text, count=1)
        if new != text:
            return re.sub(r"\s+", " ", new).strip()
    return text


def describe(text):
    """Split a heading like 'Mango Keitt 4kg BR 252pp' into its parts.
    Returns dict: species, variety, origin, weight, pack, box_pp, rest."""
    t = clean(text)
    out = {"species": None, "variety": "", "origin": "", "weight": None, "pack": "", "box_pp": None}

    m = re.search(r"(?i)\b(\d+)\s*p\.?p\.?\b", t)
    if m:
        out["box_pp"] = int(m[1])
        t = t[:m.start()] + " " + t[m.end():]
    m = re.search(r"(?i)\b\d+\s*[x*]\s*\d+(?:[.,]\d+)?\s*(?:gr|gram|g|kg|st|stuks|pcs|pc)?\b", t)
    if m:
        out["pack"] = N.pack_detail(m.group())
        out["weight"] = N.parse_weight(m.group())
        t = t[:m.start()] + " " + t[m.end():]
    m = re.search(r"(?i)(?<![\d.,])(\d+(?:[.,]\d+)?)\s*kg\b\+?", t)
    if m:
        out["weight"] = N.to_number(m[1])
        t = t[:m.start()] + " " + t[m.end():]

    tokens = re.split(r"(\s+|[|():,]|\s-\s)", t)
    kept = []
    for tok in tokens:
        w = tok.strip()
        if w and not out["origin"] and N.is_origin(w) and (
                (w.isupper() and len(w) <= 3) or len(w) > 3 or (len(w) == 3 and w.lower() not in COMMON)):
            out["origin"] = w
            continue
        kept.append(tok)
    t = "".join(kept)

    species = N.find_species(t)
    if species:
        t = remove_alias(t, species)
    out["species"] = species
    out["variety"] = re.sub(r"\s+", " ", re.sub(r"[|:()]+|\s-\s|^-|-$", " ", t)).strip(" -")
    return out


def box_material(species, weight):
    """10 kg avocados come in plastic crates; everything else in carton."""
    is_avo = (species or "") == "Avocados" or N.species_from_variety(species or "") == "Avocados"
    return "Plastic" if is_avo and weight and weight >= 10 else "Carton"
