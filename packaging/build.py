"""Build the executables (PyInstaller) and installers (Inno Setup) for the five apps.

    python packaging/build.py                       # everything, on Windows with Inno Setup installed
    python packaging/build.py --apps vault finance --version 1.2.0
    python packaging/build.py --skip-installer      # executables only (works on Linux/macOS for testing)

Result: dist/installers/Install-<App>-<version>.exe and SHA256SUMS.txt
"""
from __future__ import annotations

import argparse
import hashlib
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HERE = Path(__file__).resolve().parent
BUILD = ROOT / "build"
DIST = ROOT / "dist"
INSTALLERS = DIST / "installers"

# Fixed AppId per app: a new version updates the previous one instead of duplicating it.
APPS = {
    "billcutter": dict(name="BillCutter", exe="BillCutter.exe", folder="01-billcutter", guid="{{5E0C3B1A-7D24-4F6B-9A31-C1B7D2E48F01}"),
    "vault": dict(name="Vault", exe="Vault.exe", folder="02-vault", guid="{{A7F4D9C2-18B3-4E55-8C60-3D9E1B72A502}"),
    "photo-cleaner": dict(name="Photo Cleaner", exe="index.html", folder="03-photo-cleaner", guid="{{2B91E6F8-4C0D-47A9-B5E3-8F16C7D03A03}", web=True),
    "finance": dict(name="Finance", exe="Finance.exe", folder="04-finance", guid="{{C3D8A015-9E72-4B1F-A64D-5E20F8B91C04}"),
    "branchchat": dict(name="BranchChat", exe="BranchChat.exe", folder="05-branchchat", guid="{{F18A6E47-D3B5-4092-8E7C-A94B0D6C5E05}"),
}


# Heavy libraries the apps do not use (Vault's optional OCR would also require installing Tesseract).
EXCLUDES = ["numpy", "scipy", "pandas", "matplotlib", "PIL", "pytesseract", "IPython", "pytest"]


def run(cmd: list[str]) -> None:
    print(">", " ".join(map(str, cmd)))
    subprocess.run(cmd, check=True)


def build_executable(key: str, meta: dict) -> Path:
    project = ROOT / meta["folder"]
    icon = ROOT / "assets" / f"{key}.ico"
    work = BUILD / key
    cmd = [
        sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--windowed",
        "--name", meta["exe"].removesuffix(".exe"),
        "--distpath", str(DIST), "--workpath", str(work), "--specpath", str(work),
        "--paths", str(project), "--paths", str(ROOT / "shared"),
        "--collect-data", "sv_ttk",
        "--add-data", f"{icon}{os.pathsep}assets",
    ]
    for module in EXCLUDES:
        cmd += ["--exclude-module", module]
    if sys.platform == "win32":
        cmd += ["--icon", str(icon)]
    run(cmd + [str(project / "app_gui.py")])
    folder = DIST / meta["exe"].removesuffix(".exe")
    shutil.copy2(icon, folder / "app.ico")
    return folder


def prepare_web_app(key: str, meta: dict) -> Path:
    folder = DIST / "PhotoCleaner"
    shutil.rmtree(folder, ignore_errors=True)
    folder.mkdir(parents=True)
    shutil.copy2(ROOT / meta["folder"] / "index.html", folder / "index.html")
    shutil.copy2(ROOT / "assets" / f"{key}.ico", folder / "app.ico")
    return folder


def find_iscc() -> str | None:
    found = shutil.which("iscc") or shutil.which("ISCC")
    if found:
        return found
    for base in (os.environ.get("ProgramFiles(x86)"), os.environ.get("ProgramFiles"), os.environ.get("LOCALAPPDATA")):
        if base:
            for sub in ("Inno Setup 6", "Programs/Inno Setup 6"):
                candidate = Path(base) / sub / "ISCC.exe"
                if candidate.exists():
                    return str(candidate)
    return None


def build_installer(iscc: str, key: str, meta: dict, source: Path, version: str) -> Path:
    output_name = f"Install-{meta['name'].replace(' ', '-')}-{version}"
    run([
        iscc, f"/DAppName={meta['name']}", f"/DAppId={meta['guid']}", f"/DAppVersion={version}",
        f"/DSourceDir={source}", f"/DExeName={meta['exe']}", f"/DIconFile={ROOT / 'assets' / (key + '.ico')}",
        f"/DOutputDir={INSTALLERS}", f"/DOutputName={output_name}", str(HERE / "installer.iss"),
    ])
    return INSTALLERS / f"{output_name}.exe"


def write_checksums(files: list[Path]) -> None:
    lines = [f"{hashlib.sha256(f.read_bytes()).hexdigest()}  {f.name}" for f in files]
    (INSTALLERS / "SHA256SUMS.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--apps", nargs="+", choices=list(APPS), default=list(APPS))
    parser.add_argument("--version", default="1.0.0")
    parser.add_argument("--skip-installer", action="store_true", help="Do not create the installer (executables only)")
    args = parser.parse_args()
    version = args.version.lstrip("v")

    run([sys.executable, str(HERE / "make_icons.py")])
    iscc = None
    if not args.skip_installer:
        iscc = find_iscc()
        if iscc is None:
            print("I cannot find Inno Setup (ISCC.exe). Install it from https://jrsoftware.org/isdl.php "
                  "or run with --skip-installer.", file=sys.stderr)
            return 1
        INSTALLERS.mkdir(parents=True, exist_ok=True)

    built: list[Path] = []
    for key in args.apps:
        meta = APPS[key]
        source = prepare_web_app(key, meta) if meta.get("web") else build_executable(key, meta)
        if iscc:
            built.append(build_installer(iscc, key, meta, source, version))
    if built:
        write_checksums(built)
        print("\nInstallers ready in", INSTALLERS)
        for f in built:
            print("  ", f.name)
    return 0


if __name__ == "__main__":
    sys.exit(main())
