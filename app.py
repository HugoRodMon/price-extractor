"""Price extractor - window version. Double-click 'Price Extractor.bat' or run:  python app.py"""
import json
import os
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

sys.path.insert(0, str(Path(__file__).resolve().parent))
import updater  # noqa: E402
from pricex.base import suppliers  # noqa: E402
from pricex.extractor import identify  # noqa: E402
from pricex.pipeline import SUPPORTED, run  # noqa: E402
from version import __version__  # noqa: E402

try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
    DND = True
except ImportError:                     # still works without drag & drop
    DND = False

# settings live in %APPDATA%: next to the code would be a temporary folder inside the .exe
SETTINGS = Path(os.environ.get("APPDATA", Path.home())) / "PriceExtractor" / "settings.json"
OLD_SETTINGS = Path(__file__).resolve().parent / "settings.json"
BG, PANEL, FG, MUTED, ACCENT = "#1f2126", "#2a2d34", "#e0e2e6", "#8b909a", "#5a8c74"


def load_settings():
    for f in (SETTINGS, OLD_SETTINGS):
        try:
            return json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            continue
    return {}


def save_settings(data):
    try:
        SETTINGS.parent.mkdir(parents=True, exist_ok=True)
        SETTINGS.write_text(json.dumps(data, indent=1), encoding="utf-8")
    except Exception:
        pass


