"""Westfalia Fruits: WhatsApp message, free format.

    Hass 🥑🥑
    X24 10kg CL €28.00
    Zutano - Maroc 🥑🥑
    Size 12 & 14
    €7.50
    🥭 Mango 4kg
    x6 - Palmer - BR €5.25
"""
import re

from .. import normalize as N
from ..base import Supplier, register
from ._common import box_material, clean, describe

SIZE_RE = re.compile(r"(?i)\bsize\s*([\d\s&/+-]+?)(?=\s*(?:-|€|$))|\bx(\d+)\b")


@register
class Westfalia(Supplier):
    name = "Westfalia"
    final_file = "Westfalia Fruits pricelist.xlsx"
    match_names = ["westfalia"]
    match_text = ["westfalia fruit"]
    layout_hints = [r"^x\d+\s+\d+\s*kg\s+[a-z]{2}", r"netted avo", r"🥑🥑"]
    file_types = (".txt",)
    layout = "wide"
    origin_style = "name"
    default_cat = 1               # the final file has CAT 1 for every product

    def parse(self, doc):
        rows, head, pending_size = [], None, None
        for raw in doc.text.splitlines():
            line = clean(raw)
            if not line or re.match(r"(?i)eta\b", line):
                continue
            price = N.parse_price(line)
            m = SIZE_RE.search(line)
            size = (m[1] or m[2]).strip() if m else None
            if price is None:
                if size and re.match(r"(?i)size\b", line):
                    pending_size = size
                else:
                    head = self.heading(line)
                    pending_size = None
                continue
            if head is None:
                continue
            rest = SIZE_RE.sub(" ", re.sub(r"€\s*[\d.,]+", " ", line))
            d = describe(rest)
            pack = d["pack"] or head["pack"]
            weight = d["weight"] or head["weight"]
            rows.append(self.row(
                specie=head["species"] or d["species"] or head["variety"] or d["variety"],
                variety=head["variety"] or d["variety"], origin=d["origin"] or head["origin"],
                size=size or pending_size or ("N/S" if pack else ""), weight=weight,
                packaging=box_material(head["species"] or d["species"] or head["variety"], weight),
                price=price, detail=pack or "", type=head["type"]))
        return rows

    @staticmethod
    def heading(line):
        type_ = ""
        if re.search(r"(?i)ready to eat|\brte\b", line):
            type_ = "RTE"
            line = re.sub(r"(?i)-?\s*(ready to eat|\brte\b)", " ", line)
        h = describe(line)
        h["type"] = type_
        return h
