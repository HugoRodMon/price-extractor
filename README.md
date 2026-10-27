# Price Extractor

Reads the daily price lists (pdf, WhatsApp .txt, saved web page .mhtml, Excel) and writes the prices
in the same columns as the final Excel files on OneDrive, ready to paste.

## Daily use

1. Double-click **Price Extractor.bat**.
2. Drop the day's price files on the window (or a whole folder). The supplier of each file is shown.
3. Click **Extract prices**.

The output folder gets:

| File | What |
|---|---|
| `Prices DD-MM-YYYY.xlsx` | One tab per supplier whose final file is a single table (Anaco Greeve, Kissao, Timerfruit...) |
| `<Supplier> DD-MM-YYYY.xlsx` | One file per supplier whose final file has **a tab per species** (Verdi, Olympic, Van der Lans, Jaguar, Everest, Fruitfactor, Westfalia). Same tabs and size columns as the final file. These are listed in the pop-up at the end. |

Yellow header cells are columns or tabs that don't exist in the final file yet (a new size, a new species).

The log at the bottom also lists:
- **Products with a price that were NOT extracted**: a product the extractor doesn't know. Add it to
  `pricex/data/species.json` (see below) and run again.
- **NOT PROCESSED**: files whose supplier wasn't recognised, or whose layout changed so much the parser failed.

Command line alternative: `python extract.py "folder or files" -o "output folder"`

## Rules applied to every supplier

- Only rows with a numeric price ("POR", "On request", "exp", dates... are skipped).
- Grouped sizes are split into one row per size: `6/7`, `8-9-10`, `12 & 14`.
  A range follows the species' real sizes (`size_series` in `species.json`): mangoes `6-12` -> 6, 7, 8, 9, 10, 12;
  avocados `10--24` -> 10, 12, ... 24. A range Excel turned into a date (`01/10/2020` = "10-20") is read back as 10 to 20.
  Species without a series only expand `a--b`; `6-8` stays 6 and 8.
  Kept as one size: `Mix 12-16`, mandarin counts like `2-105`.
- `250g +`, `250+gr` become `250+`.
- Several origins are split the same way: `Dom. Rep. / Colombia` -> one row for Dominican Republic and one for
  Colombia (also `CH/COL/GUA`, `Ecua / Col`). Only split when every part is a known country (`origins.json`).
- **Price check**: each price is compared with the other offers of the same product (species, variety, origin,
  weight, box pp, packing; any brand or size). A price 3x above or below the usual one is a typo
  (e.g. Torres' Palmer 6/7 at €76 when the rest is €6-7):
  - if the same size is already offered at a normal price, the wrong row is **dropped**;
  - otherwise it's **kept with the price cell in red**.
  Both appear under "PRICE CHECKS" in the log. The 3x limit is `OUTLIER` in `pricex/base.py`.
- Rows that are exactly identical are kept only once (the log says how many were removed). In the per-species files, a group goes into its
  own column if the final file already has one (e.g. Verdi plums `45/50`).
- Pack sizes like `12x100`, `10x500gr` go to DETAIL; the size becomes `N/S`.
- Empty variety becomes the species name. Species are written in plural (`Mangoes`, `Avocados`).
- "By air", "RTE"... go to TYPE (or DETAIL, depending on what that supplier's final file does).
- Origins are written the way each final file does: codes (`RSA`, `BR`) or names (`South Africa`).

## When something changes

**A new product** (e.g. "Rambutan" shows up as not extracted): open `pricex/data/species.json` and add it under
`species`, with the words suppliers use for it:

```json
"Rambutans": ["rambutan", "rambutans"],
```

Products you never want go under `ignore`. Labels that belong in the TYPE column instead of the name go under
`type_words` (e.g. `"fairtrade": "FAIRTRADE"`: "Fairtrade Limes" -> Limes with TYPE = FAIRTRADE). Varieties that identify a species on their own (when a supplier
writes just "Keitt") go under `varieties`.

**A new country spelling**: add it to `pricex/data/origins.json`.

**You added a column or a tab to a final Excel**: copy the final files to a folder and run

```
python tools/update_templates.py "folder with the final files"
```

A final file with more than one tab automatically produces a separate file; one tab means a tab in the combined file.

**A supplier changed its layout, or a new supplier**: each supplier is one file in `pricex/suppliers/`
(e.g. `kissao.py`). The top of each file shows what the layout looks like. To add a supplier, copy the one
whose layout is most similar, change `name`, `final_file`, `match_names` (words in the file name) and the
reading part. It's picked up automatically.

Two tools help:

```
python tools/pdf_lines.py "Supplier 27-10-2026.pdf"                      # how the pdf is seen, with positions
python tools/check.py "Supplier 27-10-2026.pdf" "SUPPLIER final.xlsx"    # compare with what's in the final file
python tools/check.py "folder"                                           # check every price file in a folder
```

`check.py` compares sizes and prices against the rows already in the final Excel for the same date, so
after typing a day by hand you can confirm the extractor would have produced the same.

## Releases and auto-update (for the team)

The team uses `PriceExtractor.exe` from the GitHub Releases page. It checks GitHub every time it opens and,
when there is a newer release, offers to update: it downloads the new exe, replaces itself and restarts.

**Publishing a new version** (after committing and pushing your changes):

```
git tag v1.1.0
git push origin v1.1.0
```

The GitHub Action (`.github/workflows/release.yml`) builds the exe on a Windows machine, checks that it starts
and loads every supplier, and publishes it as release `v1.1.0`. Versions are compared as numbers
(v1.10.0 is newer than v1.9.0); always tag higher than the last release. The Action writes the version and the
repository name into `version.py` itself; you never edit them.

**For the team, once:** download `PriceExtractor.exe` from the latest release and put it in a folder they can
write to (Desktop, Documents, `C:\Users\<name>\PriceExtractor`), not in `C:\Program Files`. The first time,
Windows SmartScreen may say "Windows protected your PC": More info -> Run anyway. Updates don't ask again.

Notes:
- The repository must be **public** for the update check to work without passwords.
- `species.json`, `origins.json` and the column templates are inside the exe: to change them for everyone,
  change them in the repository and publish a new version.
- Settings (output folder) are kept in `%APPDATA%\PriceExtractor`, so they survive updates.
- `PriceExtractor.exe --update` updates without asking; `PriceExtractor.exe --extract <folder> -o <out>`
  runs without a window and writes `report.txt`.
- Build locally (optional): `pip install -r requirements.txt pyinstaller`, then `pyinstaller PriceExtractor.spec`.

## Files

```
app.py                  the window
extract.py              command line
pricex/
  suppliers/            one parser per supplier (+ _common.py, _pdf.py helpers)
  data/species.json     species names, aliases, ignored products
  data/origins.json     countries and their codes/spellings
  data/templates.json   columns and tabs of each final file (made by tools/update_templates.py)
  normalize.py          shared rules (prices, sizes, weights, origins)
  output.py             Excel writing
tools/                  check.py, pdf_lines.py, update_templates.py
```

Needs: `pip install pdfplumber openpyxl beautifulsoup4 tkinterdnd2`
