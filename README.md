# Nova Filename Lister

A tiny cross-platform GUI to list filenames from a folder, sort them, preview the result, and write to a text file. Built with Tkinter. Designed for a clean Nova Dark look with pastel pink and dark purple accents.

**Motivation**
* I made this to help sort a Minecraft mod list. You can use it for any folder that needs a quick, tidy list.

---

## Features

* Pick a folder and output file name
* Include files, include folders, or both
* Optional recursion into subfolders
* Case insensitive or natural numeric sort
* Live preview pane
* One click write to `filenames_sorted.txt` or a custom name
* Theme picker with Nova Dark and Light
* Header logo text that reads **nova**

---

## Getting started

### Prerequisites

* Python 3.8 or newer
* Tkinter available in your Python build

The app file is:

* `list_files_nova.py`  ← main GUI script

---

## Quick run

### macOS

```bash
# preferred: run with a Python that has modern Tk
/opt/homebrew/bin/python3.12 list_files_nova.py
```
## Windows

```bash
py list_files_nova.py
# or
python list_files_nova.py
```

## Linux

```bash
python3 list_files_nova.py
```

