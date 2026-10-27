"""Base class for supplier parsers.

To add a supplier, copy one of the files in pricex/suppliers/, change the settings at the top
and write parse(). It's picked up automatically.
"""
import copy
import re

from . import normalize as N
from .model import PriceRow


class Supplier:
    # ---- identity
    name = ""                 # tab name in the combined file / name of the separate file
    final_file = ""           # the Excel the prices end up in (OneDrive); used to build the column template
    match_names = []          # lowercase words looked for in the file name
    match_text = []           # lowercase words looked for in the file content (fallback)
    file_types = (".pdf",)

    # ---- output style
    layout = "long"           # "long": one row per size, a tab in the combined file
                              # "wide": a separate file with one tab per species and a column per size
    origin_style = "source"   # "source" (as written), "name" (Brazil), "NAME" (BRAZIL), "code" (BR)
    origin_overrides = {}     # country name -> text to write, e.g. {"Kenya": "KEN"}
    species_names = {}        # our species name -> how this supplier's Excel writes it
    sheet_names = {}          # wide only: species -> tab, e.g. {"Pomelos": "GRAPEFRUITS"}
    upper_species = False     # write SPECIE in capitals
    default_packaging = "Carton"
    default_cat = ""          # CAT written when the price list doesn't say (e.g. 1)

    def parse(self, doc):
        """Return a list of PriceRow. `specie` may be any text naming the product
        (section title, product name...): it's resolved to a species afterwards."""
        raise NotImplementedError

    # ---- helpers for parsers
    @staticmethod
    def row(**kw):
        return PriceRow(**kw)

    # ---- post-processing shared by all suppliers
    def finalize(self, rows, result):
        out = []
        for r in rows:
            if r.price is None or r.price <= 0:
                continue
            # "Fairtrade Limes" -> species Limes, TYPE FAIRTRADE (labels listed in species.json -> type_words)
            tags, (r.specie, r.variety, r.type) = N.take_type_words(r.specie, r.variety, r.type)
            if tags:
                r.type = " ".join([r.type] + [t for t in tags if t not in r.type.split()]).strip()
            raw = r.specie
            label = " ".join(str(x) for x in (raw, r.variety) if x).strip()
            if N.is_ignored(label):
                continue
            species = (N.find_species(raw) or N.species_from_variety(r.variety)
                       or N.species_from_variety(raw))
            if not species:
                result.skipped.append(f"{label} ({r.origin}, {r.size}, €{r.price:g})")
                continue
            r.specie = self.species_names.get(species, species)
            if self.upper_species:
                r.specie = r.specie.upper()
            r.variety = re.sub(r"\s+", " ", str(r.variety or "")).strip() or r.specie
            r.packaging = r.packaging or self.default_packaging
            r.cat = r.cat if r.cat not in ("", None) else self.default_cat
            sizes = N.split_sizes(r.size, species)
            # "Dom. Rep. / Colombia": one row per origin, like grouped sizes
            for origin in N.split_origins(r.origin):
                for s in sizes:
                    c = copy.copy(r)
                    c.origin = N.format_origin(origin, self.origin_style, self.origin_overrides)
                    c.group = str(r.size) if len(sizes) > 1 else ""
                    c.size = s if s not in ("", None) else "N/S"
                    out.append(c)
        return remove_duplicates(check_prices(out, result), result)


# ---------------------------------------------------------------- price sanity checks

OUTLIER = 3          # a price 3x above or below the usual price of the same product is suspicious


def product_key(r):
    """Same product = same species, variety, origin, weight, box pp, packing and detail (brand and size may differ)."""
    return (str(r.specie).lower(), str(r.variety).lower(), str(r.origin).lower(), r.weight, r.box_pp,
            str(r.packaging).lower(), str(r.detail).lower(), str(r.type).lower())


def check_prices(rows, result):
    """Catch typos like Palmer 6/7 at €76 when every other Palmer 4kg is €6-7.
    If the same size is already offered at a normal price the row is dropped, otherwise it's
    kept and flagged (red cell in the Excel). Both are listed in the report."""
    from statistics import median
    groups = {}
    for r in rows:
        groups.setdefault(product_key(r), []).append(r)
    drop = set()
    for group in groups.values():
        if len(group) < 3:
            continue
        for r in group:
            others = [o.price for o in group if o is not r and o.price != r.price]
            if len(others) < 2:
                continue
            usual = median(others)
            if usual <= 0 or 1 / OUTLIER < r.price / usual < OUTLIER:
                continue
            label = f"{r.specie} {r.variety} {r.origin} {r.weight or ''}kg size {r.size} at €{r.price:g}"
            same_size = [o for o in group if o is not r and str(o.size) == str(r.size)
                         and 1 / OUTLIER < o.price / usual < OUTLIER]
            if same_size:
                drop.add(id(r))
                result.corrections.append(
                    f"dropped {label}: the same product is €{min(others):g}-{max(others):g}, "
                    f"and size {r.size} is already there at €{same_size[0].price:g}")
            else:
                r.flag = f"usual price €{usual:g}"
                result.corrections.append(
                    f"CHECK {label}: the same product is usually €{usual:g} (kept, marked red)")
    return [r for r in rows if id(r) not in drop]


def remove_duplicates(rows, result):
    seen, out = set(), []
    for r in rows:
        key = tuple(getattr(r, f) for f in ("specie", "variety", "origin", "size", "weight", "brand", "cat",
                                            "packaging", "box_pp", "price", "detail", "type"))
        if key in seen:
            continue
        seen.add(key)
        out.append(r)
    if len(out) < len(rows):
        result.corrections.append(f"removed {len(rows) - len(out)} identical row(s)")
    return out


_REGISTRY = []


def register(cls):
    _REGISTRY.append(cls())
    return cls


def suppliers():
    if not _REGISTRY:
        from . import suppliers as _pkg  # noqa: F401  (imports every module, which registers itself)
    return list(_REGISTRY)
