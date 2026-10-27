"""Kraaijeveld: WhatsApp message.

    🥑 Avocado| Hass | CO | 10kg
    4 pall             size 24          € 18.00
    2 pall             MIX 12-16    € 22.00
"""
import re

from .. import normalize as N
from ..base import Supplier, register
from ._common import box_material, clean, describe


@register
class Kraaijeveld(Supplier):
    name = "KRAAIJEVELD"
    final_file = "KRAAIJEVELD.xlsx"
    match_names = ["kraaijeveld"]
    match_text = ["kraaijeveld"]
    file_types = (".txt",)
    origin_style = "source"

    def parse(self, doc):
        rows, head = [], None
        for raw in doc.text.splitlines():
            line = clean(raw)
            if not line:
                continue
            if "|" in line:
                parts = [p.strip() for p in line.split("|")]
                parts = [p for p in parts if not re.match(r"(?i)eta\b", p)]
                type_ = "RTE" if any(re.fullmatch(r"(?i)rte|ready to eat", p) for p in parts) else ""
                parts = [re.sub(r"(?i)\b(rte|ready to eat)\b", "", p).strip() for p in parts]
                various = any(p.upper() == "DIV" for p in parts)          # DIV = various origins
                head = describe(" | ".join(p for p in parts if p and p.upper() != "DIV"))
                head["type"] = type_
                if various:
                    head["origin"] = "Div"
                continue
            m = re.search(r"(?i)(size\s*\S+|mix\s*[\d\s-]+?)\s*€\s*(\d+(?:[.,]\d+)?)", line)
            if not (head and m):
                continue
            size = re.sub(r"(?i)^size\s*", "", m[1]).strip()
            weight = head["weight"]
            rows.append(self.row(
                specie=head["species"] or head["variety"], variety=head["variety"],
                origin=head["origin"], size=size, weight=weight,
                packaging=box_material(head["species"] or head["variety"], weight),
                price=N.parse_plain_price(m[2]), type=head["type"]))
        return rows
