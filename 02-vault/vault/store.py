"""Vault on disk: SQLite with encrypted metadata + one encrypted file per document."""
from __future__ import annotations

import json
import os
import secrets
import sqlite3
import unicodedata
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path

from . import crypto

_SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value BLOB NOT NULL);
CREATE TABLE IF NOT EXISTS docs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    blob_name TEXT NOT NULL UNIQUE,
    meta BLOB NOT NULL,
    created TEXT NOT NULL
);
"""
_IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp"}
_DB_NAME = "vault.db"
_LEGACY_DB_NAME = "boveda.db"


def default_root() -> Path:
    """`~/.vault`, or the old `~/.boveda` when it already exists."""
    explicit = os.environ.get("VAULT_HOME") or os.environ.get("BOVEDA_HOME")
    if explicit:
        return Path(explicit)
    modern = Path.home() / ".vault"
    legacy = Path.home() / ".boveda"
    return modern if modern.exists() or not legacy.exists() else legacy


def db_path(root: Path) -> Path:
    """Prefer the new database name, but keep opening vaults created before the rename."""
    root = Path(root)
    modern = root / _DB_NAME
    if modern.exists():
        return modern
    legacy = root / _LEGACY_DB_NAME
    return legacy if legacy.exists() else modern


class VaultError(Exception):
    pass


def _fold(text: str) -> str:
    """Lowercase and strip accents, so 'cédula' and 'cedula' match."""
    return unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()


@dataclass
class Document:
    id: int
    name: str
    filename: str
    size: int
    tags: list[str] = field(default_factory=list)
    notes: str = ""
    text: str = ""
    expires: date | None = None

    def matches(self, query: str) -> bool:
        haystack = _fold(" ".join([self.name, self.filename, self.notes, self.text, *self.tags]))
        return all(term in haystack for term in _fold(query).split())


def extract_text(path: Path) -> str:
    """Optional OCR: works only if pytesseract, pillow and Tesseract are installed."""
    if path.suffix.lower() not in _IMAGE_SUFFIXES:
        return ""
    try:
        import pytesseract
        from PIL import Image

        return pytesseract.image_to_string(Image.open(path), lang="eng").strip()
    except Exception:  # noqa: BLE001 - OCR must never prevent saving the document
        return ""


class Vault:
    def __init__(self, root: Path, key: bytes):
        self.root = Path(root)
        self._key = key
        self._db = sqlite3.connect(db_path(self.root))

    # -- creation and opening ------------------------------------------------
    @classmethod
    def create(cls, root: Path, password: str, scrypt_n: int = crypto.DEFAULT_SCRYPT_N) -> "Vault":
        root = Path(root)
        if db_path(root).exists() or (root / _DB_NAME).exists():
            raise VaultError(f"A vault already exists in {root}")
        (root / "blobs").mkdir(parents=True, exist_ok=True)
        salt = secrets.token_bytes(16)
        key = crypto.derive_key(password, salt, scrypt_n)
        db = sqlite3.connect(root / _DB_NAME)
        db.executescript(_SCHEMA)
        db.executemany(
            "INSERT INTO meta VALUES (?, ?)",
            [("salt", salt), ("scrypt_n", str(scrypt_n).encode()), ("check", crypto.make_check_token(key))],
        )
        db.commit()
        db.close()
        return cls(root, key)

    @classmethod
    def open(cls, root: Path, password: str) -> "Vault":
        path = db_path(root)
        if not path.exists():
            raise VaultError(f"There is no vault in {root}. Create one with: vault init")
        db = sqlite3.connect(path)
        try:
            values = dict(db.execute("SELECT key, value FROM meta"))
        except sqlite3.DatabaseError as error:
            raise VaultError(f"Could not read the vault in {root}: {error}") from error
        finally:
            db.close()
        missing = {"salt", "scrypt_n", "check"} - set(values)
        if missing:
            raise VaultError(f"{path} is not a vault database (missing metadata: {', '.join(sorted(missing))}).")
        try:
            key = crypto.derive_key(password, values["salt"], int(values["scrypt_n"]))
        except (KeyError, TypeError, ValueError) as error:
            raise VaultError(f"{path} has damaged vault metadata.") from error
        crypto.verify_key(key, values["check"])
        return cls(root, key)

    def close(self) -> None:
        self._db.close()

    # -- operations ------------------------------------------------------------
    def add(self, source: Path, name: str | None = None, tags: list[str] | None = None,
            notes: str = "", expires: date | None = None, ocr: bool = False) -> int:
        source = Path(source)
        data = source.read_bytes()
        meta = {
            "name": name or source.stem,
            "filename": source.name,
            "size": len(data),
            "tags": [t.strip().lower() for t in (tags or []) if t.strip()],
            "notes": notes,
            "text": extract_text(source) if ocr else "",
            "expires": expires.isoformat() if expires else None,
        }
        blob_name = secrets.token_hex(16) + ".bin"
        target = self.root / "blobs" / blob_name
        tmp = target.with_suffix(".tmp")
        tmp.write_bytes(crypto.encrypt(self._key, data))
        os.replace(tmp, target)  # atomic write: a partial file is never left behind
        cursor = self._db.execute(
            "INSERT INTO docs (blob_name, meta, created) VALUES (?, ?, ?)",
            (blob_name, crypto.encrypt(self._key, json.dumps(meta).encode()), datetime.now(timezone.utc).isoformat()),
        )
        self._db.commit()
        return int(cursor.lastrowid)

    def _row_to_doc(self, doc_id: int, blob: bytes) -> Document:
        meta = json.loads(crypto.decrypt(self._key, blob))
        expires = date.fromisoformat(meta["expires"]) if meta.get("expires") else None
        return Document(doc_id, meta["name"], meta["filename"], meta["size"], meta["tags"],
                        meta["notes"], meta.get("text", ""), expires)

    def list(self) -> list[Document]:
        rows = self._db.execute("SELECT id, meta FROM docs ORDER BY id").fetchall()
        return [self._row_to_doc(i, m) for i, m in rows]

    def search(self, query: str) -> list[Document]:
        return [d for d in self.list() if d.matches(query)]

    def expiring(self, within_days: int, today: date | None = None) -> list[Document]:
        today = today or date.today()
        due = [d for d in self.list() if d.expires and (d.expires - today).days <= within_days]
        return sorted(due, key=lambda d: d.expires)

    def get(self, doc_id: int, destination: Path, overwrite: bool = False) -> Path:
        row = self._db.execute("SELECT blob_name FROM docs WHERE id = ?", (doc_id,)).fetchone()
        if row is None:
            raise VaultError(f"Document {doc_id} does not exist")
        doc = next(d for d in self.list() if d.id == doc_id)
        destination = Path(destination)
        if destination.is_dir():
            destination = destination / doc.filename
        if destination.exists() and not overwrite:
            raise VaultError(f"{destination} already exists. Choose another name or overwrite it.")
        destination.write_bytes(crypto.decrypt(self._key, (self.root / "blobs" / row[0]).read_bytes()))
        return destination

    def remove(self, doc_id: int) -> None:
        row = self._db.execute("SELECT blob_name FROM docs WHERE id = ?", (doc_id,)).fetchone()
        if row is None:
            raise VaultError(f"Document {doc_id} does not exist")
        (self.root / "blobs" / row[0]).unlink(missing_ok=True)
        self._db.execute("DELETE FROM docs WHERE id = ?", (doc_id,))
        self._db.commit()
