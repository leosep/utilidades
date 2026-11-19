from __future__ import annotations

import argparse
import getpass
import os
import sys
from datetime import date
from pathlib import Path

from .crypto import WrongPassword
from .store import Document, Vault, VaultError, default_root


def _password(confirm: bool = False) -> str:
    env = os.environ.get("VAULT_PASSWORD") or os.environ.get("BOVEDA_PASSWORD")
    if env:
        if confirm and len(env) < 10:
            raise VaultError("Use at least 10 characters: if you forget it, the documents cannot be recovered.")
        return env
    first = getpass.getpass("Master password: ")
    if confirm and getpass.getpass("Repeat it: ") != first:
        raise VaultError("The passwords do not match.")
    if confirm and len(first) < 10:
        raise VaultError("Use at least 10 characters: if you forget it, the documents cannot be recovered.")
    return first


def _new_password() -> str:
    env = os.environ.get("VAULT_NEW_PASSWORD") or os.environ.get("BOVEDA_NEW_PASSWORD")
    if env:
        if len(env) < 10:
            raise VaultError("Use at least 10 characters: if you forget it, the documents cannot be recovered.")
        return env
    first = getpass.getpass("New master password: ")
    if len(first) < 10:
        raise VaultError("Use at least 10 characters: if you forget it, the documents cannot be recovered.")
    if getpass.getpass("Repeat it: ") != first:
        raise VaultError("The passwords do not match.")
    return first


def _row(doc: Document, today: date) -> str:
    status = ""
    if doc.expires:
        days = (doc.expires - today).days
        status = f"expired {-days} d ago" if days < 0 else f"expires in {days} d ({doc.expires})"
    tags = ",".join(doc.tags)
    return f"{doc.id:>4}  {doc.name:<28} {tags:<22} {status}"


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="vault", description="Local encrypted document vault.")
    p.add_argument("--path", "--ruta", dest="path", type=Path, default=None,
                   help="Vault folder (default ~/.vault or $VAULT_HOME)")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("init", help="Create the vault")
    add = sub.add_parser("add", help="Store a document")
    add.add_argument("file", type=Path)
    add.add_argument("--name", "--nombre", dest="name")
    add.add_argument("--tags", "--etiquetas", dest="tags", default="", help="Comma-separated")
    add.add_argument("--notes", "--notas", dest="notes", default="")
    add.add_argument("--expires", "--vence", dest="expires", type=date.fromisoformat, help="yyyy-mm-dd")
    add.add_argument("--ocr", action="store_true", help="Extract text from images (requires pytesseract)")
    sub.add_parser("list", help="List documents")
    search = sub.add_parser("search", help="Search by name, tags, notes or text")
    search.add_argument("text")
    get = sub.add_parser("get", help="Decrypt and extract a document")
    get.add_argument("id", type=int)
    get.add_argument("--output", "--salida", dest="output", type=Path, default=Path("."))
    get.add_argument("--force", "--forzar", dest="force", action="store_true",
                     help="Overwrite the file if it already exists")
    rm = sub.add_parser("remove", help="Delete a document")
    rm.add_argument("id", type=int)
    exp = sub.add_parser("expiring", help="Expired or soon-to-expire documents")
    exp.add_argument("--days", "--dias", dest="days", type=int, default=60)
    sub.add_parser("passwd", aliases=["contrasena"], help="Change the master password")
    bak = sub.add_parser("backup", aliases=["respaldo"], help="Copy the vault to another folder")
    bak.add_argument("destination", type=Path, help="New, empty folder")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root = args.path or default_root()
    today = date.today()
    try:
        if args.cmd == "init":
            Vault.create(root, _password(confirm=True)).close()
            print(f"Vault created in {root}")
            return 0
        vault = Vault.open(root, _password())
        try:
            if args.cmd == "add":
                tags = [t for t in args.tags.split(",")]
                doc_id = vault.add(args.file, args.name, tags, args.notes, args.expires, args.ocr)
                print(f"Saved with id {doc_id}")
            elif args.cmd in ("list", "search"):
                docs = vault.list() if args.cmd == "list" else vault.search(args.text)
                if docs:
                    print("\n".join(_row(d, today) for d in docs))
                else:
                    print("Your vault is empty." if args.cmd == "list" else "No results.")
            elif args.cmd == "get":
                print(f"Saved to {vault.get(args.id, args.output, overwrite=args.force)}")
            elif args.cmd == "remove":
                vault.remove(args.id)
                print("Deleted.")
            elif args.cmd == "expiring":
                docs = vault.expiring(args.days, today)
                print("\n".join(_row(d, today) for d in docs) or f"Nothing expires in the next {args.days} days.")
            elif args.cmd == "passwd":
                vault.change_password(_new_password())
                print("Password changed. The documents were re-encrypted.")
            elif args.cmd == "backup":
                print(f"Backup saved to {vault.backup(args.destination)}")
        finally:
            vault.close()
    except WrongPassword:
        print("Wrong password.", file=sys.stderr)
        return 2
    except (VaultError, OSError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1
    return 0
