"""Compare what the extractor gets from a price file with what is already in the final Excel.

    python tools/check.py "Kissao 26-10-2026.pdf" "Kissao.xlsx"
    python tools/check.py "PRICES EXAMPLES"            (every raw file in the folder against its final file)

Useful after changing a parser, or when a supplier changes its layout.
"""
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import openpyxl  # noqa: E402

from pricex.extractor import extract_file  # noqa: E402
from pricex.output import BASE, size_key  # noqa: E402


def number(v):
    """Prices are sometimes stored as text ('22.00') in the final files."""
    try:
        return float(str(v).replace(",", "."))
    except (TypeError, ValueError):
        return None


def final_prices(xlsx, date):
    """(variety, size, price) of every price in the final file on that date, long or wide layout."""
    wb = openpyxl.load_workbook(xlsx, read_only=True, data_only=True)
    out = Counter()
    for ws in wb:
        rows = ws.iter_rows(values_only=True)
        headers = [str(h).strip() if h is not None else "" for h in next(rows, ())]
        up = [h.upper() for h in headers]
        if "DATE" not in up:
            continue
        for r in rows:
            if not r or r[0] is None or not hasattr(r[0], "date") or r[0].date() != date.date():
                continue
            get = lambda name: r[up.index(name)] if name in up and up.index(name) < len(r) else None  # noqa: E731
            var = str(get("VARIETY") or "").strip().lower()
            if "PRICE EUR" in up:
                p = number(get("PRICE EUR"))
                if p is not None:
                    out[(var, size_key(get("SIZE") or "N/S"), round(p, 2))] += 1
            else:
                for i, h in enumerate(headers):
                    if h and h.upper() not in BASE and i < len(r) and isinstance(r[i], (int, float)):
                        out[(var, size_key(h), round(float(r[i]), 2))] += 1
    return out


def check(raw, final, verbose=True):
    res, err = extract_file(raw)
    if err:
        print("ERROR:", err)
        return
    got = Counter((str(r.variety).lower(), size_key(r.size), round(r.price, 2)) for r in res.rows)
    want = final_prices(final, res.date)
    # match on size+price first (variety names are often written differently)
    loose_got = Counter((k[1], k[2]) for k in got.elements())
    loose_want = Counter((k[1], k[2]) for k in want.elements())
    both = sum((loose_got & loose_want).values())
    print(f"{Path(raw).name}: extracted {len(res.rows)}, final file has {sum(want.values())}, "
          f"matching size+price {both}")
    if verbose:
        miss = loose_want - loose_got
        extra = loose_got - loose_want
        if miss:
            print("  in final file but not extracted:",
                  sorted({k for k in want if (k[1], k[2]) in miss}, key=str))
        if extra:
            print("  extracted but not in final file:",
                  sorted({k for k in got if (k[1], k[2]) in extra}, key=str))
        for w in res.warnings:
            print("  warning:", w)
        if res.skipped:
            print("  skipped (not tracked):", res.skipped)


if __name__ == "__main__":
    import re
    from pricex.base import suppliers

    args = sys.argv[1:]
    if len(args) == 1 and Path(args[0]).is_dir():
        folder = Path(args[0])
        by_name = {s.name: s for s in suppliers()}
        from pricex.extractor import identify
        for f in sorted(folder.iterdir()):
            if not re.search(r"\d{2}-\d{2}-\d{4}", f.name):
                continue
            s = identify(f)
            if s and (folder / s.final_file).exists():
                check(f, folder / s.final_file, verbose="-v" in sys.argv)
            else:
                print(f"{f.name}: no supplier / final file")
    else:
        check(args[0], args[1])
