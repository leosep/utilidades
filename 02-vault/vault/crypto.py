"""Key derivation and authenticated encryption (Fernet: AES-128-CBC + HMAC-SHA256)."""
from __future__ import annotations

import base64

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt

DEFAULT_SCRYPT_N = 2**15  # ~32 MB of memory: slow for anyone trying to guess the key
_CHECK_PLAINTEXTS = (b"vault-ok", b"boveda-ok")  # the second one opens vaults created by the Spanish version


class WrongPassword(Exception):
    """The master password does not open this vault."""


def derive_key(password: str, salt: bytes, n: int = DEFAULT_SCRYPT_N) -> bytes:
    raw = Scrypt(salt=salt, length=32, n=n, r=8, p=1).derive(password.encode("utf-8"))
    return base64.urlsafe_b64encode(raw)


def make_check_token(key: bytes) -> bytes:
    return Fernet(key).encrypt(_CHECK_PLAINTEXTS[0])


def verify_key(key: bytes, token: bytes) -> None:
    try:
        if Fernet(key).decrypt(token) not in _CHECK_PLAINTEXTS:
            raise WrongPassword()
    except InvalidToken as error:
        raise WrongPassword() from error


def encrypt(key: bytes, data: bytes) -> bytes:
    return Fernet(key).encrypt(data)


def decrypt(key: bytes, token: bytes) -> bytes:
    return Fernet(key).decrypt(token)
