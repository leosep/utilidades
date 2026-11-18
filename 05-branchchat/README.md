# BranchChat

When you regenerate answers or rephrase a question, AI conversations branch out and it is easy to get lost. BranchChat reads your chat export and shows it as a **tree of branches**, marks the chosen branch and exports only the path you care about as Markdown.

## Usage

```bash
python -m branchchat samples/chats_example.json list
python -m branchchat samples/chats_example.json html -c 1 -o tree.html     # open it in the browser
python -m branchchat samples/chats_example.json endings -c 1              # ids of each possible ending
python -m branchchat samples/chats_example.json export -c 1 --ending a2 -o path.md
```

Without `--ending`, `export` uses the chosen branch (the last one active in the conversation).

The original Spanish commands (`listar`, `finales`, `exportar`, `--final`, `--salida`, `--conversacion`) still work.

## Supported formats

| Format | Branches |
|---|---|
| Tree with `mapping` / `current_node` (like the ChatGPT export) | Yes |
| `chat_messages` with `sender` and `text` | No (linear) |
| `messages` with `role` and `content` | No (linear) |

I have not been able to check each service's format with current real exports; the reader is tolerant, but if your file is not recognized, the error states which formats it expects and adding another one in `loaders.py` is easy.

## Privacy

Everything is local. The generated HTML escapes the content and loads nothing external and contains no scripts.

## Tests

```bash
python -m unittest discover -s tests -v
```

No external dependencies. Requires Python 3.10+.
