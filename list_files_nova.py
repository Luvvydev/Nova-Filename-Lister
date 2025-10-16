#!/usr/bin/env python3
# The shebang line above lets Unix like systems know to use Python 3 to run this script
# On Windows it is ignored, which is fine.

import os, re, sys
# os is used for walking folders and files
# re is used for splitting text with regular expressions for natural sorting
# sys is not currently used but is a common standard import and harmless to keep
from pathlib import Path  # Path gives a nicer, object oriented way to work with filesystem paths
import tkinter as tk  # tk is the standard Python interface to the Tk GUI toolkit
from tkinter import filedialog, messagebox  # handy dialogs for file picking and popup messages

# Window title string shown in the header bar and top left branding
APP_TITLE = "Filename lister"

# A tiny theme system. This dictionary holds color choices for two looks.
# apply_theme reads from here to paint the interface.
THEMES = {
    "Nova Dark": {
        "bg": "#252525",        # background of windows and frames
        "fg": "#ECECEC",        # main text color
        "muted": "#BBBBBB",     # secondary text color
        "accent_pink": "#f6b2d1",
        "accent_purple": "#5a2a83",
        "input_bg": "#2f2f2f",  # text boxes background
        "border": "#3a3a3a",    # outlines and separators
        "btn_fg": "#ffffff",    # button label color
        "btn_bg": "#5a2a83",    # button background color
        "btn_hover": "#7d44b2", # button hover color
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

# Natural sort helper.
# It splits the string into text and number chunks. Numbers are converted to int.
def natural_key(s: str):
    # re.split with capture group keeps the digits. Non digits stay as text.
    # For text, we use casefold to normalize case so the sort is stable and case insensitive when comparing letters.
    return [int(t) if t.isdigit() else t.casefold() for t in re.split(r"(\d+)", s)]

# Custom clickable button drawn on a Canvas.
# Why do this instead of tk.Button?
# It gives us consistent coloring and hover effects across platforms, since native buttons differ.
class CButton(tk.Canvas):
    def __init__(self, parent, text, command, bg, fg, hover_bg, **kw):
        # width and height set a fixed button size. highlightthickness and bd remove default borders.
        super().__init__(parent, width=110, height=28, highlightthickness=0, bd=0, **kw)
        self.cmd = command          # function to call when clicked
        self.text = text            # text shown on the button
        self.bg_color = bg          # normal background
        self.fg_color = fg          # text color
        self.hover_bg = hover_bg    # background when mouse is over
        self._rect = None           # internal references to drawn shapes if needed later
        self._label = None
        self._draw(bg)              # initial paint
        # Bind mouse events for hover and click
        self.bind("<Enter>", lambda e: self._draw(self.hover_bg))
        self.bind("<Leave>", lambda e: self._draw(self.bg_color))
        self.bind("<Button-1>", lambda e: self.cmd())

    def _draw(self, fill):
        # Redraw the button with a solid rectangle and centered text
        self.delete("all")
        w = int(self["width"]); h = int(self["height"])
        # Simple rectangle gives a flat modern look. Rounded corners would require a custom polygon.
        self.create_rectangle(0,0,w,h, outline="", fill=fill)
        self.create_text(w//2, h//2, text=self.text, fill=self.fg_color, font=("Helvetica", 11, "bold"))

# Main application. This is the root Tk window plus all widgets and behaviors.
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP_TITLE)
        # geometry sets initial size. minsize prevents shrinking below a usable layout.
        self.geometry("900x660")
        self.minsize(760, 560)

        # Tkinter control variables hold UI state and make it easy to read or bind to widgets.
        self.dir_var = tk.StringVar(value=str(Path.cwd()))               # starting folder to scan
        self.out_var = tk.StringVar(value="filenames_sorted.txt")        # default output filename
        self.include_files = tk.BooleanVar(value=True)                   # include regular files in listing
        self.include_dirs = tk.BooleanVar(value=False)                   # include folders in listing
        self.recurse = tk.BooleanVar(value=False)                        # walk into subfolders or not
        self.case_insensitive = tk.BooleanVar(value=True)                # case insensitive sort when not natural
        self.natural_sort = tk.BooleanVar(value=True)                    # prefer natural sort by default
        self.skip_output = tk.BooleanVar(value=True)                     # skip writing the output file name if it would appear in results
        self.theme_name = tk.StringVar(value="Nova Dark")                # current theme name
        # Compare tool state
        self.comp_case_insensitive = tk.BooleanVar(value=False)          # case handling for compare
        self.comp_reduce_output = tk.BooleanVar(value=False)             # suppress very large results from rendering

        # Export lister output into compare boxes A or B
        self.send_to_a = tk.BooleanVar(value=False)
        self.send_to_b = tk.BooleanVar(value=False)
        self.comp_max_combined_mb = 15  # limit for combined loaded text via file picker

        # Keep A and B mutually exclusive so the lister sends the preview to only one side at a time
        try:
            # Newer Tk versions
            self.send_to_a.trace_add('write', self._on_send_toggle)
            self.send_to_b.trace_add('write', self._on_send_toggle)
        except AttributeError:
            # Older Tk fallback
            self.send_to_a.trace('w', self._on_send_toggle)
            self.send_to_b.trace('w', self._on_send_toggle)

        # If compare result text is extremely large, treat it as a special case
        self.comp_large_threshold_mb = 3
        # Build all widgets
        self._build_ui()
        # Paint them according to the selected theme
        self.apply_theme()

    def _on_send_toggle(self, *args):
        """
        Ensure only one of Send to Compare A or Send to Compare B is on.
        If both somehow become true, prefer A and turn B off.
        """
        try:
            a = bool(self.send_to_a.get())
            b = bool(self.send_to_b.get())
        except Exception:
            return
        # Avoid looping from setting one var inside the other's callback
        if a and b:
            self.send_to_b.set(False)
        elif a:
            self.send_to_b.set(False)
        elif b:
            self.send_to_a.set(False)

    def _build_ui(self):
        """Create all visible widgets and lay them out with pack and grid where appropriate."""
        pad_y = 6

        # Menubar keeps important actions visible even if the window is not maximized
        try:
            self.menubar = tk.Menu(self)
            m_compare = tk.Menu(self.menubar, tearoff=0)
            m_compare.add_command(label='Open compare window', command=self.open_compare_window)
            self.menubar.add_cascade(label='Compare', menu=m_compare)
            self.config(menu=self.menubar)
        except Exception:
            # Some platforms may not support a menubar. It is safe to ignore.
            pass

        # Header is a Canvas so we can draw a colored bar and the nova label
        self.header = tk.Canvas(self, height=68, highlightthickness=0)
        self.header.pack(fill="x")

        # Theme switchers and a quick Compare button live in the header
        self.theme_frame = tk.Frame(self)
        # place puts it at the top right inside the header canvas
        self.theme_frame.place(in_=self.header, relx=1.0, x=-12, y=10, anchor="ne")
        self.btn_dark = tk.Button(self.theme_frame, text="Nova Dark", command=lambda: self.set_theme("Nova Dark"))
        self.btn_light = tk.Button(self.theme_frame, text="Light", command=lambda: self.set_theme("Light"))
        self.btn_dark.pack(side="left", padx=(0,6))
        self.btn_light.pack(side="left")

        # Quick access Compare button so it is visible even on smaller windows
        try:
            self.btn_open_compare_hdr = tk.Button(self.theme_frame, text="Compare", command=self.open_compare_window)
            self.btn_open_compare_hdr.pack(side="left", padx=(6,0))
        except Exception:
            pass

        # Top area with folder picker and Browse button
        top = tk.Frame(self)
        top.pack(fill="x", padx=12, pady=(8, pad_y))
        tk.Label(top, text="Folder").pack(side="left")
        self.dir_entry = tk.Entry(top, textvariable=self.dir_var, highlightthickness=1)
        self.dir_entry.pack(side="left", fill="x", expand=True, padx=6)
        # Custom canvas button for Browse to keep styling consistent
        self.browse_btn_canvas = CButton(top, "Browse", self.browse_dir, "#444", "#fff", "#666")
        self.browse_btn_canvas.pack(side="left")

        # Output filename entry row
        out = tk.Frame(self)
        out.pack(fill="x", padx=12, pady=(0, pad_y))
        tk.Label(out, text="Output file name").pack(side="left")
        self.out_entry = tk.Entry(out, textvariable=self.out_var, highlightthickness=1)
        self.out_entry.pack(side="left", fill="x", expand=True, padx=6)

        # Options group for lister behavior
        self.opts = tk.LabelFrame(self, text="Options")
        self.opts.pack(fill="x", padx=12, pady=(0, pad_y))
        self.cb_files = tk.Checkbutton(self.opts, text="Include files", variable=self.include_files)
        self.cb_dirs = tk.Checkbutton(self.opts, text="Include folders", variable=self.include_dirs)
        self.cb_recurse = tk.Checkbutton(self.opts, text="Recurse into subfolders", variable=self.recurse)
        self.cb_ci = tk.Checkbutton(self.opts, text="Case insensitive sort", variable=self.case_insensitive)
        self.cb_nat = tk.Checkbutton(self.opts, text="Natural sort numbers", variable=self.natural_sort)
        self.cb_skip = tk.Checkbutton(self.opts, text="Skip the output file itself", variable=self.skip_output)
        # grid is fine inside a group. It aligns checkboxes into neat rows.
        self.cb_files.grid(row=0, column=0, sticky="w")
        self.cb_dirs.grid(row=0, column=1, sticky="w")
        self.cb_recurse.grid(row=0, column=2, sticky="w")
        self.cb_ci.grid(row=1, column=0, sticky="w")
        self.cb_nat.grid(row=1, column=1, sticky="w")
        self.cb_skip.grid(row=1, column=2, sticky="w")

        # Action buttons
        acts = tk.Frame(self)
        acts.pack(fill="x", padx=12, pady=(0, pad_y))
        # Custom canvas buttons for consistent look
        self.preview_btn_canvas = CButton(acts, "Preview", self.preview, "#444", "#fff", "#666")
        self.write_btn_canvas = CButton(acts, "Write file", self.write_file, "#444", "#fff", "#666")
        self.preview_btn_canvas.pack(side="left")
        self.write_btn_canvas.pack(side="left", padx=(8,0))

        # Optional export to compare inputs
        self.cb_send_a = tk.Checkbutton(acts, text="Send to Compare A", variable=self.send_to_a)
        self.cb_send_b = tk.Checkbutton(acts, text="Send to Compare B", variable=self.send_to_b)
        self.cb_send_a.pack(side="left", padx=(12,0))
        self.cb_send_b.pack(side="left", padx=(8,0))

        # Status line for short feedback messages
        self.status_var = tk.StringVar(value="Ready")
        self.status = tk.Label(self, textvariable=self.status_var, anchor="w")
        self.status.pack(fill="x", padx=12, pady=(0, 4))

        # Large text area to preview the listing
        text_frame = tk.Frame(self)
        text_frame.pack(fill="both", expand=True, padx=12, pady=8)
        self.text = tk.Text(text_frame, wrap="none", height=18)  # wrap="none" keeps long lines on one line with horizontal scroll
        self.text.pack(side="left", fill="both", expand=True)
        self.yscroll = tk.Scrollbar(text_frame, orient="vertical", command=self.text.yview)
        self.yscroll.pack(side="right", fill="y")
        self.text.configure(yscrollcommand=self.yscroll.set)
        self.xscroll = tk.Scrollbar(self, orient="horizontal", command=self.text.xview)
        self.xscroll.pack(fill="x", padx=12, pady=(0,8))
        self.text.configure(xscrollcommand=self.xscroll.set)

        # Compare section sits under the preview
        self.compare_group = tk.LabelFrame(self, text="Compare two lists")
        self.compare_group.pack(fill="both", expand=False, padx=12, pady=8)

        # Top row of compare with file loaders and toggles
        cmp_top = tk.Frame(self.compare_group)
        cmp_top.pack(fill="x", pady=(4,6))

        tk.Label(cmp_top, text="List A").pack(side="left")
        self.btn_load_a = tk.Button(cmp_top, text="Browse A", command=lambda: self._load_list_file(self.text_a))
        self.btn_load_a.pack(side="left", padx=(6,12))

        tk.Label(cmp_top, text="List B").pack(side="left")
        self.btn_load_b = tk.Button(cmp_top, text="Browse B", command=lambda: self._load_list_file(self.text_b))
        self.btn_load_b.pack(side="left", padx=(6,12))

        self.cb_comp_ci = tk.Checkbutton(cmp_top, text="Case insensitive", variable=self.comp_case_insensitive)
        self.cb_comp_ci.pack(side="left", padx=(12,0))

        self.cb_comp_reduce = tk.Checkbutton(cmp_top, text="Reduce output for large lists", variable=self.comp_reduce_output)
        self.cb_comp_reduce.pack(side="left", padx=(12,0))

        # Two side by side text boxes for List A and List B
        cmp_body = tk.Frame(self.compare_group)
        cmp_body.pack(fill="both", expand=True)

        left_frame = tk.Frame(cmp_body)
        left_frame.pack(side="left", fill="both", expand=True, padx=(0,6))
        self.text_a = tk.Text(left_frame, wrap="none", height=10)
        self.text_a.pack(side="left", fill="both", expand=True)
        self.yscroll_a = tk.Scrollbar(left_frame, orient="vertical", command=self.text_a.yview)
        self.yscroll_a.pack(side="right", fill="y")
        self.text_a.configure(yscrollcommand=self.yscroll_a.set)

        right_frame = tk.Frame(cmp_body)
        right_frame.pack(side="left", fill="both", expand=True, padx=(6,0))
        self.text_b = tk.Text(right_frame, wrap="none", height=10)
        self.text_b.pack(side="left", fill="both", expand=True)
        self.yscroll_b = tk.Scrollbar(right_frame, orient="vertical", command=self.text_b.yview)
        self.yscroll_b.pack(side="right", fill="y")
        self.text_b.configure(yscrollcommand=self.yscroll_b.set)

        # Buttons for comparing and saving results under the list inputs
        cmp_actions = tk.Frame(self.compare_group)
        cmp_actions.pack(fill="x", pady=(6,4))
        self.btn_compare = tk.Button(cmp_actions, text="Compare", command=self.compare_lists)
        self.btn_compare.pack(side="left")
        self.btn_save_results = tk.Button(cmp_actions, text="Save results...", command=self.save_compare_results)
        self.btn_save_results.pack(side="left", padx=(8,0))
        # Dedicated window gives more room if needed
        self.btn_compare_popup = tk.Button(cmp_actions, text="Open compare window", command=self.open_compare_window)
        self.btn_compare_popup.pack(side="left", padx=(8,0))

        # Text area shows the combined diff results
        self.compare_result = tk.Text(self.compare_group, wrap="none", height=10)
        self.compare_result.pack(fill="both", expand=True, pady=(6,0))

    def set_theme(self, name):
        """Switch theme by setting the selected name then repainting."""
        self.theme_name.set(name)
        self.apply_theme()

    def apply_theme(self):
        """
        Read colors from THEMES and apply to all widgets.
        Called at startup and whenever the theme is changed.
        """
        t = THEMES[self.theme_name.get()]
        # window and groups
        for w in (self, self.opts, self.status.master, self.text.master):
            try: w.configure(bg=t["bg"])
            except tk.TclError: pass

        # header drawing: a thin accent bar, then two text labels
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
        # When the header resizes, repaint so the accent bar spans the full width
        self.header.bind("<Configure>", lambda e: self.apply_theme())

        # entries and large text boxes
        for e in (self.dir_entry, self.out_entry, self.text, self.text_a, self.text_b, self.compare_result):
            try:
                e.configure(bg=t["input_bg"], fg=t["fg"], insertbackground=t["fg"], highlightbackground=t["border"])
            except tk.TclError:
                pass

        # checkboxes and labels should share the window background for a flat look
        for cb in (self.cb_files, self.cb_dirs, self.cb_recurse, self.cb_ci, self.cb_nat, self.cb_skip, self.cb_comp_ci, self.cb_comp_reduce, self.cb_send_a, self.cb_send_b):
            try:
                cb.configure(bg=t["bg"], fg=t["fg"], activebackground=t["bg"], selectcolor=t["input_bg"])
            except tk.TclError:
                pass
        try:
            self.opts.configure(bg=t["bg"], fg=t["fg"], highlightbackground=t["border"])
            self.status.configure(bg=t["bg"], fg=t["muted"])
        except tk.TclError:
            pass

        # Scrollbar colors. Note that native scrollbars may ignore some options on some platforms.
        for s in (self.yscroll, self.xscroll, self.yscroll_a, self.yscroll_b):
            try:
                s.configure(troughcolor=t["bg"], bg=t["border"], activebackground=t["accent_pink"], highlightbackground=t["border"])
            except tk.TclError:
                pass

        # Repaint custom buttons to match the theme
        for b in (self.browse_btn_canvas, self.preview_btn_canvas, self.write_btn_canvas):
            b.bg_color = t["btn_bg"]
            b.hover_bg = t["btn_hover"]
            b.fg_color = t["btn_fg"]
            b._draw(b.bg_color)

    # ------------- Lister behavior functions -------------

    def browse_dir(self):
        """Open a folder picker dialog and store the chosen path in dir_var."""
        path = filedialog.askdirectory(initialdir=self.dir_var.get() or str(Path.cwd()))
        if path:
            self.dir_var.set(path)

    def gather_names(self):
        """
        Collect file and or folder names from the selected directory according to the option toggles.
        Returns a sorted list of relative names.
        Raises ValueError if the selected folder does not exist.
        """
        root = Path(self.dir_var.get()).resolve()
        if not root.exists() or not root.is_dir():
            raise ValueError("Folder does not exist")
        out_name = self.out_var.get().strip() or "filenames_sorted.txt"
        names = []

        if self.recurse.get():
            # Walk through all subfolders
            for dirpath, dirnames, filenames in os.walk(root):
                dpath = Path(dirpath)
                if self.include_dirs.get():
                    for d in dirnames:
                        # relative_to makes the listing relative to the root, not absolute
                        names.append(str((dpath / d).relative_to(root)))
                if self.include_files.get():
                    for f in filenames:
                        names.append(str((dpath / f).relative_to(root)))
        else:
            # Only the top level of the chosen folder
            for p in root.iterdir():
                if p.is_dir() and self.include_dirs.get():
                    names.append(p.name)
                if p.is_file() and self.include_files.get():
                    names.append(p.name)

        # Optionally drop the output file from the list, so you do not list the file you are writing
        if self.skip_output.get():
            names = [n for n in names if Path(n).name != Path(out_name).name]

        # Choose the sorting key based on the toggles
        key_func = natural_key if self.natural_sort.get() else (str.casefold if self.case_insensitive.get() else None)
        if not self.natural_sort.get() and not self.case_insensitive.get():
            key_func = None
        names.sort(key=key_func)
        return names

    def preview(self):
        """
        Collect names and render up to 5000 entries into the big preview text box.
        Also optionally copy the same names into Compare A or Compare B if requested.
        """
        try:
            names = self.gather_names()
        except Exception as e:
            messagebox.showerror("Error", str(e))
            return
        self.text.delete("1.0", "end")
        for n in names[:5000]:
            self.text.insert("end", n + "\n")

        # Export a preview into the compare inputs if the checkboxes are on
        if self.send_to_a.get():
            self.text_a.delete("1.0", "end")
            self.text_a.insert("1.0", "\n".join(names[:5000]))
        if self.send_to_b.get():
            self.text_b.delete("1.0", "end")
            self.text_b.insert("1.0", "\n".join(names[:5000]))
        self.status_var.set(f"Previewed {len(names)} entries")

    def write_file(self):
        """
        Write all collected names to the output file in the chosen folder.
        Then optionally export the complete list into Compare A or B.
        """
        try:
            names = self.gather_names()
        except Exception as e:
            messagebox.showerror("Error", str(e))
            return
        out_path = Path(self.dir_var.get()).resolve() / (self.out_var.get().strip() or "filenames_sorted.txt")
        try:
            # newline="\n" forces Unix style line endings for consistency across platforms
            with out_path.open("w", encoding="utf-8", newline="\n") as f:
                for n in names:
                    f.write(n + "\n")
        except Exception as e:
            messagebox.showerror("Write failed", str(e))
            return

        # Export full list into compare inputs if desired
        if self.send_to_a.get():
            self.text_a.delete("1.0", "end")
            self.text_a.insert("1.0", "\n".join(names))
        if self.send_to_b.get():
            self.text_b.delete("1.0", "end")
            self.text_b.insert("1.0", "\n".join(names))

        self.status_var.set(f"Wrote {len(names)} entries to {out_path.name}")
        messagebox.showinfo("Done", f"Wrote {len(names)} entries to\n{out_path}")

    # ------------- Compare behavior functions -------------

    def _load_list_file(self, target_text):
        """
        Open a text file and load its contents into the given Text widget.
        Safety check: if both List A and List B already have content and the new file would push the combined
        size over comp_max_combined_mb, block the load and warn the user.
        This size guard applies only to files loaded via the dialog. Pasting text is unrestricted.
        """
        path = filedialog.askopenfilename(
            title="Select list file",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
        )
        if not path:
            return
        try:
            # Measure current sizes of A and B in bytes
            size_a = 0
            size_b = 0
            if self.text_a.get("1.0", "end-1c"):
                size_a = len(self.text_a.get("1.0", "end-1c").encode("utf-8"))
            if self.text_b.get("1.0", "end-1c"):
                size_b = len(self.text_b.get("1.0", "end-1c").encode("utf-8"))
            size_new = Path(path).stat().st_size
            if size_a + size_b + size_new > self.comp_max_combined_mb * 1024 * 1024:
                messagebox.showerror("Too large", f"Combined size exceeds {self.comp_max_combined_mb} MB")
                return
            data = Path(path).read_text(encoding="utf-8", errors="ignore")
        except Exception as e:
            messagebox.showerror("Read failed", str(e))
            return
        target_text.delete("1.0", "end")
        target_text.insert("1.0", data)

    @staticmethod
    def _normalize_list(raw: str, case_insensitive: bool):
        """
        Convert a raw multi line string into a clean list of unique items.
        Steps:
          1. split into lines
          2. strip spaces on each line
          3. drop blank lines
          4. remove duplicates while keeping the first occurrence
          5. lower case items if case insensitive is selected, to match common website behavior
          6. sort with natural_key for readability
        Returns the cleaned list of strings.
        """
        items = []
        seen = set()
        for line in raw.splitlines():
            s = line.strip()
            if not s:
                continue
            k = s.lower() if case_insensitive else s
            if k in seen:
                continue
            seen.add(k)
            items.append(k if case_insensitive else s)
        items.sort(key=natural_key)
        return items

    def compare_lists(self):
        """
        Compare List A and List B and show three sections:
          Only in A
          Only in B
          In both
        Honors the Case insensitive toggle and the Reduce output toggle.
        """
        a_raw = self.text_a.get("1.0", "end-1c")
        b_raw = self.text_b.get("1.0", "end-1c")
        if not a_raw and not b_raw:
            messagebox.showwarning("Missing input", "Provide at least one list")
            return
        ci = self.comp_case_insensitive.get()
        a = self._normalize_list(a_raw, ci)
        b = self._normalize_list(b_raw, ci)

        set_a = set(a)
        set_b = set(b)
        only_a = sorted(set_a - set_b, key=natural_key)
        only_b = sorted(set_b - set_a, key=natural_key)
        both = sorted(set_a & set_b, key=natural_key)

        # helper to produce a titled block with a count and the items below
        def block(title, arr):
            return title + " (" + str(len(arr)) + ")\n" + "\n".join(arr) + ("\n\n" if arr else "\n\n")

        result_text = ""
        result_text += block("Only in A", only_a)
        result_text += block("Only in B", only_b)
        result_text += block("In both", both)

        # If the combined text is huge and reduce is on, do not render into the text widget.
        bytes_len = len(result_text.encode("utf-8"))
        if self.comp_reduce_output.get() and bytes_len > int(self.comp_large_threshold_mb * 1024 * 1024):
            self.text_a.delete("1.0", "end")
            self.text_b.delete("1.0", "end")
            self.compare_result.delete("1.0", "end")
            messagebox.showinfo("Large output", "Result not shown. Use 'Save results...' to download.")
            self._compare_cache = {"only_a": only_a, "only_b": only_b, "both": both, "combined": result_text}
        else:
            self.compare_result.delete("1.0", "end")
            self.compare_result.insert("1.0", result_text)
            self._compare_cache = {"only_a": only_a, "only_b": only_b, "both": both, "combined": result_text}
        self.status_var.set(f"Compared lists. A:{len(a)} B:{len(b)}")

    def save_compare_results(self):
        """
        Save the compare results into four text files in a folder you choose:
          only_in_a.txt
          only_in_b.txt
          in_both.txt
          compare_result.txt  which contains the combined human readable blocks
        """
        if not hasattr(self, "_compare_cache"):
            messagebox.showwarning("No results", "Run Compare first")
            return
        outdir = filedialog.askdirectory(title="Select folder to save results")
        if not outdir:
            return
        outdir = Path(outdir)
        try:
            (outdir / "only_in_a.txt").write_text("\n".join(self._compare_cache["only_a"]) + "\n", encoding="utf-8")
            (outdir / "only_in_b.txt").write_text("\n".join(self._compare_cache["only_b"]) + "\n", encoding="utf-8")
            (outdir / "in_both.txt").write_text("\n".join(self._compare_cache["both"]) + "\n", encoding="utf-8")
            (outdir / "compare_result.txt").write_text(self._compare_cache["combined"], encoding="utf-8")
        except Exception as e:
            messagebox.showerror("Write failed", str(e))
            return
        messagebox.showinfo("Saved", f"Wrote result files to\n{outdir}")

    def open_compare_window(self):
        """
        Open a separate, larger compare window.
        It copies the current A and B lists into larger text boxes and lets you run a compare there.
        Buttons let you copy the edited lists back to the main window or go back.
        """
        win = tk.Toplevel(self)
        win.title("Compare two lists")
        try:
            win.geometry("960x720")
        except Exception:
            pass

        # Top row in the popup with the same two toggles as the main compare area
        top = tk.Frame(win)
        top.pack(fill="x", pady=(8,6), padx=12)
        tk.Label(top, text="Case insensitive").pack(side="left")
        tk.Checkbutton(top, variable=self.comp_case_insensitive).pack(side="left", padx=(6,18))
        tk.Label(top, text="Reduce output for large lists").pack(side="left")
        tk.Checkbutton(top, variable=self.comp_reduce_output).pack(side="left", padx=(6,0))

        # Two labeled group boxes for A and B inputs
        body = tk.Frame(win)
        body.pack(fill="both", expand=True, padx=12, pady=6)

        left = tk.LabelFrame(body, text="List A")
        right = tk.LabelFrame(body, text="List B")
        left.pack(side="left", fill="both", expand=True, padx=(0,6))
        right.pack(side="left", fill="both", expand=True, padx=(6,0))

        ta = tk.Text(left, wrap="none")
        tb = tk.Text(right, wrap="none")
        ta.pack(fill="both", expand=True)
        tb.pack(fill="both", expand=True)

        # preload current text from the main window so you can continue editing here
        ta.insert("1.0", self.text_a.get("1.0", "end-1c"))
        tb.insert("1.0", self.text_b.get("1.0", "end-1c"))

        def do_compare_popup():
            """
            Compare the contents of the popup A and B editors, optionally reduce large output,
            and write the combined result into the popup result area.
            Also updates the main window compare cache so Save results works from either place.
            """
            a_raw = ta.get("1.0", "end-1c")
            b_raw = tb.get("1.0", "end-1c")
            if not a_raw and not b_raw:
                messagebox.showwarning("Missing input", "Provide at least one list", parent=win)
                return
            ci = self.comp_case_insensitive.get()
            a = self._normalize_list(a_raw, ci)
            b = self._normalize_list(b_raw, ci)

            set_a, set_b = set(a), set(b)
            only_a = sorted(set_a - set_b, key=natural_key)
            only_b = sorted(set_b - set_a, key=natural_key)
            both = sorted(set_a & set_b, key=natural_key)

            def block(title, arr):
                return title + " (" + str(len(arr)) + ")\n" + "\n".join(arr) + ("\n\n" if arr else "\n\n")

            combined = block("Only in A", only_a) + block("Only in B", only_b) + block("In both", both)

            # Keep a shared cache so the Save button in either window writes the same latest results
            self._compare_cache = {"only_a": only_a, "only_b": only_b, "both": both, "combined": combined}

            threshold_bytes = int(getattr(self, "comp_large_threshold_mb", 3) * 1024 * 1024)
            if self.comp_reduce_output.get() and len(combined.encode("utf-8")) > threshold_bytes:
                res.delete("1.0", "end")
                messagebox.showinfo("Large output", "Result not shown. Use 'Save results...' to download.", parent=win)
            else:
                res.delete("1.0", "end")
                res.insert("1.0", combined)

        # Actions row in the popup
        actions = tk.Frame(win)
        actions.pack(fill="x", padx=12, pady=(6,6))
        tk.Button(actions, text="Compare", command=do_compare_popup).pack(side="left")

        # Result output area in the popup
        res = tk.Text(win, wrap="none", height=14)
        res.pack(fill="both", expand=True, padx=12, pady=(0,12))

        # Navigation and copy helpers
        def _back_to_main():
            """
            Close the popup and focus the main window again.
            If destroy fails for any reason, hide the window.
            """
            try:
                win.destroy()
                self.focus_force()
            except Exception:
                try:
                    win.withdraw()
                except Exception:
                    pass

        tk.Button(actions, text="Back to main", command=_back_to_main).pack(side="left", padx=(0,8))
        tk.Button(actions, text="Copy to main A", command=lambda: (self.text_a.delete("1.0","end"), self.text_a.insert("1.0", ta.get("1.0","end-1c")))).pack(side="left", padx=(8,0))
        tk.Button(actions, text="Copy to main B", command=lambda: (self.text_b.delete("1.0","end"), self.text_b.insert("1.0", tb.get("1.0","end-1c")))).pack(side="left", padx=(8,0))
        tk.Button(actions, text="Save results...", command=self.save_compare_results).pack(side="left", padx=(8,0))

def main():
    # Standard Tk entrypoint. Construct the App and hand control to Tk's event loop.
    App().mainloop()

if __name__ == "__main__":
    main()
