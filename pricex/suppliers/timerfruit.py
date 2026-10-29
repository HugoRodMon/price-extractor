"""Timerfruit: pdf price list in Dutch.

    Omschrijving                                   Klasse Merk     Maat LvO PP  ETA  Prijs
     Druiven zonder pit                                                        <- section (species)
      Druiven Rood zonder pit Punnet 10 X 500 Gr                               <- group (colour, packing)
      Druiven IFG9 (Jack's Salute) 10 X 500 Gr     I      NO LABEL XL   PE  120 ...  € 19,00
      Mandarijnen 10 Kg OT                                                     <- group (weight, box)
      Mandarijnen Tango OT II Wrapped Top Layer    II     NTB      3    ZA  104      € 15,00
"""
import re

from .. import normalize as N
from ..base import Supplier, register
from ._common import remove_alias

COLOURS = {"rood": "Red", "wit": "White", "zwart": "Black", "geel": "Yellow", "wit/rood": "White/Red"}
HEADER = ["Omschrijving", "Klasse", "Merk", "Maat", "LvO", "PP", "ETA", "Prijs"]


@register
class Timerfruit(Supplier):
    name = "TIMERFRUIT"
    final_file = "TIMERFRUIT.xlsx"
    match_names = ["timerfruit"]
    match_text = ["timerfruit"]
    layout_hints = [r"omschrijving\s+klasse\s+merk\s+maat"]
    origin_style = "source"
    default_packaging = "CARTON"
    species_names = {"Nectarines": "Nectarin"}

    def parse(self, doc):
        rows, x, section, group = [], None, "", ""
        for line in doc.lines:
            texts = [w.text for w in line.words]
            if texts[:1] == ["Omschrijving"]:
                pos = {w.text: w.x0 for w in line.words}
                x = [pos[h] - (25 if h == "Prijs" else 4) for h in HEADER]
                continue
            if x is None or line.text.startswith("POA"):
                continue
            cols = [[] for _ in HEADER]
            for w in line.words:
                i = max(j for j, start in enumerate(x) if w.x0 >= start - 1) if w.x0 >= x[0] - 1 else 0
                cols[i].append(w.text)
            c = dict(zip(HEADER, (" ".join(v) for v in cols)))
            price = N.parse_price(c["Prijs"])
            if price is None:
                if c["Omschrijving"] and not any(c[h] for h in HEADER[1:]):
                    if line.words[0].x0 < x[0] + 8:
                        section, group = c["Omschrijving"], ""
                    else:
                        group = c["Omschrijving"]
                continue
            rows.append(self.make_row(section, group, c, price))
        return rows

    def make_row(self, section, group, c, price):
        desc = c["Omschrijving"]
        species = N.find_species(f"{desc} {section}") or N.find_species(group)
        weight = N.find_weight(desc) or N.find_weight(group)
        box = N.box_type(desc) or N.box_type(group)
        wrapped = "Wrapped Top Layer" if re.search(r"(?i)wrapped top layer", desc) else ""

        # variety: trade name in brackets when there is one, otherwise the code / name
        name = re.sub(r"(?i)\b\d+(?:[.,]\d+)?\s*(x\s*\d+\s*gr?|kg)\b|\bno label\b|\bcarrybag\b|\bcarton\b|"
                      r"\bpolycote\b|\bwrapped top layer\b|\b(OT|TC|LS)\b|\bII?\b(?=\s|$)", " ", desc)
        if species:
            name = remove_alias(name, species)
        m = re.search(r"\(([^)]*)\)", name)
        variety = m[1] if m else name
        variety = " ".join(re.sub(r"[()]", " ", variety).split())
        variety = re.sub(r"\bDelta S\.$", "Delta Seedless", variety)
        if species == "Grapes":
            colour = next((v for k, v in COLOURS.items() if re.search(rf"(?i)\b{k}\b", group)), "")
            seedless = " Seedless" if re.search(r"(?i)zonder pit", group) and "los" not in group.lower() else ""
            variety = f"{colour}{seedless} {variety}".strip()
        pack = N.pack_detail(desc) or ""
        return self.row(
            specie=species or desc, variety=variety, cat=c["Klasse"], brand=c["Merk"],
            size=c["Maat"].strip(), origin=c["LvO"], box_pp=N.to_number(c["PP"]), price=price,
            weight=weight, detail=" ".join(v for v in (box, wrapped, pack if species != "Grapes" else "") if v))
