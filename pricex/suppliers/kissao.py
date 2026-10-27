"""Kissao: pdf table. Prices are often printed on their own line just above the product row.

    Product        Origin Variety Size      Packing Boxes / pallet Price Availability
                                                                   € 9,50          <- price line
    Pomelos white  China  Honey   8/9/10/11 10kg    75                             <- its product
    Lime           Brazil Tahiti  42        4,5Kg   240            P.O.R ETA 28/10
"""
import re

from .. import normalize as N
from ..base import Supplier, register
from ._common import remove_alias
from ._pdf import Columns, is_header

HEADER = ["Product", "Origin", "Variety", "Size", "Packing", "Boxes / pallet", "Price", "Availability"]


@register
class Kissao(Supplier):
    name = "Kissao"
    final_file = "Kissao.xlsx"
    match_names = ["kissao"]
    match_text = ["kissao"]
    origin_style = "name"
    species_names = {"Passion Fruits": "Passion fruit", "Sweet Potatoes": "Sweet potato",
                     "Granadillas": "Granadilla", "Tamarinds": "Tamarind", "Mangosteens": "Mangosteen",
                     "Guavas": "Guava", "Dragon Fruits": "Pithaya"}

    def parse(self, doc):
        rows, cols, pending = [], None, None
        for line in doc.lines:
            if is_header(line, "product", "origin", "price"):
                cols = Columns.from_header(line, HEADER)
                pending = None
                continue
            if cols is None:
                continue
            c = cols.split(line)
            price_text = f'{c["Boxes / pallet"]} {c["Price"]}'     # the € sign can sit left of the column
            if not c["Product"] and c["Price"]:               # price printed above its row
                pending = N.parse_price(price_text)
                continue
            if not (c["Product"] and c["Origin"]):
                continue
            price = N.parse_price(price_text)
            if price is None and pending is not None and not re.search(r"(?i)p\.?o\.?r", c["Price"]):
                price = pending
            pending = None
            if price is None:
                continue
            rows.append(self.make_row(c, price))
        return rows

    def make_row(self, c, price):
        product, variety, type_, brand = c["Product"], c["Variety"], "", ""
        m = re.search(r"\s+(\d+(?:\s*[/-]+\s*\d+)+)$", variety)    # long size groups start left of the Size column
        if m:
            c["Size"] = (m[1] + " " + c["Size"]).strip()
            variety = variety[:m.start()]
        for text in (product, variety):
            m = re.search(r"(?i)\bby (air|boat|sea)\b", text)
            if m:
                type_ = m[0].upper()
        product = re.sub(r"(?i)\bby (air|boat|sea)\b", "", product).strip()
        variety = re.sub(r"(?i)\bby (air|boat|sea)\b", "", variety).strip()
        if re.search(r"(?i)mrl free", product):
            brand = "MRL Free"
            product = re.sub(r"(?i)mrl free", "", product).strip()
        species = N.find_species(product)
        if not variety and species:
            rest = remove_alias(re.sub(r"(?i)young coco", "", product), species).strip()
            variety = rest.title() if rest and rest.lower() not in ("white", "red") else ""
        packing = c["Packing"]
        size = re.sub(r"(?i)(\d+)\s*g?\s*\+", r"\1+", c["Size"]).strip()
        pack = N.pack_detail(packing)
        return self.row(
            specie=product, variety=variety, origin=c["Origin"], size=size or "N/S",
            weight=N.parse_weight(packing), packaging=N.packaging_from(packing),
            box_pp=N.to_number(c["Boxes / pallet"]), price=price, brand=brand, type=type_,
            detail=pack or "")
