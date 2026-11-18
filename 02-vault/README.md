# Vault

Store your ID, passport, contracts, warranties and invoices in an encrypted folder on your computer, with expiry alerts. No accounts, no servers, no cloud.

## Security

- The master password becomes a key with **scrypt** (N=2^15); every document and all metadata (name, tags, notes, dates) is encrypted with **Fernet** (AES + HMAC, authenticated).
- No readable name or text is left on disk. The tests verify it.
- If you forget the password **there is no way to recover** the documents.
- It protects you from someone copying the folder, not from malware reading your keyboard or memory while the vault is open. Back up the whole folder.

## Usage

```bash
pip install cryptography
python -m vault init
python -m vault add passport.pdf --name "Passport" --tags travel,identity --expires 2028-05-14
python -m vault list
python -m vault search travel
python -m vault expiring --days 90
python -m vault get 1 --output ~/Downloads
```

If the destination file already exists, `get` refuses to overwrite it: pass `--force` when you really want to replace it.

The default folder is `~/.vault` (or `$VAULT_HOME` / `--path`). For scripts, `VAULT_PASSWORD` skips the prompt (use it carefully). The original names `~/.boveda`, `boveda.db`, `BOVEDA_HOME` and `BOVEDA_PASSWORD` still work, so vaults created by the Spanish version keep opening.

## Optional OCR

`pip install pytesseract pillow` and install Tesseract; with `--ocr` the text of images is stored encrypted and can be searched.

## Tests

```bash
python -m unittest discover -s tests -v
```
