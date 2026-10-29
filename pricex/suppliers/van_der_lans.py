"""Van der Lans: pdf with a grid per species. Prices are plain numbers; '-', 'p.o.r.' and dates (02.11)
mean no price. Some products get a new size line just above them.

    Oranges                                                                   <- species
    Variety  Origin       Package   kg. p.p. 48  56    64    72               <- header with sizes
    Valencia South Africa Telescope 15  80   -   12,50 13,00 13,50  Cat. 1
                                             45  50    55                     <- new sizes for the next row
"""
import re

from .. import normalize as N
from ..base import Supplier, register
from ._common import box_material
from ._pdf import nearest


@register
class VanDerLans(Supplier):
    name = "Van der Lans"
    final_file = "VAN DER LANS.xlsx"
    match_names = ["van der lans", "vanderlans"]
    match_text = ["vanderlans", "van der lans"]
    layout_hints = [r"variety\s+origin\s+package\s+kg\.\s+p\.p\."]
    layout = "wide"
    origin_style = "name"
    species_names = {"Pomelos": "Pomelo"}
    sheet_names = {"Pomelos": "GRAPEFRUITS"}

    def parse(self, doc):
        rows, section, x, sizes = [], "", None, []
        for line in doc.lines:
            texts = [w.text for w in line.words]
            if "Variety" in texts and "p.p." in texts:
                pos = {w.text: w.x0 for w in line.words}
                x = {"origin": pos["Origin"] - 10, "package": pos["Package"] - 4,
                     "kg": pos["kg."] - 9, "pp": pos["p.p."] - 4, "grid": pos["p.p."] + 25}
                sizes = [(w.text, w.xc) for w in line.words if w.x0 >= x["grid"]]
                continue
            if line.size > 9:                                         # species / category title
                section = line.text
                continue
            if x is None:
                continue
            if all(w.x0 >= x["grid"] - 6 for w in line.words):       # sizes for the next product
                sizes = [(w.text, w.xc) for w in line.words]
                continue
            if not any(w.x0 < x["origin"] for w in line.words):
                continue
            rows += self.product_rows(line, x, sizes, section)
        return rows

    def product_rows(self, line, x, sizes, section):
        def part(a, b):
            return " ".join(w.text for w in line.words if x[a] <= w.x0 < x[b]) if b else ""

        variety = " ".join(w.text for w in line.words if w.x0 < x["origin"])
        origin, package = part("origin", "package"), part("package", "kg")
        kg, pp = part("kg", "pp"), part("pp", "grid")
        grid_words = [w for w in line.words if w.x0 >= x["grid"]]
        last_size_x = max((sx for _, sx in sizes), default=0)
        remark = " ".join(w.text for w in grid_words if w.xc > last_size_x + 20)
        cat = re.search(r"Cat\.\s*(\d)", remark)
        detail = "Price/kg" if "price/kg" in remark.lower() else ""

        weights = [N.to_number(v) for v in re.findall(r"\d+(?:,\d+)?", kg.replace("±", ""))[:2]]
        if not re.fullmatch(r"\+?\d+(?:,\d+)?-\d+(?:,\d+)?", kg.strip()):
            weights = weights[:1]                                    # "10,5-11" -> two rows, else one
        if "x" in kg.lower():
            weights = [N.parse_weight(kg)]
        out = []
        for w in grid_words:
            if w.xc > last_size_x + 20:
                break
            price = N.parse_plain_price(w.text) if re.fullmatch(r"\d+,\d{2}", w.text) else None
            if price is None:
                continue
            i = nearest(w.xc, [sx for _, sx in sizes], max_dist=18)
            if i is None:
                continue
            for weight in weights or [None]:
                out.append(self.row(
                    specie=f"{variety} {section}", variety=re.sub(r"\s*\((green|yellow)\)", "", variety),
                    origin=origin, packaging=N.packaging_from(package, default=box_material(
                        N.find_species(f"{variety} {section}"), weight)),
                    detail=" ".join(v for v in (N.box_type(package) or ("Telescope" if "telescope" in package.lower() else ""), detail) if v),
                    weight=weight, box_pp=N.to_number(pp), cat=int(cat[1]) if cat else "",
                    size=sizes[i][0], price=price))
        return out
