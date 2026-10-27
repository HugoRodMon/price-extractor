"""Avoclear Europe: pdf table.

    AVOCADO HASS                                                    <- section
    Product  Origin    Brand    Cat KG  PP   Size Remark  Price     <- header
    Hass     Colombia  generic  1   4   264  12-14        € 12,00
"""
from .. import normalize as N
from ..base import Supplier, register
from ._common import box_material
from ._pdf import Columns, is_header

HEADER = ["Product", "Origin", "Brand", "Cat", "KG", "PP", "Size", "Remark", "Price"]


@register
class Avoclear(Supplier):
    name = "Avoclear"
    final_file = "Avoclear Europe.xlsx"
    match_names = ["avoclear"]
    match_text = ["avoclear"]
    origin_style = "name"

    def parse(self, doc):
        rows, section, cols = [], "", None
        for line in doc.lines:
            if is_header(line, "product", "origin", "price"):
                cols = Columns.from_header(line, HEADER)
                continue
            if cols is None:
                continue
            c = cols.split(line)
            price = N.parse_price(c.get("Price"))
            if price is None:
                if line.text.isupper() and len(line.words) <= 4:          # AVOCADO HASS, MANGO...
                    section = line.text
                continue
            origin, brand, detail = c["Origin"], c["Brand"], ""
            pack = N.pack_detail(brand)
            if pack:                                                      # 14x700gr in the brand column
                detail, brand = pack, origin
                origin = ""
            weight = N.parse_weight(c["KG"])
            species = N.find_species(f"{c['Product']} {section}")
            rows.append(self.row(
                specie=f"{c['Product']} {section}", variety=c["Product"] if c["Product"].lower() != "avocado" else "Avocado",
                origin="" if origin.lower() == "various" else origin, brand=brand,
                cat=N.to_number(c["Cat"]), weight=weight, box_pp=N.to_number(c["PP"]),
                size=c["Size"] or "N/S", price=price, detail=detail,
                packaging=box_material(species, weight)))
        return rows
