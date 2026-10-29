"""Four Seasons Fruit Supply: WhatsApp message.

    *Mango Kent 4kg BR:*
    Size 6 €4
    *Garlic CN 10kg NW 20x500gr:*
    50+ €23.50
"""
import re

from .. import normalize as N
from ..base import Supplier, register
from ._common import clean, clean_size, describe


@register
class FourSeasons(Supplier):
    name = "Four Seasons"
    final_file = "Four Seasons Fruit Supply.xlsx"
    match_names = ["four seasons", "fourseasons"]
    match_text = ["four seasons", "fourseasons"]
    layout_hints = [r"all prices are fot barendrecht", r"^\*[^*\n]+:\*\s*$"]
    file_types = (".txt",)
    origin_style = "name"
    default_packaging = ""

    def parse(self, doc):
        rows, head = [], None
        for raw in doc.text.splitlines():
            line = clean(raw)
            if not line:
                continue
            if raw.strip().startswith("*") and line.endswith(":"):
                head = describe(line.rstrip(":").replace(" NW", " "))
                head["detail"] = head["pack"]
                if re.search(r"(?i)\bloose\b", head["variety"]):
                    head["detail"] = "Loose"
                    head["variety"] = re.sub(r"(?i)\s*\bloose\b", "", head["variety"]).strip()
                continue
            m = re.match(r"(.*?)\s*€\s*(\d+(?:[.,]\d+)?)", line)
            if not (head and m):
                continue
            size, detail = clean_size(m[1]), head["detail"]
            pack = N.pack_detail(size)
            weight = head["weight"]
            if pack:                                   # "10x1kg" is a pack, not a size
                size, detail = "N/S", pack
                weight = weight or N.parse_weight(pack)
            rows.append(self.row(
                specie=head["species"] or head["variety"], variety=head["variety"],
                origin=head["origin"], size=size, weight=weight,
                price=N.parse_price("€" + m[2]), detail=detail))
        return rows
