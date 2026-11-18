from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Message:
    id: str
    role: str                      # "user" | "assistant" | others
    text: str
    parent: str | None = None
    children: list[str] = field(default_factory=list)


@dataclass
class Conversation:
    title: str
    messages: dict[str, Message]
    roots: list[str]
    current: str | None            # leaf of the "chosen" branch (the last one used)

    def path_to(self, message_id: str) -> list[Message]:
        """Messages from the root down to `message_id`."""
        chain: list[Message] = []
        seen: set[str] = set()
        node = self.messages.get(message_id)
        while node is not None:
            if node.id in seen:
                raise ValueError("The conversation contains a cycle in its parent links.")
            seen.add(node.id)
            chain.append(node)
            node = self.messages.get(node.parent) if node.parent else None
        return chain[::-1]

    def main_path_ids(self) -> set[str]:
        return {m.id for m in self.path_to(self.current)} if self.current else set()

    def leaves(self) -> list[Message]:
        return [m for m in self.messages.values() if not m.children]

    def branch_points(self) -> int:
        return sum(1 for m in self.messages.values() if len(m.children) > 1) + max(0, len(self.roots) - 1)

    def default_leaf(self) -> str | None:
        if self.current and self.current in self.messages:
            return self.current
        leaves = self.leaves()
        return leaves[-1].id if leaves else None
