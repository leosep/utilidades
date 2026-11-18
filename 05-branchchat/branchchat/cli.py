from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .loaders import load_conversations
from .render import _preview, path_to_markdown, to_html

_ALIASES = {"listar": "list", "finales": "endings", "exportar": "export"}


def _safe_stdout() -> None:
    """Never crash because the Windows console cannot encode a chat title or message."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(errors="replace")
        except (AttributeError, ValueError):
            pass


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="branchchat", description="AI chats as a tree of branches.")
    p.add_argument("file", type=Path, help="JSON exported from your chats")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list", aliases=["listar"], help="List conversations and how many forks they have")
    for name, text, aliases in (("html", "Generate a page with the tree", []),
                                ("endings", "List the possible endings of a conversation", ["finales"]),
                                ("export", "Export only the path to one ending as Markdown", ["exportar"])):
        cmd = sub.add_parser(name, aliases=aliases, help=text)
        cmd.add_argument("-c", "--conversation", "--conversacion", dest="conversation", type=int, default=1,
                         help="Number from `list` (1)")
        if name != "endings":
            cmd.add_argument("-o", "--output", "--salida", dest="output", type=Path, help="Output file")
        if name == "export":
            cmd.add_argument("--ending", "--final", dest="ending", help="Id (or prefix) of the ending message; default is the chosen branch")
    return p


def main(argv: list[str] | None = None) -> int:
    _safe_stdout()
    args = build_parser().parse_args(argv)
    cmd = _ALIASES.get(args.cmd, args.cmd)
    try:
        conversations = load_conversations(args.file)
        if cmd == "list":
            for number, conv in enumerate(conversations, 1):
                print(f"{number:>3}  {conv.title[:45]:<45} {len(conv.messages):>5} msgs  {conv.branch_points():>3} branches")
            return 0

        if not 1 <= args.conversation <= len(conversations):
            raise ValueError(f"The conversation must be between 1 and {len(conversations)}.")
        conv = conversations[args.conversation - 1]

        if cmd == "endings":
            for leaf in conv.leaves():
                mark = "*" if leaf.id == conv.current else " "
                print(f"{mark} {leaf.id[:8]}  {leaf.role:<9} {_preview(leaf.text, 60)}")
            print("\n* = chosen branch")
        elif cmd == "html":
            out = args.output or Path(f"branchchat-{args.conversation}.html")
            out.write_text(to_html(conv), encoding="utf-8")
            print(f"Written: {out}")
        else:  # export
            leaf_id = conv.default_leaf()
            if args.ending:
                exact = [args.ending] if args.ending in conv.messages else []
                matches = exact or [m.id for m in conv.messages.values() if m.id.startswith(args.ending)]
                if len(matches) != 1:
                    raise ValueError(f"The id \"{args.ending}\" " + ("does not exist." if not matches else "is ambiguous; use more characters."))
                leaf_id = matches[0]
            if leaf_id is None:
                raise ValueError("The conversation has no messages.")
            markdown = path_to_markdown(conv, leaf_id)
            if args.output:
                args.output.write_text(markdown, encoding="utf-8")
                print(f"Written: {args.output}")
            else:
                print(markdown)
    except (OSError, ValueError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1
    return 0
