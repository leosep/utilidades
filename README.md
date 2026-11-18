# Useful Utilities

Five small, local, no-cloud tools, each with a **graphical interface** and a double-click **Windows installer** (see `INSTALLERS.md`). Every folder has its own README and also works from the command line.

| Folder | What it solves | Technology |
|---|---|---|
| `01-billcutter` | Finds subscriptions and recurring charges in your bank CSV | Python (no dependencies) |
| `02-vault` | Stores important documents encrypted and warns about expiry dates | Python + `cryptography` |
| `03-photo-cleaner` | Removes location and metadata from photos and shrinks them | HTML/JS in a single file |
| `04-finance` | Imports transactions, categorizes with rules and summarizes by month | Python (no dependencies) |
| `05-branchchat` | Shows AI chats as a tree of branches and exports one path | Python (no dependencies) |

## Why these technologies

Python for the command-line tools: it installs on any system, needs no compilation and the tests run in seconds. Plain HTML for the photo cleaner because it opens with a double click and the files never leave the browser.

## Graphical interface

Built with Tkinter and the Sun Valley theme (`sv-ttk`), with a shared style in `shared/uikit.py`. To open it from the source: `python app_gui.py` inside each folder (the photo cleaner opens with a double click on `index.html`). It needs `pip install sv-ttk`, and on Linux `python3-tk`.

## Test everything

```bash
pip install cryptography sv-ttk  # cryptography: vault · sv-ttk: interfaces
./run_all_tests.sh              # needs Python 3.10+ and Node (only for the photo cleaner test)
```

## Status

Every project has automated tests that pass, including the interface tests under a virtual display, and the packaged executables were checked by starting them on Linux. **They have not been tested on Windows**, nor the `.exe` installers (they require Windows and Inno Setup), nor with real bank files or current exports from each service, nor the photo cleaner page in a real browser (only its metadata reader, with synthetic JPEGs). The READMEs state the limits of each tool.
