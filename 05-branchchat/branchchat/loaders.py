"""Chat export readers. Supports trees with branches (the `mapping` format) and linear chats."""
from __future__ import annotations

import json
from pathlib import Path

from .model import Conversation, Message

_ROLE_ALIASES = {"human": "user", "assistant": "assistant", "user": "user"}


def _text_of(content) -> str:
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, dict):
        parts = content.get("parts")
        if parts is None and "text" in content:
            parts = [content["text"]]
        content = parts or []
    if isinstance(content, list):
        pieces = []
        for part in content:
            if isinstance(part, str):
                pieces.append(part)
            elif isinstance(part, dict) and isinstance(part.get("text"), str):
                pieces.append(part["text"])
        return "\n".join(p for p in pieces if p).strip()
    return ""


def _from_mapping(item: dict) -> Conversation:
    """Tree with {id, parent, children, message} nodes. Nodes without text are skipped, not their children."""
    mapping: dict = item["mapping"]

    def effective_parent(node_id: str) -> str | None:
        parent = mapping[node_id].get("parent")
        seen: set[str] = set()
        while parent is not None and parent in mapping and not _kept(parent):
            if parent in seen:
                raise ValueError("The chat export contains a cycle in its parent links.")
            seen.add(parent)
            parent = mapping[parent].get("parent")
        return parent if parent in mapping else None

    def _kept(node_id: str) -> bool:
        message = mapping[node_id].get("message")
        return bool(message) and message.get("author", {}).get("role") in ("user", "assistant") and bool(_text_of(message.get("content")))

    messages: dict[str, Message] = {}
    order = list(mapping)
    for node_id in order:
        if not _kept(node_id):
            continue
        message = mapping[node_id]["message"]
        messages[node_id] = Message(node_id, message["author"]["role"], _text_of(message.get("content")), effective_parent(node_id))
    for node_id in order:  # `order` keeps the order in which the branches were created
        message = messages.get(node_id)
        if message and message.parent:
            messages[message.parent].children.append(node_id)

    _reject_cycles(messages)
    current = item.get("current_node")
    while current is not None and current not in messages:  # the current leaf may be an empty node
        current = mapping.get(current, {}).get("parent")
    roots = [m.id for m in messages.values() if m.parent is None]
    return Conversation(item.get("title") or "Untitled", messages, roots, current)


def _reject_cycles(messages: dict[str, Message]) -> None:
    """A cyclic `mapping` would render an empty page: fail with a clear message instead."""
    for start in messages:
        seen: set[str] = set()
        node: str | None = start
        while node is not None and node in messages:
            if node in seen:
                raise ValueError("The chat export contains a cycle in its parent links.")
            seen.add(node)
            node = messages[node].parent


def _from_linear(title: str, entries: list[tuple[str, str]]) -> Conversation:
    messages: dict[str, Message] = {}
    previous = None
    for index, (role, text) in enumerate(entries):
        message = Message(f"m{index}", role, text, previous)
        messages[message.id] = message
        if previous:
            messages[previous].children.append(message.id)
        previous = message.id
    roots = ["m0"] if messages else []
    return Conversation(title, messages, roots, previous)


def _from_chat_messages(item: dict) -> Conversation:
    entries = []
    for message in item.get("chat_messages", []):
        text = _text_of(message.get("text") or message.get("content"))
        role = _ROLE_ALIASES.get(message.get("sender", ""), "")
        if text and role:
            entries.append((role, text))
    return _from_linear(item.get("name") or "Untitled", entries)


def load_conversations(path: Path) -> list[Conversation]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(data, dict):
        data = [data]
    if not isinstance(data, list):
        raise ValueError("The file does not have the format of a chat export.")
    result = []
    for item in data:
        if not isinstance(item, dict):
            continue
        if "mapping" in item:
            result.append(_from_mapping(item))
        elif "chat_messages" in item:
            result.append(_from_chat_messages(item))
        elif "messages" in item:
            entries = [(_ROLE_ALIASES.get(m.get("role", ""), ""), _text_of(m.get("content"))) for m in item["messages"]]
            result.append(_from_linear(item.get("title") or "Untitled", [e for e in entries if e[0] and e[1]]))
    if not result:
        raise ValueError("I found no recognizable conversations (formats: tree with 'mapping', 'chat_messages' or 'messages').")
    return result
