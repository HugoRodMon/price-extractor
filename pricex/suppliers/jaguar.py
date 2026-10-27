"""Jaguar The Fresh Company: WhatsApp message.

    🍊 Mandarins (ZA)            <- species (origin)
    Tango 10kg Cat 1             <- variety, weight, class
    size 2–105 € 17,50           <- size and price
    🫚 Ginger (BR)
    13,6kg 70pp € 24,00          <- no size
"""
import re

from .. import normalize as N
from ..base import Supplier, register
from ._common import box_material, clean, clean_size, describe

SPECIES_LINE = re.compile(r"^(?P<name>[^()€]+?)\s*\((?P<origin>[A-Za-z /]{2,})\)")


@register
class Jaguar(Supplier):
    name = "Jaguar"
    final_file = "Jaguar the fresh.xlsx"
    match_names = ["jaguar"]
    match_text = ["jaguar the fresh"]
    file_types = (".txt",)
    layout = "wide"
    origin_style = "name"
    sheet_names = {"Pomelos": "GRAPEFRUITS", "Passion Fruits": "PASSIONFRUITS"}

    def parse(self, doc):
        rows, sp, var = [], None, None
        for raw in doc.text.splitlines():
            line = clean(raw)
            if not line or line.lower().startswith("prices "):
                continue
            m = SPECIES_LINE.match(line)
            if m:
                sp = {"name": m["name"].strip(), "origin": m["origin"].strip()}
                var = None
                continue
            if sp is None:
                continue
            price = N.parse_price(line)
            sm = re.match(r"(?i)size\s+(.+?)\s*(?:€|por\b|exp\b|$)", line)
            if price is None and not sm:
                var = self.variety_line(line)             # "Tango 10kg Cat 1"
                continue
            if price is None:
                continue                                  # POR / EXP
            info = var or self.variety_line(re.sub(r"(?i)€.*|^size\b.*", "", line))
            weight = info["weight"]
            rows.append(self.row(
                specie=sp["name"], variety=info["variety"], origin=sp["origin"],
                size=clean_size(sm[1]) if sm else "N/S", weight=weight, box_pp=info["box_pp"],
                cat=info["cat"], detail=info["detail"], price=price,
                packaging=box_material(N.find_species(sp["name"]), weight)))
        return rows

    @staticmethod
    def variety_line(line):
        cat, detail = "", ""
        m = re.search(r"(?i)\bcat\.?\s*(\d|i{1,2})\b", line)
        if m:
            cat = 2 if m[1].lower() in ("2", "ii") else 1
            line = line[:m.start()] + line[m.end():]
        if re.search(r"\bTC\b", line):
            detail = "Telescopic"
        elif re.search(r"\bOT\b", line):
            detail = "Open Top"
        line = re.sub(r"\b(TC|OT)\b", " ", line)
        d = describe(line)
        d["cat"], d["detail"] = cat or 1, detail
        return d
