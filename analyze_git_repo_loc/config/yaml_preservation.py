"""Preserve selected YAML blocks across generated config writes.

Description:
    Provides small dependency-free helpers for carrying repository selections and
    commented repository candidates forward when config files are regenerated.
Functions:
    preserve_repository_blocks:
        Append preserved repository blocks from existing YAML text to new YAML.
"""

from __future__ import annotations


def _is_top_level_key(line: str) -> bool:
    """Return whether a line starts a non-comment top-level YAML key."""
    stripped = line.strip()
    return bool(stripped) and not line.startswith((" ", "\t", "#")) and ":" in line


def _extract_active_repository_block(lines: list[str]) -> list[str]:
    """Extract the top-level active repositories block from YAML lines."""
    for index, line in enumerate(lines):
        if line.strip() != "repositories:" or line.startswith("#"):
            continue
        block = [line]
        for candidate in lines[index + 1 :]:
            if _is_top_level_key(candidate):
                break
            block.append(candidate)
        return block
    return []


def _extract_commented_repository_blocks(lines: list[str]) -> list[list[str]]:
    """Extract top-level commented repository template blocks from YAML lines."""
    blocks: list[list[str]] = []
    index = 0
    while index < len(lines):
        line = lines[index]
        if line.lstrip() != line or not line.strip().startswith("# repositories:"):
            index += 1
            continue
        block = [line]
        index += 1
        while index < len(lines):
            candidate = lines[index]
            if candidate.strip() and not candidate.strip().startswith("#"):
                break
            if candidate.strip().startswith("#"):
                block.append(candidate)
            elif block:
                block.append(candidate)
            index += 1
        blocks.append(block)
    return blocks


def _append_unique_block(target: list[str], block: list[str]) -> None:
    """Append a block when its text is not already present."""
    if not block:
        return
    target_text = "\n".join(target)
    block_text = "\n".join(block)
    if block_text in target_text:
        return
    if target and target[-1].strip():
        target.append("")
    target.extend(block)


def preserve_repository_blocks(
    rendered_text: str,
    existing_text: str | None,
    *,
    preserve_active: bool,
    preserve_commented: bool = True,
) -> str:
    """Append preserved repository blocks from existing YAML text to new YAML."""
    if not existing_text:
        return rendered_text
    rendered_lines = rendered_text.rstrip("\n").splitlines()
    existing_lines = existing_text.rstrip("\n").splitlines()
    if preserve_active and "repositories:" not in {
        line.strip() for line in rendered_lines if not line.startswith("#")
    }:
        _append_unique_block(
            rendered_lines,
            _extract_active_repository_block(existing_lines),
        )
    if preserve_commented:
        for block in _extract_commented_repository_blocks(existing_lines):
            _append_unique_block(rendered_lines, block)
    return "\n".join(rendered_lines).rstrip("\n") + "\n"
