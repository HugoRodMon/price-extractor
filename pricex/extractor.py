"""Identify the supplier of each file and extract its prices."""
import traceback
from pathlib import Path

from . import readers
from .base import suppliers
from .model import Result


def identify(path, doc=None):
    """Supplier for a file: by file name first, then by words in its content."""
    name = Path(path).name.lower()
    for s in suppliers():
        if any(k in name for k in s.match_names):
            return s
    if doc is not None:
        text = doc.text[:5000].lower()
        for s in suppliers():
            if s.match_text and any(k in text for k in s.match_text):
                return s
    return None


def extract_file(path, supplier=None):
    """Returns (Result or None, error message or None)."""
    path = Path(path)
    finals = {s.final_file.lower(): s.name for s in suppliers() if s.final_file}
    if path.name.lower() in finals:
        return None, f"{path.name}: this is the final Excel of {finals[path.name.lower()]}, not a price list"
    try:
        doc = readers.load(path)
    except Exception as e:
        return None, f"{path.name}: could not read the file ({e})"
    supplier = supplier or identify(path, doc)
    if supplier is None:
        return None, f"{path.name}: supplier not recognised"
    date = readers.find_date(doc)
    result = Result(supplier.name, path.name, date)
    if date is None:
        result.warnings.append("no date found in the file name or content")
    if doc.kind == "image":
        result.warnings.append("read from a picture (OCR): compare the rows with the picture before using them; "
                               "red cells are rows with missing or unclear data")
    try:
        rows = supplier.parse(doc)
    except Exception:
        return None, f"{path.name} ({supplier.name}): the parser failed. The layout may have changed.\n{traceback.format_exc(limit=3)}"
    result.rows = supplier.finalize(rows, result)
    if not result.rows:
        result.warnings.append("no prices found (everything on request, or the layout changed)")
    return result, None
