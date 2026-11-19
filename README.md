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
pip install cryptography sv-ttk   # vault, and the theme used by the interfaces
python run_all_tests.py           # Windows, macOS and Linux; Node is only for the photo cleaner test
./run_all_tests.sh                # same thing from a POSIX shell
```

GitHub Actions runs the suite on **Windows and Linux** with Python 3.10 and 3.13. The interface tests run on Windows and, on Linux, under a virtual display when Tk is available. The photo cleaner was also checked end to end in Chromium during development (metadata detection and removal, resizing and the maximum-size limit).

## Backups and recovery

- **Vault:** `python -m vault backup <empty-folder>` or the "Back up vault…" button. The copy is a normal vault and opens with the same password.
- **Finance:** `python -m finance backup -o <file>` or the "Back up…" button. It takes a consistent snapshot even while the app is open.
- **Lost vault password:** there is no recovery. That is the point of the encryption; keep the password and a backup somewhere safe.
- **Deleted documents:** deleting removes the encrypted file, but filesystems and SSDs may keep old blocks. Use full-disk encryption if that matters to you.

## Status

The automated suite covers parsing, storage, encryption, duplicate detection, the command line and the graphical interfaces, and runs in CI on Windows and Linux. **What is still not verified:** real bank exports from every bank, current exports from each AI service (their formats change), and the Windows installers themselves (they require Inno Setup and are built in CI; they are not digitally signed, so Windows SmartScreen warns). Each README states the limits of its tool.

## License

MIT. See `LICENSE`.
