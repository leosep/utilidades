# Windows installers

Each app has its own double-click installer: `Install-BillCutter-1.0.0.exe`, `Install-Vault-1.0.0.exe`, `Install-Photo-Cleaner-1.0.0.exe`, `Install-Finance-1.0.0.exe` and `Install-BranchChat-1.0.0.exe`.

## For people who use them

1. Double-click the installer and press **Next → Install → Finish**. It runs in English.
2. It does not ask for administrator permissions: it installs only for your user.
3. It creates a Start menu shortcut and, if you tick the box, a desktop one.
4. To remove it: **Settings → Apps → Installed apps**. Your data is not deleted.

**Windows warning:** because the installers are not digitally signed, Windows may show "Windows protected your PC". Press **More info → Run anyway**. A (paid) code-signing certificate removes that warning. Verify the installers with `SHA256SUMS.txt`.

Where your data is stored (back up these folders): Vault in `C:\Users\YOUR_USER\.vault`, Finance in `C:\Users\YOUR_USER\.finance`. If something fails, the error log is in `%LOCALAPPDATA%\UsefulUtilities`.

## For the person who builds them (you)

The `.exe` files are built on Windows; they cannot be generated from Linux or macOS. Three ways:

**A) With GitHub, installing nothing (recommended).** Upload this folder to a repository. In the *Actions* tab run "Build installers" (or create a `v1.0.0` tag and they are published in *Releases*). Download the five `.exe` files from the result.

**B) On your Windows machine with a double click.** Install [Python 3.10+](https://www.python.org/downloads/) (tick *Add to PATH*) and [Inno Setup 6](https://jrsoftware.org/isdl.php), then run `Build-Installers.bat`. The result is in `dist\installers`.

**C) Manual:** `python packaging/build.py --apps vault finance --version 1.1.0`.

Each app has a fixed identifier, so installing a new version **updates** the previous one instead of duplicating it. To change the version, use `--version` or a new tag.