class App:
    def __init__(self):
        self.root = TkinterDnD.Tk() if DND else tk.Tk()
        self.root.title(f"Price Extractor  v{__version__}")
        w, h = 900, 640
        self.root.geometry(f"{w}x{h}+{(self.root.winfo_screenwidth() - w) // 2}+{(self.root.winfo_screenheight() - h) // 3}")
        self.root.minsize(700, 500)
        self.root.configure(bg=BG)
        self.settings = load_settings()
        self.files = []                          # [Path]
        self.out_dir = tk.StringVar(value=self.settings.get("output", str(Path.home() / "Downloads" / "Prices extracted")))
        self._style()
        self._build()
        updater.cleanup_old()
        if updater.is_frozen():                  # only the built .exe updates itself
            threading.Thread(target=self._check_update, daemon=True).start()

    # ------------------------------------------------------------ updates
    def _check_update(self):
        info = updater.check()
        if info:
            self.root.after(0, self._offer_update, info)

    def _offer_update(self, info):
        notes = info["notes"][:600] + ("..." if len(info["notes"]) > 600 else "")
        msg = f"Version {info['version']} is available (you have {__version__}).\n\n{notes}\n\nUpdate now? The app will restart."
        if not messagebox.askyesno("Update available", msg):
            return
        self.go_btn.configure(state="disabled")
        self.status.configure(text="Downloading update...")
        threading.Thread(target=self._do_update, args=(info,), daemon=True).start()

    def _do_update(self, info):
        def progress(done, total):
            self.root.after(0, lambda: (self.progress.configure(maximum=total or 1, value=done),
                                        self.status.configure(text=f"Downloading update... {done * 100 // (total or 1)}%")))
        try:
            new_exe = updater.download(info, progress)
            updater.install_and_restart(new_exe)
        except Exception as e:
            self.root.after(0, lambda: (self.go_btn.configure(state="normal"), self.status.configure(text=""),
                                        messagebox.showerror("Update failed", f"The update could not be installed:\n{e}\n\n"
                                                             "You can keep using this version.")))
            return
        self.root.after(0, self.root.destroy)

    # ------------------------------------------------------------ layout
    def _style(self):
        s = ttk.Style()
        s.theme_use("clam")
        s.configure("TFrame", background=BG)
        s.configure("TLabel", background=BG, foreground=FG, font=("Segoe UI", 10))
        s.configure("Muted.TLabel", foreground=MUTED, font=("Segoe UI", 9))
        s.configure("TButton", font=("Segoe UI", 10), padding=(12, 6))
        s.configure("Go.TButton", font=("Segoe UI", 11, "bold"), padding=(18, 8), background=ACCENT, foreground="white")
        s.map("Go.TButton", background=[("active", "#6ba487"), ("disabled", "#3a3d45")])
        s.configure("Treeview", background=PANEL, fieldbackground=PANEL, foreground=FG, rowheight=24, font=("Segoe UI", 9))
        s.configure("Treeview.Heading", font=("Segoe UI", 9, "bold"))
        s.map("Treeview", background=[("selected", "#3a5a47")])
        s.configure("Horizontal.TProgressbar", background=ACCENT)

    def _build(self):
        main = ttk.Frame(self.root, padding=16)
        main.pack(fill="both", expand=True)

        hint = "Drop price files here (pdf, txt, mhtml, xlsx, pictures)  -  or click to choose" if DND else "Click to choose price files"
        self.drop = tk.Label(main, text=hint, bg="#18191d", fg=MUTED, font=("Segoe UI", 11), cursor="hand2",
                             highlightthickness=2, highlightbackground="#3a3d45")
        self.drop.pack(fill="x", ipady=22)
        self.drop.bind("<Button-1>", lambda e: self.choose_files())
        if DND:
            self.drop.drop_target_register(DND_FILES)
            self.drop.dnd_bind("<<Drop>>", self.on_drop)
            self.drop.dnd_bind("<<DragEnter>>", lambda e: self.drop.configure(highlightbackground=ACCENT, fg=ACCENT))
            self.drop.dnd_bind("<<DragLeave>>", lambda e: self.drop.configure(highlightbackground="#3a3d45", fg=MUTED))

        table = ttk.Frame(main)
        table.pack(fill="both", expand=True, pady=(12, 6))
        self.tree = ttk.Treeview(table, columns=("supplier", "file"), show="headings", selectmode="extended")
        self.tree.heading("supplier", text="Supplier")
        self.tree.heading("file", text="File")
        self.tree.column("supplier", width=170, stretch=False)
        self.tree.column("file", width=600)
        sb = ttk.Scrollbar(table, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        self.tree.bind("<Delete>", lambda e: self.remove_selected())

        row = ttk.Frame(main)
        row.pack(fill="x", pady=(0, 8))
        ttk.Button(row, text="Add files", command=self.choose_files).pack(side="left")
        ttk.Button(row, text="Remove selected", command=self.remove_selected).pack(side="left", padx=6)
        ttk.Button(row, text="Clear", command=self.clear).pack(side="left")
        self.count = ttk.Label(row, text="", style="Muted.TLabel")
        self.count.pack(side="right")

        out = ttk.Frame(main)
        out.pack(fill="x", pady=(4, 8))
        ttk.Label(out, text="Save to:").pack(side="left")
        ttk.Entry(out, textvariable=self.out_dir).pack(side="left", fill="x", expand=True, padx=6)
        ttk.Button(out, text="Change", command=self.choose_out).pack(side="left")
        ttk.Button(out, text="Open folder", command=self.open_out).pack(side="left", padx=(6, 0))

        go = ttk.Frame(main)
        go.pack(fill="x", pady=(4, 8))
        self.go_btn = ttk.Button(go, text="Extract prices", style="Go.TButton", command=self.start)
        self.go_btn.pack(side="left")
        self.progress = ttk.Progressbar(go, mode="determinate", style="Horizontal.TProgressbar")
        self.progress.pack(side="left", fill="x", expand=True, padx=12)
        self.status = ttk.Label(go, text="", style="Muted.TLabel", width=34)
        self.status.pack(side="left")

        self.log = tk.Text(main, height=11, bg="#18191d", fg=FG, insertbackground=FG, relief="flat",
                           font=("Consolas", 9), wrap="none")
        self.log.pack(fill="both", expand=False)
        self.log.tag_configure("head", foreground="#e8c26b", font=("Consolas", 9, "bold"))
        self.log.tag_configure("bad", foreground="#e57373")

    # ------------------------------------------------------------ files
    def on_drop(self, event):
        self.drop.configure(highlightbackground="#3a3d45", fg=MUTED)
        self.add(self.root.tk.splitlist(event.data))

    def choose_files(self):
        start = self.settings.get("input", str(Path.home() / "Downloads"))
        paths = filedialog.askopenfilenames(
            title="Choose price files", initialdir=start,
            filetypes=[("Price files", " ".join(f"*{e}" for e in sorted(SUPPORTED))), ("All files", "*.*")])
        if paths:
            self.settings["input"] = str(Path(paths[0]).parent)
            save_settings(self.settings)
            self.add(paths)

    def add(self, paths):
        finals = {s.final_file.lower() for s in suppliers() if s.final_file}
        left_out = 0
        for p in paths:
            p = Path(p)
            items = sorted(f for f in p.iterdir() if f.suffix.lower() in SUPPORTED) if p.is_dir() else [p]
            for f in items:
                if f in self.files:
                    continue
                if f.name.lower() in finals:              # a final (OneDrive) Excel, not a price list
                    left_out += 1
                    continue
                self.files.append(f)
                sup = identify(f)
                self.tree.insert("", "end", iid=str(f), values=(sup.name if sup else "? (checked on extract)", f.name))
        note = f"   ({left_out} final Excel file(s) left out)" if left_out else ""
        self.count.configure(text=f"{len(self.files)} file(s){note}")

    def remove_selected(self):
        for iid in self.tree.selection():
            self.tree.delete(iid)
            self.files = [f for f in self.files if str(f) != iid]
        self.count.configure(text=f"{len(self.files)} file(s)" if self.files else "")

    def clear(self):
        self.tree.delete(*self.tree.get_children())
        self.files = []
        self.count.configure(text="")

    def choose_out(self):
        d = filedialog.askdirectory(title="Where to save the extracted prices", initialdir=self.out_dir.get())
        if d:
            self.out_dir.set(d)

    def open_out(self):
        d = Path(self.out_dir.get())
        d.mkdir(parents=True, exist_ok=True)
        os.startfile(d) if hasattr(os, "startfile") else None

    # ------------------------------------------------------------ run
    def start(self):
        if not self.files:
            messagebox.showinfo("Price Extractor", "Add some price files first.")
            return
        self.settings["output"] = self.out_dir.get()
        save_settings(self.settings)
        self.go_btn.configure(state="disabled")
        self.log.delete("1.0", "end")
        threading.Thread(target=self.work, args=(list(self.files), Path(self.out_dir.get())), daemon=True).start()

    def work(self, files, out_dir):
        def progress(i, n, name):
            self.root.after(0, self.show_progress, i, n, name)
        try:
            report = run(files, out_dir, progress)
            self.root.after(0, self.done, report)
        except Exception as e:                                         # never leave the window stuck
            self.root.after(0, self.failed, e)

    def show_progress(self, i, n, name):
        self.progress.configure(maximum=n, value=i)
        self.status.configure(text=f"Reading {name}" if name else "Writing Excel...")

    def failed(self, e):
        self.go_btn.configure(state="normal")
        self.status.configure(text="Failed")
        messagebox.showerror("Price Extractor", f"Something went wrong:\n{e}")

    def done(self, report):
        self.go_btn.configure(state="normal")
        rows = sum(len(r.rows) for r in report.results)
        self.status.configure(text=f"Done: {rows} prices")
        for line in report.text().splitlines():
            tag = "head" if line and not line.startswith(" ") else None
            if line.startswith("NOT PROCESSED") or line.startswith("WARNINGS"):
                tag = "bad"
            self.log.insert("end", line + "\n", tag)

        msg = []
        if report.combined:
            msg.append(f"Combined file:\n   {report.combined.name}")
        if report.separate:
            msg.append("Separate files (their final file is split by species):\n" +
                       "\n".join(f"   {p.name}" for _, p in report.separate))
        if report.errors:
            msg.append(f"{len(report.errors)} file(s) could not be processed - see the log.")
        skipped = sum(len(r.skipped) for r in report.results)
        if skipped:
            msg.append(f"{skipped} price(s) of unknown products were not extracted - see the log.")
        title = "Extraction finished"
        if report.errors:
            messagebox.showwarning(title, "\n\n".join(msg) or "Nothing extracted.")
        else:
            messagebox.showinfo(title, "\n\n".join(msg) or "Nothing extracted.")

    def mainloop(self):
        self.root.mainloop()


def run_without_window(args):
    """PriceExtractor.exe --extract <files or folders> -o <output folder>   (writes report.txt there)"""
    out = Path(args[args.index("-o") + 1]) if "-o" in args else Path.cwd() / "Prices extracted"
    inputs = [Path(a) for a in args if a not in ("--extract", "-o") and Path(a) != out]
    files = []
    for p in inputs:
        files += sorted(f for f in p.iterdir() if f.suffix.lower() in SUPPORTED) if p.is_dir() else [p]
    report = run(files, out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "report.txt").write_text(f"Price Extractor v{__version__}\nSuppliers loaded: {len(suppliers())}\n\n"
                                    f"{report.text()}\n", encoding="utf-8")


def update_without_asking():
    """PriceExtractor.exe --update : install the latest version if there is one, then start it."""
    updater.cleanup_old()
    info = updater.check()
    if info and updater.is_frozen():
        updater.install_and_restart(updater.download(info))


if __name__ == "__main__":
    if "--extract" in sys.argv:
        run_without_window(sys.argv[1:])
    elif "--update" in sys.argv:
        update_without_asking()
    else:
        App().mainloop()
