"""Price extractor, command line version (the window version is app.py).

    python extract.py "Kissao 27-10-2026.pdf" "Verdi 27-10-2026.xlsx" ... -o "output folder"
    python extract.py "C:/.../folder with today's price files" -o "output folder"
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from pricex.pipeline import SUPPORTED, run  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("inputs", nargs="+", type=Path, help="price files or folders")
    ap.add_argument("-o", "--output", type=Path, default=Path("output"), help="output folder")
    args = ap.parse_args()

    files = []
    for p in args.inputs:
        if any(c in p.name for c in "*?["):             # Windows cmd doesn't expand wildcards
            files += sorted(p.parent.glob(p.name))
        elif p.is_dir():
            files += sorted(f for f in p.iterdir() if f.suffix.lower() in SUPPORTED)
        else:
            files.append(p)
    report = run(files, args.output)
    print(report.text())
    return 0 if not report.errors else 1


if __name__ == "__main__":
    sys.exit(main())
