"""Graphical interface entry point (also used by PyInstaller)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "shared"))

from branchchat.gui import main  # noqa: E402

if __name__ == "__main__":
    main()
