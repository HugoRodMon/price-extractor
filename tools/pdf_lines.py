"""Show how the extractor sees a pdf: every line with the x position of each word.
Handy when writing or fixing a supplier parser.

    python tools/pdf_lines.py "Kissao 26-10-2026.pdf" [first_line] [last_line]
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pricex.readers import pdf_lines  # noqa: E402

lines = pdf_lines(sys.argv[1])
a = int(sys.argv[2]) if len(sys.argv) > 2 else 0
b = int(sys.argv[3]) if len(sys.argv) > 3 else len(lines)
for i, line in enumerate(lines[a:b], a):
    print(f"{i:3} p{line.page} size={line.size:<4} " + "  ".join(f"{w.text}@{w.x0:.0f}" for w in line.words))
