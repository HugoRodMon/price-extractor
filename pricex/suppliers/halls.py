"""Halls BV: WhatsApp message.

    *Hass Chile*
    10kg

    Size 20    32.00e
"""
import re

from .. import normalize as N
from ..base import Supplier, register
from ._common import box_material, clean, describe


@register
class Halls(Supplier):
    name = "Halls"
    final_file = "HALLS BV.xlsx"
    match_names = ["halls"]
    match_text = ["halls bv"]
    layout_hints = [r"^size \S+\.?\s+(\d+p\s+)?\d+[.,]\d{2}e\s*$", r"subject to demand"]
    file_types = (".txt",)
    origin_style = "code"
    origin_overrides = {"Kenya": "KEN", "South Africa": "RSA", "Chile": "CL", "Peru": "PE"}

    def parse(self, doc):
        rows, head = [], None
        for raw in doc.text.splitlines():
            line = clean(raw)
            if not line:
                continue
            if raw.strip().startswith("*") and raw.strip().endswith("*"):
                head = describe(line)
                continue
            if head and re.fullmatch(r"(?i)\d+(?:[.,]\d+)?\s*kg", line):
                head["weight"] = N.to_number(line)
                continue
            m = re.match(r"(?i)size\s*([\w+/-]+)\.?\s+(?:\d+\s*p\s+)?(\d+(?:[.,]\d+)?)\s*e\b", line)
            if not (head and m):
                continue
            weight = head["weight"]
            rows.append(self.row(
                specie=head["species"] or head["variety"], variety=head["variety"],
                origin=head["origin"], size=m[1], weight=weight,
                packaging=box_material(head["species"] or head["variety"], weight),
                price=N.parse_plain_price(m[2])))
        return rows
