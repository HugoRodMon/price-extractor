"""Frutos Tropicales Europe: pdf table.

    MANGO                                                                          <- section
    Variety         Origin Brand    Weight Packing Size  CPP Remark   Price        <- header
    Kent ''By Air'' Peru   Flamingo 5,5 kg Carton  8-9   88           P.O.R.
    GREENSKINS                                                                     <- sub-section
"""
import re

from .. import normalize as N
from ..base import Supplier, register
from ._common import remove_alias
from ._pdf import Columns, is_header

HEADER = ["Variety", "Origin", "Brand", "Weight", "Packing", "Size", "CPP", "Remark", "Price"]


@register
class FrutosTropicales(Supplier):
    name = "Frutos Tropicales"
    final_file = "Frutos Tropicales.xlsx"
    match_names = ["frutos tropicales", "frutos"]
    match_text = ["fteurope", "frutos tropicales"]
    layout_hints = [r"variety\s+origin\s+brand\s+weight\s+packing\s+size\s+cpp\s+remark\s+price"]
    origin_style = "name"
    species_names = {"Dragon Fruits": "Pithaya", "Passion Fruits": "Passion fruits"}

    def parse(self, doc):
        rows, section, sub, cols = [], "", "", None
        for line in doc.lines:
            if is_header(line, "variety", "origin", "price"):
                cols = Columns.from_header(line, HEADER)
                continue
            if cols is None:
                continue
            if line.text.isupper() and len(line.words) <= 2:
                if line.size > 7:
                    section, sub = line.text, ""
                else:
                    sub = line.text
                continue
            c = cols.split(line)
            price = N.parse_price(c.get("Price"))
            if price is None or not c.get("Variety"):
                continue
            variety, type_ = c["Variety"], ""
            m = re.search(r"""['"]{1,2}\s*by air\s*['"]{0,2}""", variety, re.I)
            if m:
                type_, variety = "BY AIR", variety[:m.start()] + variety[m.end():]
            m = re.search(r"(?i)-?\s*ready to eat", variety)
            if m:
                type_, variety = "RTE", variety[:m.start()] + variety[m.end():]
            variety = " ".join(variety.split())
            species = N.find_species(variety)
            if species:
                variety = remove_alias(variety, species) or variety
            rows.append(self.row(
                specie=f"{c['Variety']} {sub} {section}", variety=variety, origin=c["Origin"],
                brand=c["Brand"], weight=N.parse_weight(c["Weight"]),
                packaging=N.packaging_from(c["Packing"]), size=c["Size"],
                box_pp=N.to_number(c["CPP"]), price=price, type=type_))
        return rows
