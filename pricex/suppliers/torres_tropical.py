"""Torres Tropical: web price list saved from the browser (.mhtml)."""
import re

from bs4 import BeautifulSoup

from .. import normalize as N
from ..base import Supplier, register


@register
class TorresTropical(Supplier):
    name = "Torres Tropical"
    final_file = "Torres Tropical.xlsx"
    match_names = ["torres"]
    match_text = ["torrestropical"]
    file_types = (".mhtml", ".html")
    origin_style = "source"
    default_packaging = ""

    def parse(self, doc):
        soup = BeautifulSoup(doc.html, "html.parser")
        rows = []
        for group in soup.select("tbody.productGroup"):
            product = ""
            for tr in group.find_all("tr", recursive=False):
                if tr.find("td", class_="productGroupCol"):
                    product = cell(tr, "productGroupCol")
                price = N.parse_plain_price(cell(tr, "priceCol"))
                if price is None:
                    continue                                    # "On request"
                specie, type_ = split_product(product)
                variety = cell(tr, "varietyCol")
                size = cell(tr, "sizeCol")
                detail = ""
                if re.fullmatch(r"\d+\s*x\s*\d+", size, re.I):   # 12x100 is a pack, not a size
                    detail = re.sub(r"\s+", "", size).lower() + "g"
                    size = "N/S"
                rows.append(self.row(
                    specie=specie, variety="" if variety == "-" else variety,
                    origin=cell(tr, "originCol"), size="" if size == "-" else size,
                    weight=N.to_number(cell(tr, "weightCol")), brand=cell(tr, "brandCol"),
                    cat=N.to_number(cell(tr, "classCol")) or cell(tr, "classCol"),
                    box_pp=N.to_number(cell(tr, "cppCol")), price=price, detail=detail, type=type_))
        return rows


def cell(tr, cls):
    td = tr.find("td", class_=cls)
    return " ".join(td.get_text(" ", strip=True).split()) if td else ""


def split_product(text):
    """'Mango by Air' -> ('Mango', 'by Air'), 'Bio Turmeric' -> ('Turmeric', 'Bio')."""
    text = " ".join(text.split())
    types = []
    for prefix in ("Bio", "Organic", "Fair Trade", "Fairtrade"):
        if text.lower().startswith(prefix.lower() + " "):
            types.append(prefix)
            text = text[len(prefix):].strip()
    m = re.search(r"\b(by air|by sea|by boat|rte|ready to eat)\b.*$", text, re.I)
    if m:
        types.append(m.group())
        text = text[:m.start()].strip()
    return text, " ".join(types)
