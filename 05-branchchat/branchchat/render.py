from __future__ import annotations

from html import escape

from .model import Conversation, Message

_ROLE_LABEL = {"user": "You", "assistant": "AI"}

_CSS = """
:root{--ink:#1c2430;--muted:#5d6b78;--bg:#eef1f4;--panel:#fff;--line:#cdd5dc;--user:#e4ecf8;--ai:#fff;--main:#0e6b5e}
body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.55 system-ui,-apple-system,"Segoe UI",sans-serif}
main{max-width:56rem;margin:0 auto;padding:2rem 1.25rem 4rem}
h1{font:700 1.8rem/1.2 Cambria,Georgia,serif;margin:0 0 .25rem}
.meta{color:var(--muted);margin:0 0 1.5rem}
.msg{border:1px solid var(--line);border-radius:6px;padding:.7rem .9rem;margin:.6rem 0;background:var(--ai)}
.msg.user{background:var(--user)}
.msg.main{border-left:4px solid var(--main)}
.who{font-weight:700;font-size:.9rem}
.who code{font-weight:400;color:var(--muted);font-size:.8rem}
.text{white-space:pre-wrap;overflow-wrap:anywhere;margin:.2rem 0 0}
details.branch{margin:.6rem 0 .6rem 1rem;padding-left:.9rem;border-left:2px dashed var(--line)}
details.branch.main{border-left:2px solid var(--main)}
summary{cursor:pointer;padding:.3rem 0;font-weight:600}
summary .tag{font-size:.8rem;color:var(--main);margin-left:.4rem}
summary:focus-visible{outline:3px solid #1d4ed8;outline-offset:2px}
.fork{margin:1rem 0 .2rem;font-weight:700}
"""


def _preview(text: str, limit: int = 70) -> str:
    flat = " ".join(text.split())
    return flat if len(flat) <= limit else flat[: limit - 3] + "..."  # ASCII: the Windows console may not encode "…"


def _message_html(message: Message, on_main: bool) -> str:
    classes = f"msg {escape(message.role)}" + (" main" if on_main else "")
    who = _ROLE_LABEL.get(message.role, message.role)
    return (f'<div class="{classes}"><div class="who">{escape(who)} <code>{escape(message.id[:8])}</code></div>'
            f'<p class="text">{escape(message.text)}</p></div>')


def _branch_html(conv: Conversation, start_id: str, main: set[str], index: int) -> str:
    on_main = start_id in main
    tag = ' <span class="tag">chosen branch</span>' if on_main else ""
    summary = f"Branch {index}: {escape(_preview(conv.messages[start_id].text))}{tag}"
    return (f'<details class="branch{" main" if on_main else ""}"{" open" if on_main else ""}>'
            f"<summary>{summary}</summary>{_chain_html(conv, start_id, main)}</details>")


def _chain_html(conv: Conversation, start_id: str, main: set[str]) -> str:
    """Walk the linear chain without recursion; only branches are recursive."""
    parts: list[str] = []
    node = conv.messages[start_id]
    while True:
        parts.append(_message_html(node, node.id in main))
        if len(node.children) == 1:
            node = conv.messages[node.children[0]]
            continue
        if len(node.children) > 1:
            parts.append(f'<div class="fork">Here there are {len(node.children)} branches</div>')
            parts += [_branch_html(conv, child, main, i) for i, child in enumerate(node.children, 1)]
        return "".join(parts)


def to_html(conv: Conversation) -> str:
    main = conv.main_path_ids()
    if len(conv.roots) > 1:
        body = "".join(_branch_html(conv, root, main, i) for i, root in enumerate(conv.roots, 1))
    else:
        body = "".join(_chain_html(conv, root, main) for root in conv.roots)
    info = f"{len(conv.messages)} messages · {conv.branch_points()} branches · {len(conv.leaves())} possible endings"
    return (f'<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            f"<title>{escape(conv.title)}</title><style>{_CSS}</style></head><body><main>"
            f'<h1>{escape(conv.title)}</h1><p class="meta">{escape(info)}. The green line marks the chosen branch.</p>{body}</main></body></html>')


def path_to_markdown(conv: Conversation, leaf_id: str) -> str:
    lines = [f"# {conv.title}", ""]
    for message in conv.path_to(leaf_id):
        lines += [f"**{_ROLE_LABEL.get(message.role, message.role)}**", "", message.text, ""]
    return "\n".join(lines).rstrip() + "\n"
