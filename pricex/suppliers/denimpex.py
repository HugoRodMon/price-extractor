"""Denimpex: pdf table, one row per size.

    Citrus                                                                             <- big section
    Limes                                                                              <- species section
    Product Origin Cat. Size Brand       Weight Packaging  PP  Price   Location Expected
    Tahiti  BR     I    54   Cloe / Mood 4,0    Carton     240 € 16,00 Waddinxveen
    Valencia ZA    II   48   Groenheuwel 15,0   Telescopic 80  € 8,00  Waddinxveen MRL FREE !!
"""
import re

from .. import normalize as N
from ..base import Supplier, register
from ._common import remove_alias


@register
class Denimpex(Supplier):
    name = "Denimpex"
    final_file = "DENIMPEX.xlsx"
    match_names = ["denimpex"]
    match_text = ["denimpex"]
    origin_style = "source"
    default_packaging = ""           # the final file only writes Carton when the list says so

    def parse(self, doc):
        rows, big, small, x = [], "", "", None
        for line in doc.lines:
            texts = [w.text for w in line.words]
            if texts[:1] == ["Product"] and "Origin" in texts:
                pos = {w.text: w.x0 for w in line.words}
                x = {"origin": pos["Origin"] - 4, "cat": pos["Cat."] - 4, "size": pos["Size"] - 4,
                     "brand": pos["Brand"] - 4, "weight": pos["Weight"] - 4, "pack": pos["Packaging"] - 4,
                     "pp": pos["PP"] - 8, "price": pos["PP"] + 20, "location": pos["Price"] + 22,
                     "remark": pos.get("Expected", 515) - 20}
                continue
            if line.size >= 12:
                big, small = line.text, ""
                continue
            if line.size >= 9:
                small = line.text
                continue
            if x is None or not any(x["origin"] <= w.x0 < x["cat"] for w in line.words):
                continue
            if not any(w.x0 < x["origin"] for w in line.words):
                continue
            rows.append(self.make_row(line, x, big, small))
        return [r for r in rows if r]

    def make_row(self, line, x, big, small):
        def part(a, b):
            return " ".join(w.text for w in line.words if x[a] <= w.x0 < x[b])

        price = N.parse_price(part("price", "location"))
        if price is None:
            return None                                   # exp / POR
        product = " ".join(w.text for w in line.words if w.x0 < x["origin"])
        species = N.find_species(product) or N.find_species(small) or N.find_species(big)
        variety = remove_alias(product, species) if species and N.find_species(product) else product
        packing = part("pack", "pp")
        pack = N.pack_detail(packing)
        detail = pack or ("" if packing.lower() == "carton" else N.box_type(packing) or packing.capitalize())
        remark = " ".join(w.text for w in line.words if w.x0 >= x["remark"])
        if re.search(r"(?i)light coloured", remark):
            detail = " ".join(v for v in (detail, "Light coloured") if v)
        return self.row(
            specie=species or f"{product} {small} {big}", variety=variety.capitalize() if variety.islower() else variety,
            origin=part("origin", "cat"), cat=part("cat", "size"), size=part("size", "brand") or "N/S",
            brand=part("brand", "weight"), weight=N.to_number(part("weight", "pack")),
            packaging="Carton" if packing.lower() == "carton" else "", box_pp=N.to_number(part("pp", "price")),
            price=price, detail=detail)
