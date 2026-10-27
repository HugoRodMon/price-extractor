# PyInstaller recipe for PriceExtractor.exe  ->  pyinstaller PriceExtractor.spec
# (the GitHub Action runs this; you only need it to build locally)
from PyInstaller.utils.hooks import collect_all, collect_submodules

datas = [("pricex/data", "pricex/data")]
binaries = []
# supplier parsers are found at run time, so PyInstaller has to be told about them
hiddenimports = collect_submodules("pricex.suppliers")
for pkg in ("tkinterdnd2", "pypdfium2", "pypdfium2_raw"):
    d, b, h = collect_all(pkg)
    datas += d
    binaries += b
    hiddenimports += h

a = Analysis(
    ["app.py"],
    pathex=["."],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    # big libraries installed on the build machine that the app never uses
    excludes=["pandas", "numpy", "matplotlib", "camelot", "tabula", "fitz", "pymupdf", "IPython", "notebook",
              "cv2", "scipy", "lxml", "pytest", "setuptools"],
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="PriceExtractor",
    console=False,          # a window app, no black console
    upx=False,              # UPX-packed exes trigger antivirus false alarms
    icon=None,
)
