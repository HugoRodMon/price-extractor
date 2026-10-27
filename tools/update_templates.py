"""Copy the columns and tabs of the final (OneDrive) Excel files, so the extractor's output
matches them. Run again whenever you add a column or a tab to a final file.

    python tools/update_templates.py "C:/Users/.../OneDrive/Precios"
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pricex import templates  # noqa: E402
from pricex.base import suppliers  # noqa: E402

if len(sys.argv) != 2:
    sys.exit(__doc__)
found, missing = templates.build(sys.argv[1], suppliers())
print("Updated:", ", ".join(found) or "-")
if missing:
    print("Final file not found for:", ", ".join(missing))
