#!/usr/bin/env python3
import os, re, sys
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox

APP_TITLE = "Filename lister"

THEMES = {
    "Nova Dark": {
        "bg": "#252525",
        "fg": "#ECECEC",
        "muted": "#BBBBBB",
        "accent_pink": "#f6b2d1",
        "accent_purple": "#5a2a83",
        "input_bg": "#2f2f2f",
        "border": "#3a3a3a",
        "btn_fg": "#ffffff",
        "btn_bg": "#5a2a83",
        "btn_hover": "#7d44b2",
    },
    "Light": {
        "bg": "#ffffff",
        "fg": "#111111",
        "muted": "#666666",
        "accent_pink": "#eaa7c9",
        "accent_purple": "#6a40a6",
        "input_bg": "#ffffff",
        "border": "#cccccc",
        "btn_fg": "#ffffff",
        "btn_bg": "#6a40a6",
        "btn_hover": "#8557c2",
    },
}

def natural_key(s: str):
    return [int(t) if t.isdigit() else t.casefold() for t in re.split(r"(\d+)", s)]

class CButton(tk.Canvas):
    def __init__(self, parent, text, command, bg, fg, hover_bg, **kw):
        super().__init__(parent, width=110, height=28, highlightthickness=0, bd=0, **kw)
        self.cmd = command
        self.text = text
        self.bg_color = bg
        self.fg_color = fg
        self.hover_bg = hover_bg
        self._rect = None
        self._label = None
        self._draw(bg)
        self.bind("<Enter>", lambda e: self._draw(self.hover_bg))
        self.bind("<Leave>", lambda e: self._draw(self.bg_color))
        self.bind("<Button-1>", lambda e: self.cmd())

    def _draw(self, fill):
        self.delete("all")
        w = int(self["width"]); h = int(self["height"])
        r = 6
        # rounded rect path using create_polygon for compatibility
        points = [
            (r,0),(w-r,0),(w,0),(w,h-r),(w,h),(w-r,h),(r,h),(0,h),(0,h-r),(0,0)
        ]
        self.create_rectangle(0,0,w,h, outline="", fill=fill)
        self.create_text(w//2, h//2, text=self.text, fill=self.fg_color, font=("Helvetica", 11, "bold"))

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP_TITLE)
        self.geometry("900x660")
        self.minsize(760, 560)

        self.dir_var = tk.StringVar(value=str(Path.cwd()))
        self.out_var = tk.StringVar(value="filenames_sorted.txt")
        self.include_files = tk.BooleanVar(value=True)
        self.include_dirs = tk.BooleanVar(value=False)
        self.recurse = tk.BooleanVar(value=False)
        self.case_insensitive = tk.BooleanVar(value=True)
        self.natural_sort = tk.BooleanVar(value=True)
        self.skip_output = tk.BooleanVar(value=True)
        self.theme_name = tk.StringVar(value="Nova Dark")

        self._build_ui()
        self.apply_theme()

    def _build_ui(self):
        pad_y = 6
        self.header = tk.Canvas(self, height=68, highlightthickness=0)
        self.header.pack(fill="x")

        # Theme toggle
        self.theme_frame = tk.Frame(self)
        self.theme_frame.place(in_=self.header, relx=1.0, x=-12, y=10, anchor="ne")
        self.btn_dark = tk.Button(self.theme_frame, text="Nova Dark", command=lambda: self.set_theme("Nova Dark"))
        self.btn_light = tk.Button(self.theme_frame, text="Light", command=lambda: self.set_theme("Light"))
        self.btn_dark.pack(side="left", padx=(0,6))
        self.btn_light.pack(side="left")

        top = tk.Frame(self)
        top.pack(fill="x", padx=12, pady=(8, pad_y))
        tk.Label(top, text="Folder").pack(side="left")
        self.dir_entry = tk.Entry(top, textvariable=self.dir_var, highlightthickness=1)
        self.dir_entry.pack(side="left", fill="x", expand=True, padx=6)
        # custom canvas button for Browse
        self.browse_btn_canvas = CButton(top, "Browse", self.browse_dir, "#444", "#fff", "#666")
        self.browse_btn_canvas.pack(side="left")

        out = tk.Frame(self)
        out.pack(fill="x", padx=12, pady=(0, pad_y))
        tk.Label(out, text="Output file name").pack(side="left")
        self.out_entry = tk.Entry(out, textvariable=self.out_var, highlightthickness=1)
        self.out_entry.pack(side="left", fill="x", expand=True, padx=6)

        self.opts = tk.LabelFrame(self, text="Options")
        self.opts.pack(fill="x", padx=12, pady=(0, pad_y))
        self.cb_files = tk.Checkbutton(self.opts, text="Include files", variable=self.include_files)
        self.cb_dirs = tk.Checkbutton(self.opts, text="Include folders", variable=self.include_dirs)
        self.cb_recurse = tk.Checkbutton(self.opts, text="Recurse into subfolders", variable=self.recurse)
        self.cb_ci = tk.Checkbutton(self.opts, text="Case insensitive sort", variable=self.case_insensitive)
        self.cb_nat = tk.Checkbutton(self.opts, text="Natural sort numbers", variable=self.natural_sort)
        self.cb_skip = tk.Checkbutton(self.opts, text="Skip the output file itself", variable=self.skip_output)
        self.cb_files.grid(row=0, column=0, sticky="w")
        self.cb_dirs.grid(row=0, column=1, sticky="w")
        self.cb_recurse.grid(row=0, column=2, sticky="w")
        self.cb_ci.grid(row=1, column=0, sticky="w")
        self.cb_nat.grid(row=1, column=1, sticky="w")
        self.cb_skip.grid(row=1, column=2, sticky="w")

        acts = tk.Frame(self)
        acts.pack(fill="x", padx=12, pady=(0, pad_y))
        # custom buttons for Preview and Write
        self.preview_btn_canvas = CButton(acts, "Preview", self.preview, "#444", "#fff", "#666")
        self.write_btn_canvas = CButton(acts, "Write file", self.write_file, "#444", "#fff", "#666")
        self.preview_btn_canvas.pack(side="left")
        self.write_btn_canvas.pack(side="left", padx=(8,0))

        self.status_var = tk.StringVar(value="Ready")
        self.status = tk.Label(self, textvariable=self.status_var, anchor="w")
        self.status.pack(fill="x", padx=12, pady=(0, 4))

        text_frame = tk.Frame(self)
        text_frame.pack(fill="both", expand=True, padx=12, pady=8)
        self.text = tk.Text(text_frame, wrap="none", height=18)
        self.text.pack(side="left", fill="both", expand=True)
        self.yscroll = tk.Scrollbar(text_frame, orient="vertical", command=self.text.yview)
        self.yscroll.pack(side="right", fill="y")
        self.text.configure(yscrollcommand=self.yscroll.set)
        self.xscroll = tk.Scrollbar(self, orient="horizontal", command=self.text.xview)
        self.xscroll.pack(fill="x", padx=12, pady=(0,8))
        self.text.configure(xscrollcommand=self.xscroll.set)

    def set_theme(self, name):
        self.theme_name.set(name)
        self.apply_theme()

    def apply_theme(self):
        t = THEMES[self.theme_name.get()]
        # window and groups
        for w in (self, self.opts, self.status.master, self.text.master):
            try: w.configure(bg=t["bg"])
            except tk.TclError: pass

        # header
        self.header.delete("all")
        self.header.configure(bg=t["bg"])
        W = self.header.winfo_width() or self.header.winfo_reqwidth()
        H = self.header.winfo_height() or 68
        self.header.create_rectangle(0, H-6, W, H, fill=t["accent_purple"], width=0)
        self.header.create_text(16, H//2, text="nova", anchor="w",
                                font=("Helvetica", 24, "bold"),
                                fill=t["accent_pink"])
        self.header.create_text(95, H//2, text="Filename lister", anchor="w",
                                font=("Helvetica", 14, "bold"),
                                fill=t["fg"])
        self.header.bind("<Configure>", lambda e: self.apply_theme())

        # entries and labels
        for e in (self.dir_entry, self.out_entry, self.text):
            try:
                e.configure(bg=t["input_bg"], fg=t["fg"], insertbackground=t["fg"], highlightbackground=t["border"])
            except tk.TclError:
                pass

        # checkboxes and labels
        for cb in (self.cb_files, self.cb_dirs, self.cb_recurse, self.cb_ci, self.cb_nat, self.cb_skip):
            try:
                cb.configure(bg=t["bg"], fg=t["fg"], activebackground=t["bg"], selectcolor=t["input_bg"])
            except tk.TclError:
                pass
        try:
            self.opts.configure(bg=t["bg"], fg=t["fg"], highlightbackground=t["border"])
            self.status.configure(bg=t["bg"], fg=t["muted"])
        except tk.TclError:
            pass

        # scrollbars
        for s in (self.yscroll, self.xscroll):
            try:
                s.configure(troughcolor=t["bg"], bg=t["border"], activebackground=t["accent_pink"], highlightbackground=t["border"])
            except tk.TclError:
                pass

        # custom buttons recolor
        for b in (self.browse_btn_canvas, self.preview_btn_canvas, self.write_btn_canvas):
            b.bg_color = t["btn_bg"]
            b.hover_bg = t["btn_hover"]
            b.fg_color = t["btn_fg"]
            b._draw(b.bg_color)

        # theme toggle native buttons still may be white; leave as is for reliability

    # behavior
    def browse_dir(self):
        path = filedialog.askdirectory(initialdir=self.dir_var.get() or str(Path.cwd()))
        if path:
            self.dir_var.set(path)

    def gather_names(self):
        root = Path(self.dir_var.get()).resolve()
        if not root.exists() or not root.is_dir():
            raise ValueError("Folder does not exist")
        out_name = self.out_var.get().strip() or "filenames_sorted.txt"
        names = []

        if self.recurse.get():
            for dirpath, dirnames, filenames in os.walk(root):
                dpath = Path(dirpath)
                if self.include_dirs.get():
                    for d in dirnames:
                        names.append(str((dpath / d).relative_to(root)))
                if self.include_files.get():
                    for f in filenames:
                        names.append(str((dpath / f).relative_to(root)))
        else:
            for p in root.iterdir():
                if p.is_dir() and self.include_dirs.get():
                    names.append(p.name)
                if p.is_file() and self.include_files.get():
                    names.append(p.name)

        if self.skip_output.get():
            names = [n for n in names if Path(n).name != Path(out_name).name]

        key_func = natural_key if self.natural_sort.get() else (str.casefold if self.case_insensitive.get() else None)
        if not self.natural_sort.get() and not self.case_insensitive.get():
            key_func = None
        names.sort(key=key_func)
        return names

    def preview(self):
        try:
            names = self.gather_names()
        except Exception as e:
            messagebox.showerror("Error", str(e))
            return
        self.text.delete("1.0", "end")
        for n in names[:5000]:
            self.text.insert("end", n + "\n")
        self.status_var.set(f"Previewed {len(names)} entries")

    def write_file(self):
        try:
            names = self.gather_names()
        except Exception as e:
            messagebox.showerror("Error", str(e))
            return
        out_path = Path(self.dir_var.get()).resolve() / (self.out_var.get().strip() or "filenames_sorted.txt")
        try:
            with out_path.open("w", encoding="utf-8", newline="\n") as f:
                for n in names:
                    f.write(n + "\n")
        except Exception as e:
            messagebox.showerror("Write failed", str(e))
            return
        self.status_var.set(f"Wrote {len(names)} entries to {out_path.name}")
        messagebox.showinfo("Done", f"Wrote {len(names)} entries to\n{out_path}")

def main():
    App().mainloop()

if __name__ == "__main__":
    main()
