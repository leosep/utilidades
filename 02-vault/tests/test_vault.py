import os
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest import mock

from vault.cli import main
from vault.crypto import WrongPassword
from vault.store import Vault, VaultError

FAST = 2**10  # cheap scrypt, for tests only


class VaultTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name) / "vault"
        self.doc = Path(self._tmp.name) / "passport.txt"
        self.doc.write_text("SECRET NUMBER 12345", encoding="utf-8")
        self.vault = Vault.create(self.root, "long-enough-pass-1", scrypt_n=FAST)

    def tearDown(self):
        self.vault.close()
        self._tmp.cleanup()

    def test_nothing_readable_on_disk(self):
        self.vault.add(self.doc, name="John's passport", tags=["Travel"], notes="renew")
        for path in self.root.rglob("*"):
            if path.is_file():
                content = path.read_bytes()
                for secret in (b"SECRET NUMBER", b"John's passport", b"renew", b"passport.txt"):
                    self.assertNotIn(secret, content, path.name)

    def test_roundtrip_search_remove(self):
        doc_id = self.vault.add(self.doc, name="Passport", tags=["travel", "identity"])
        out = self.vault.get(doc_id, Path(self._tmp.name) / "output.txt")
        self.assertEqual(out.read_text(encoding="utf-8"), "SECRET NUMBER 12345")
        self.assertEqual([d.id for d in self.vault.search("TRAVEL passport")], [doc_id])
        self.assertEqual(self.vault.search("missing"), [])
        self.vault.remove(doc_id)
        self.assertEqual(self.vault.list(), [])
        self.assertEqual(list((self.root / "blobs").iterdir()), [])

    def test_search_ignores_accents(self):
        doc_id = self.vault.add(self.doc, name="Cédula de identidad", tags=["Identificación"])
        self.assertEqual([d.id for d in self.vault.search("cedula")], [doc_id])
        self.assertEqual([d.id for d in self.vault.search("IDENTIFICACION")], [doc_id])

    def test_get_does_not_overwrite_without_permission(self):
        doc_id = self.vault.add(self.doc, name="Passport")
        destination = Path(self._tmp.name) / "output.txt"
        destination.write_text("do not lose me", encoding="utf-8")
        with self.assertRaises(VaultError):
            self.vault.get(doc_id, destination)
        self.assertEqual(destination.read_text(encoding="utf-8"), "do not lose me")
        self.vault.get(doc_id, destination, overwrite=True)
        self.assertEqual(destination.read_text(encoding="utf-8"), "SECRET NUMBER 12345")

    def test_corrupt_database_is_reported_clearly(self):
        broken = Path(self._tmp.name) / "broken"
        broken.mkdir()
        (broken / "vault.db").write_bytes(b"this is not a database")
        with self.assertRaises(VaultError) as caught:
            Vault.open(broken, "long-enough-pass-1")
        self.assertIn("Could not read the vault", str(caught.exception))

    def test_expiring_sorted_and_includes_expired(self):
        a = self.vault.add(self.doc, name="Insurance", expires=date(2026, 12, 1))
        b = self.vault.add(self.doc, name="Warranty", expires=date(2026, 10, 1))
        self.vault.add(self.doc, name="No date")
        self.vault.add(self.doc, name="Far away", expires=date(2030, 1, 1))
        due = self.vault.expiring(60, today=date(2026, 11, 17))
        self.assertEqual([d.id for d in due], [b, a])

    def test_wrong_password_and_missing_vault(self):
        with self.assertRaises(WrongPassword):
            Vault.open(self.root, "another-key")
        reopened = Vault.open(self.root, "long-enough-pass-1")
        try:
            self.assertEqual(reopened.list(), [])
        finally:
            reopened.close()
        with self.assertRaises(VaultError):
            Vault.open(Path(self._tmp.name) / "nothing", "x")
        with self.assertRaises(VaultError):
            Vault.create(self.root, "x" * 12, scrypt_n=FAST)

    def test_backup_can_be_opened_as_a_vault(self):
        doc_id = self.vault.add(self.doc, name="Passport", tags=["travel"])
        destination = Path(self._tmp.name) / "backup"
        self.vault.backup(destination)
        copy = Vault.open(destination, "long-enough-pass-1")
        try:
            self.assertEqual([d.name for d in copy.list()], ["Passport"])
            out = copy.get(doc_id, Path(self._tmp.name) / "from-backup.txt")
            self.assertEqual(out.read_text(encoding="utf-8"), "SECRET NUMBER 12345")
        finally:
            copy.close()
        with self.assertRaises(VaultError):
            self.vault.backup(destination)  # refuses to mix with an existing backup

    def test_change_password_reencrypts_documents_and_metadata(self):
        doc_id = self.vault.add(self.doc, name="Passport", tags=["travel", "identity"])
        self.vault.change_password("new-long-pass-2", scrypt_n=FAST)
        self.vault.close()
        with self.assertRaises(WrongPassword):
            Vault.open(self.root, "long-enough-pass-1")
        reopened = Vault.open(self.root, "new-long-pass-2")
        try:
            self.assertEqual([d.id for d in reopened.search("travel")], [doc_id])
            out = reopened.get(doc_id, Path(self._tmp.name) / "after-rekey.txt")
            self.assertEqual(out.read_text(encoding="utf-8"), "SECRET NUMBER 12345")
        finally:
            reopened.close()
        self.vault = Vault.open(self.root, "new-long-pass-2")

    def test_failed_rekey_leaves_the_original_vault_usable(self):
        doc_id = self.vault.add(self.doc, name="Passport")
        real_replace = os.replace
        calls = {"count": 0}

        def flaky_replace(source, target):
            calls["count"] += 1
            if calls["count"] == 3:  # fail while moving the original blobs
                raise OSError("simulated disk failure")
            return real_replace(source, target)

        with mock.patch("vault.store.os.replace", side_effect=flaky_replace):
            with self.assertRaises(OSError):
                self.vault.change_password("new-long-pass-2", scrypt_n=FAST)
        # The vault reconnected with the old key and the document is still readable.
        out = self.vault.get(doc_id, Path(self._tmp.name) / "still-here.txt")
        self.assertEqual(out.read_text(encoding="utf-8"), "SECRET NUMBER 12345")
        self.assertEqual(list(self.root.glob(".rekey-*")), [])
        self.assertEqual(list(self.root.glob(".old-*")), [])
        self.vault.close()
        reopened = Vault.open(self.root, "long-enough-pass-1")
        try:
            self.assertEqual([d.name for d in reopened.list()], ["Passport"])
        finally:
            reopened.close()
        self.vault = Vault.open(self.root, "long-enough-pass-1")

    def test_legacy_database_name_still_opens(self):
        self.vault.close()
        (self.root / "vault.db").rename(self.root / "boveda.db")
        legacy = Vault.open(self.root, "long-enough-pass-1")
        try:
            self.assertEqual(legacy.list(), [])
        finally:
            legacy.close()
        self.vault = Vault.open(self.root, "long-enough-pass-1")  # keep tearDown happy

    def test_change_password_works_on_a_legacy_named_database(self):
        doc_id = self.vault.add(self.doc, name="Old file")
        self.vault.close()
        (self.root / "vault.db").rename(self.root / "boveda.db")
        legacy = Vault.open(self.root, "long-enough-pass-1")
        try:
            legacy.change_password("new-long-pass-2", scrypt_n=FAST)
            out = legacy.get(doc_id, Path(self._tmp.name) / "legacy.txt")
            self.assertEqual(out.read_text(encoding="utf-8"), "SECRET NUMBER 12345")
            self.assertEqual([d.name for d in legacy.list()], ["Old file"])
        finally:
            legacy.close()
        self.vault = Vault.open(self.root, "new-long-pass-2")

    def test_cli_flow(self):
        os.environ["VAULT_PASSWORD"] = "long-enough-pass-2"
        try:
            cli_root = str(Path(self._tmp.name) / "cli")
            self.assertEqual(main(["--path", cli_root, "init"]), 0)
            self.assertEqual(main(["--path", cli_root, "add", str(self.doc), "--tags", "id", "--expires", "2027-01-01"]), 0)
            self.assertEqual(main(["--path", cli_root, "expiring", "--days", "400"]), 0)
            os.environ["VAULT_NEW_PASSWORD"] = "new-long-pass-3"
            self.assertEqual(main(["--path", cli_root, "backup", str(Path(self._tmp.name) / "cli-backup")]), 0)
            self.assertEqual(main(["--path", cli_root, "passwd"]), 0)
            os.environ["VAULT_PASSWORD"] = "new-long-pass-3"
            self.assertEqual(main(["--path", cli_root, "list"]), 0)
            os.environ["VAULT_PASSWORD"] = "wrong"
            self.assertEqual(main(["--path", cli_root, "list"]), 2)
            os.environ["VAULT_PASSWORD"] = "short"
            self.assertEqual(main(["--path", str(Path(self._tmp.name) / "short"), "init"]), 1)
        finally:
            del os.environ["VAULT_PASSWORD"]
            del os.environ["VAULT_NEW_PASSWORD"]


if __name__ == "__main__":
    unittest.main()
