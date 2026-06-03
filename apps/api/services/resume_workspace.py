"""Structured resume document workspaces for surgical AI edits."""

from __future__ import annotations

import hashlib
import html
import json
import logging
import os
import re
import shutil
import subprocess
import tempfile
import uuid
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

TEXT_UNIT_KINDS = {"header_name", "contact", "paragraph", "role_meta", "bullet", "item", "skill"}
ORDINALS = {
    "first": 0,
    "1st": 0,
    "second": 1,
    "2nd": 1,
    "third": 2,
    "3rd": 2,
    "fourth": 3,
    "4th": 3,
    "fifth": 4,
    "5th": 4,
}
STOP_WORDS = {
    "and",
    "for",
    "from",
    "make",
    "more",
    "the",
    "this",
    "that",
    "with",
    "under",
    "bullet",
    "tighten",
    "rewrite",
    "improve",
}


class ResumeWorkspaceError(Exception):
    """Base error for resume workspace operations."""


class UnitResolutionError(ResumeWorkspaceError):
    """Raised when a request cannot be resolved to one resume unit."""

    def __init__(self, reason: str, candidates: list[dict[str, Any]] | None = None):
        super().__init__(reason)
        self.reason = reason
        self.candidates = candidates or []


class PatchMismatchError(ResumeWorkspaceError):
    """Raised when a scoped patch cannot be safely applied."""

    def __init__(self, reason: str, current_text: str, target_unit_id: str):
        super().__init__(reason)
        self.reason = reason
        self.current_text = current_text
        self.target_unit_id = target_unit_id


@dataclass
class PatchParts:
    target_unit_id: str
    search: str
    replace: str


def utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def html_hash(html_content: str | None) -> str:
    return hashlib.sha256((html_content or "").encode("utf-8")).hexdigest()


def slugify(value: str, fallback: str = "section") -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")
    return slug or fallback


def normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def normalize_for_match(value: str) -> str:
    value = normalize_text(value).lower()
    return re.sub(r"[^\w\s%$.-]", "", value)


def word_count(value: str) -> int:
    return len(re.findall(r"\b[\w'-]+\b", value or ""))


def text_preview(value: str, limit: int = 120) -> str:
    value = normalize_text(value)
    if len(value) <= limit:
        return value
    return value[: limit - 1].rstrip() + "..."


def node_text(node: Any) -> str:
    return normalize_text(node.get_text(" ", strip=True))


def ensure_section(document: dict[str, Any], title: str) -> dict[str, Any]:
    base_slug = slugify(title)
    existing = {
        section["id"]
        for section in document["sections"]
        if section.get("kind") == "section"
    }
    section_id = f"section.{base_slug}"
    suffix = 2
    while section_id in existing:
        section_id = f"section.{base_slug}_{suffix}"
        suffix += 1

    section = {
        "id": section_id,
        "kind": "section",
        "label": title,
        "title": title,
        "children": [],
        "metadata": {"slug": base_slug},
    }
    document["sections"].append(section)
    return section


def make_text_unit(
    unit_id: str,
    kind: str,
    label: str,
    text: str,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "id": unit_id,
        "kind": kind,
        "label": label,
        "text": normalize_text(text),
        "metadata": metadata or {},
    }


def parse_resume_html(document_id: str, html_content: str) -> dict[str, Any]:
    """Parse generated resume HTML into stable, addressable units."""
    soup = BeautifulSoup(html_content or "", "html.parser")
    body = soup.body or soup
    created_at = utc_now()
    document: dict[str, Any] = {
        "documentId": document_id,
        "revisionId": f"rev_{uuid.uuid4().hex[:12]}",
        "schemaVersion": 1,
        "createdAt": created_at,
        "updatedAt": created_at,
        "sourceHtmlHash": html_hash(html_content),
        "sections": [
            {
                "id": "header",
                "kind": "header",
                "label": "Header",
                "title": "Header",
                "children": [],
                "metadata": {},
            }
        ],
    }

    current_section = document["sections"][0]
    current_role: dict[str, Any] | None = None
    role_counts: dict[str, int] = {}
    child_counts: dict[str, dict[str, int]] = {}
    saw_h1 = False
    saw_section = False

    def next_index(parent_id: str, kind: str) -> int:
        counters = child_counts.setdefault(parent_id, {})
        index = counters.get(kind, 0)
        counters[kind] = index + 1
        return index

    def add_to_parent(parent: dict[str, Any], unit: dict[str, Any]) -> None:
        parent.setdefault("children", []).append(unit)

    def add_paragraph(text: str) -> None:
        nonlocal current_role
        if not text:
            return
        if current_role is not None and not any(
            child.get("kind") == "role_meta" for child in current_role.get("children", [])
        ):
            unit = make_text_unit(f"{current_role['id']}.meta", "role_meta", "Role details", text)
            add_to_parent(current_role, unit)
            return

        kind = "skill" if slugify(current_section.get("title", "")) == "skills" else "paragraph"
        index = next_index(current_section["id"], kind)
        unit_id = f"{current_section['id']}.{kind}.{index}"
        add_to_parent(current_section, make_text_unit(unit_id, kind, current_section["title"], text))
        current_role = None

    def add_list(node: Any) -> None:
        nonlocal current_role
        for item in node.find_all("li", recursive=False):
            text = node_text(item)
            if not text:
                continue
            if current_role is not None:
                index = next_index(current_role["id"], "bullet")
                unit_id = f"{current_role['id']}.bullet.{index}"
                add_to_parent(current_role, make_text_unit(unit_id, "bullet", f"Bullet {index + 1}", text))
            else:
                section_slug = slugify(current_section.get("title", ""))
                kind = "skill" if section_slug == "skills" else "item"
                index = next_index(current_section["id"], kind)
                unit_id = f"{current_section['id']}.{kind}.{index}"
                add_to_parent(
                    current_section,
                    make_text_unit(unit_id, kind, f"{current_section['title']} item {index + 1}", text),
                )

    for node in body.children:
        name = getattr(node, "name", None)
        if not name:
            continue
        text = node_text(node)
        if not text:
            continue

        if name == "h1":
            saw_h1 = True
            current_role = None
            add_to_parent(document["sections"][0], make_text_unit("header.name", "header_name", "Name", text))
        elif name == "h2":
            saw_section = True
            current_section = ensure_section(document, text)
            current_role = None
        elif name == "h3":
            if not saw_section:
                current_section = ensure_section(document, "Experience")
                saw_section = True
            index = role_counts.get(current_section["id"], 0)
            role_counts[current_section["id"]] = index + 1
            role_id = f"{current_section['id']}.role.{index}"
            current_role = {
                "id": role_id,
                "kind": "role",
                "label": text,
                "title": text,
                "text": "",
                "children": [],
                "metadata": {"index": index},
            }
            add_to_parent(current_section, current_role)
        elif name == "p":
            if saw_h1 and not saw_section and not any(
                child.get("kind") == "contact" for child in document["sections"][0]["children"]
            ):
                add_to_parent(document["sections"][0], make_text_unit("header.contact", "contact", "Contact", text))
            else:
                add_paragraph(text)
        elif name in {"ul", "ol"}:
            add_list(node)
        elif name in {"div", "section", "article"}:
            nested = parse_resume_html(f"{document_id}.nested", str(node))
            for section in nested["sections"]:
                if section["id"] == "header":
                    for child in section.get("children", []):
                        if child["id"] not in {unit["id"] for unit in document["sections"][0]["children"]}:
                            add_to_parent(document["sections"][0], child)
                else:
                    document["sections"].append(section)

    return document


def iter_units(document: dict[str, Any]) -> Iterable[dict[str, Any]]:
    for section in document.get("sections", []):
        yield section
        for child in section.get("children", []):
            yield child
            for grandchild in child.get("children", []):
                yield grandchild


def find_unit(document: dict[str, Any], unit_id: str) -> dict[str, Any] | None:
    return next((unit for unit in iter_units(document) if unit.get("id") == unit_id), None)


def text_units(document: dict[str, Any]) -> list[dict[str, Any]]:
    return [unit for unit in iter_units(document) if unit.get("kind") in TEXT_UNIT_KINDS]


def unit_text(unit: dict[str, Any]) -> str:
    if unit.get("kind") in TEXT_UNIT_KINDS:
        return unit.get("text", "")
    return " ".join(unit_text(child) for child in unit.get("children", []))


def parent_lookup(document: dict[str, Any]) -> dict[str, str]:
    parents: dict[str, str] = {}
    for section in document.get("sections", []):
        for child in section.get("children", []):
            parents[child["id"]] = section["id"]
            for grandchild in child.get("children", []):
                parents[grandchild["id"]] = child["id"]
    return parents


def unit_label(document: dict[str, Any], unit_id: str) -> str:
    parents = parent_lookup(document)
    units = {unit["id"]: unit for unit in iter_units(document)}
    labels: list[str] = []
    current_id: str | None = unit_id
    while current_id:
        unit = units.get(current_id)
        if unit:
            label = unit.get("title") or unit.get("label") or unit.get("id")
            if unit.get("kind") == "bullet":
                label = unit.get("label") or label
            labels.append(label)
        current_id = parents.get(current_id)
    return " > ".join(reversed(labels))


def build_resume_map(document: dict[str, Any]) -> dict[str, Any]:
    parents = parent_lookup(document)
    map_units = []
    for unit in iter_units(document):
        text = unit_text(unit)
        map_units.append(
            {
                "id": unit["id"],
                "kind": unit["kind"],
                "label": unit.get("title") or unit.get("label") or unit["id"],
                "pathLabel": unit_label(document, unit["id"]),
                "parentId": parents.get(unit["id"]),
                "wordCount": word_count(text),
                "textPreview": text_preview(text),
                "childIds": [child["id"] for child in unit.get("children", [])],
                "metadata": unit.get("metadata", {}),
            }
        )
    return {
        "documentId": document["documentId"],
        "revisionId": document["revisionId"],
        "units": map_units,
    }


def render_markdown(document: dict[str, Any]) -> str:
    lines: list[str] = []
    header = next((section for section in document.get("sections", []) if section["id"] == "header"), None)
    if header:
        for child in header.get("children", []):
            if child["id"] == "header.name":
                lines.append(f"# {child.get('text', '')}")
            elif child["id"] == "header.contact":
                lines.append(child.get("text", ""))
        if lines:
            lines.append("")

    for section in document.get("sections", []):
        if section["id"] == "header":
            continue
        lines.append(f"## {section.get('title', section.get('label', 'Section'))}")
        lines.append("")
        for child in section.get("children", []):
            if child.get("kind") == "role":
                lines.append(f"### {child.get('title') or child.get('label')}")
                for role_child in child.get("children", []):
                    if role_child.get("kind") == "role_meta":
                        lines.append(role_child.get("text", ""))
                    elif role_child.get("kind") == "bullet":
                        lines.append(f"- {role_child.get('text', '')}")
                lines.append("")
            elif child.get("kind") in {"paragraph", "skill"}:
                lines.append(child.get("text", ""))
                lines.append("")
            elif child.get("kind") == "item":
                lines.append(f"- {child.get('text', '')}")
        if lines and lines[-1]:
            lines.append("")

    return "\n".join(lines).strip() + "\n"


def render_html(document: dict[str, Any]) -> str:
    parts: list[str] = []
    header = next((section for section in document.get("sections", []) if section["id"] == "header"), None)
    if header:
        for child in header.get("children", []):
            text = html.escape(child.get("text", ""))
            if child["id"] == "header.name":
                parts.append(f"<h1>{text}</h1>")
            elif child["id"] == "header.contact":
                parts.append(f"<p>{text}</p>")

    for section in document.get("sections", []):
        if section["id"] == "header":
            continue
        parts.append(f"<h2>{html.escape(section.get('title', section.get('label', 'Section')))}</h2>")
        pending_items: list[str] = []

        def flush_items() -> None:
            if not pending_items:
                return
            parts.append("<ul>")
            for item_text in pending_items:
                parts.append(f"<li>{html.escape(item_text)}</li>")
            parts.append("</ul>")
            pending_items.clear()

        for child in section.get("children", []):
            if child.get("kind") == "role":
                flush_items()
                parts.append(f"<h3>{html.escape(child.get('title') or child.get('label') or '')}</h3>")
                bullets: list[str] = []
                for role_child in child.get("children", []):
                    if role_child.get("kind") == "role_meta":
                        if bullets:
                            parts.append("<ul>")
                            for bullet in bullets:
                                parts.append(f"<li>{html.escape(bullet)}</li>")
                            parts.append("</ul>")
                            bullets.clear()
                        parts.append(f"<p>{html.escape(role_child.get('text', ''))}</p>")
                    elif role_child.get("kind") == "bullet":
                        bullets.append(role_child.get("text", ""))
                if bullets:
                    parts.append("<ul>")
                    for bullet in bullets:
                        parts.append(f"<li>{html.escape(bullet)}</li>")
                    parts.append("</ul>")
            elif child.get("kind") == "item":
                pending_items.append(child.get("text", ""))
            else:
                flush_items()
                parts.append(f"<p>{html.escape(child.get('text', ''))}</p>")
        flush_items()

    return "\n".join(parts)


def parse_patch(patch: str) -> PatchParts:
    patch_pattern = (
        r"targetUnitId:\s*(?P<target>\S+)\s*<<<<<<< SEARCH\s*\n"
        r"(?P<search>.*?)\n=======\s*\n(?P<replace>.*?)\n>>>>>>> REPLACE\s*$"
    )
    match = re.search(
        patch_pattern,
        patch or "",
        re.DOTALL,
    )
    if not match:
        raise PatchMismatchError("Patch does not match SEARCH/REPLACE format", "", "")
    return PatchParts(
        target_unit_id=match.group("target").strip(),
        search=match.group("search").strip(),
        replace=match.group("replace").strip(),
    )


def build_patch(target_unit_id: str, search: str, replace: str) -> str:
    return (
        f"targetUnitId: {target_unit_id}\n"
        "<<<<<<< SEARCH\n"
        f"{normalize_text(search)}\n"
        "=======\n"
        f"{normalize_text(replace)}\n"
        ">>>>>>> REPLACE"
    )


def role_matches_message(role: dict[str, Any], user_message: str) -> bool:
    message = normalize_for_match(user_message)
    role_text = normalize_for_match(f"{role.get('label', '')} {unit_text(role)}")
    role_tokens = {
        token
        for token in re.findall(r"[a-z0-9]{3,}", role_text)
        if token not in STOP_WORDS
    }
    message_tokens = set(re.findall(r"[a-z0-9]{3,}", message))
    return bool(role_tokens & message_tokens)


def parse_requested_bullet_index(user_message: str) -> int | None:
    message = normalize_for_match(user_message)
    for word, index in ORDINALS.items():
        if re.search(rf"\b{re.escape(word)}\s+bullet\b|\bbullet\s+{re.escape(word)}\b", message):
            return index
    digit_match = re.search(r"\bbullet\s+(\d+)\b|\b(\d+)(?:st|nd|rd|th)?\s+bullet\b", message)
    if digit_match:
        number = int(next(group for group in digit_match.groups() if group))
        return max(0, number - 1)
    return None


def parse_role_anchor(user_message: str) -> str | None:
    """Extract an explicit role/company anchor from phrases like 'under Acme Corp'."""
    match = re.search(
        r"\bunder\s+([A-Za-z0-9&.,' -]+?)(?:[.;,\n]|$)",
        user_message or "",
        re.IGNORECASE,
    )
    if not match:
        return None
    anchor = normalize_text(match.group(1))
    anchor = re.sub(r"\b(?:role|company|section|entry)\b$", "", anchor, flags=re.IGNORECASE).strip()
    return anchor or None


def role_matches_anchor(role: dict[str, Any], anchor: str) -> bool:
    role_text = normalize_for_match(f"{role.get('label', '')} {unit_text(role)}")
    anchor_text = normalize_for_match(anchor)
    return bool(anchor_text and anchor_text in role_text)


def _selection_value(editor_selection: Any, *names: str) -> Any:
    if editor_selection is None:
        return None
    if isinstance(editor_selection, dict):
        for name in names:
            if name in editor_selection:
                return editor_selection[name]
        return None
    for name in names:
        if hasattr(editor_selection, name):
            return getattr(editor_selection, name)
    return None


def _ordered_text_unit_spans(document: dict[str, Any]) -> tuple[str, list[dict[str, Any]]]:
    parts: list[str] = []
    spans: list[dict[str, Any]] = []
    offset = 0
    for unit in text_units(document):
        text = unit.get("text", "")
        if not text:
            continue
        if parts:
            parts.append("\n")
            offset += 1
        start = offset
        parts.append(text)
        offset += len(text)
        spans.append({"unit": unit, "start": start, "end": offset})
    return "".join(parts), spans


def resolve_target_from_editor_selection(
    document: dict[str, Any],
    selected_text: str,
    editor_selection: Any,
) -> dict[str, Any] | None:
    """Use selection offsets/context to disambiguate repeated selected text."""
    selected = normalize_text(selected_text)
    if not selected or editor_selection is None:
        return None

    document_text, spans = _ordered_text_unit_spans(document)
    if not document_text or not spans:
        return None

    context_before = normalize_text(
        _selection_value(
            editor_selection,
            "context_before",
            "contextBefore",
            "text_before",
            "textBefore",
        )
        or ""
    )
    context_after = normalize_text(
        _selection_value(
            editor_selection,
            "context_after",
            "contextAfter",
            "text_after",
            "textAfter",
        )
        or ""
    )
    from_pos = _selection_value(editor_selection, "from_pos", "from")
    to_pos = _selection_value(editor_selection, "to_pos", "to")

    candidates: list[tuple[float, dict[str, Any]]] = []
    for span in spans:
        unit = span["unit"]
        current = normalize_text(unit.get("text", ""))
        if not current:
            continue
        selected_norm = normalize_for_match(selected)
        current_norm = normalize_for_match(current)
        if selected_norm == current_norm:
            text_score = 1.0
        elif selected_norm and selected_norm in current_norm:
            text_score = 0.98
        else:
            text_score = SequenceMatcher(None, selected_norm, current_norm).ratio()
        if text_score < 0.78:
            continue

        window_before = normalize_text(document_text[max(0, span["start"] - 500) : span["start"]])
        window_after = normalize_text(document_text[span["end"] : span["end"] + 500])
        context_score = 0.0
        if context_before:
            context_score += SequenceMatcher(
                None,
                normalize_for_match(context_before[-200:]),
                normalize_for_match(window_before[-200:]),
            ).ratio()
        if context_after:
            context_score += SequenceMatcher(
                None,
                normalize_for_match(context_after[:200]),
                normalize_for_match(window_after[:200]),
            ).ratio()

        position_score = 0.0
        if isinstance(from_pos, int) and isinstance(to_pos, int):
            selection_mid = (from_pos + to_pos) / 2
            span_mid = (span["start"] + span["end"]) / 2
            position_score = max(0.0, 1.0 - abs(selection_mid - span_mid) / max(len(document_text), 1))

        score = text_score * 4 + context_score + position_score
        candidates.append((score, unit))

    candidates.sort(key=lambda item: item[0], reverse=True)
    if candidates and (len(candidates) == 1 or candidates[0][0] - candidates[1][0] >= 0.15):
        return candidates[0][1]
    return None


def resolve_target_unit(
    document: dict[str, Any],
    selected_text: str | None = None,
    user_message: str | None = None,
    editor_selection: Any = None,
) -> dict[str, Any]:
    """Resolve selection and feedback to exactly one editable resume unit."""
    selected = normalize_text(selected_text or "")
    message = user_message or ""

    selected_target = resolve_target_from_editor_selection(document, selected, editor_selection)
    if selected_target is not None:
        return selected_target

    requested_bullet = parse_requested_bullet_index(message)
    if requested_bullet is not None:
        anchor = parse_role_anchor(message)
        if anchor:
            anchored_roles = [
                role
                for role in iter_units(document)
                if role.get("kind") == "role" and role_matches_anchor(role, anchor)
            ]
            if len(anchored_roles) == 1:
                bullets = [child for child in anchored_roles[0].get("children", []) if child.get("kind") == "bullet"]
                if requested_bullet < len(bullets):
                    return bullets[requested_bullet]
                raise UnitResolutionError(
                    f"Role has {len(bullets)} bullets; requested bullet {requested_bullet + 1}",
                    [map_unit_for_resolution(document, unit) for unit in bullets],
                )
            if len(anchored_roles) > 1:
                raise UnitResolutionError(
                    f"Multiple roles matched anchor '{anchor}'",
                    [map_unit_for_resolution(document, role) for role in anchored_roles],
                )

        matching_roles = [
            role
            for role in iter_units(document)
            if role.get("kind") == "role" and role_matches_message(role, message)
        ]
        if len(matching_roles) == 1:
            bullets = [child for child in matching_roles[0].get("children", []) if child.get("kind") == "bullet"]
            if requested_bullet < len(bullets):
                return bullets[requested_bullet]
            raise UnitResolutionError(
                f"Role has {len(bullets)} bullets; requested bullet {requested_bullet + 1}",
                [map_unit_for_resolution(document, unit) for unit in bullets],
            )
        if len(matching_roles) > 1:
            raise UnitResolutionError(
                "Multiple roles matched the requested bullet reference",
                [map_unit_for_resolution(document, role) for role in matching_roles],
            )

    units = text_units(document)
    if selected:
        selected_norm = normalize_for_match(selected)
        scored: list[tuple[float, dict[str, Any]]] = []
        for unit in units:
            current = normalize_for_match(unit.get("text", ""))
            if not current:
                continue
            if selected_norm == current:
                score = 1.0
            elif selected_norm and selected_norm in current:
                score = 0.96 + min(len(selected_norm) / max(len(current), 1), 1) * 0.03
            elif current and current in selected_norm:
                score = 0.93
            else:
                score = SequenceMatcher(None, selected_norm, current).ratio()
            if score >= 0.78:
                scored.append((score, unit))
        scored.sort(key=lambda item: item[0], reverse=True)
        if scored:
            if len(scored) == 1 or scored[0][0] - scored[1][0] >= 0.04:
                return scored[0][1]
            raise UnitResolutionError(
                "Selection matched multiple resume units",
                [map_unit_for_resolution(document, unit, score) for score, unit in scored[:5]],
            )

    message_norm = normalize_for_match(message)
    if message_norm:
        scored = []
        for unit in units:
            current = normalize_for_match(f"{unit_label(document, unit['id'])} {unit.get('text', '')}")
            score = SequenceMatcher(None, message_norm, current).ratio()
            if score >= 0.55:
                scored.append((score, unit))
        scored.sort(key=lambda item: item[0], reverse=True)
        if scored and (len(scored) == 1 or scored[0][0] - scored[1][0] >= 0.08):
            return scored[0][1]

    raise UnitResolutionError("Could not resolve request to a single resume unit")


def map_unit_for_resolution(
    document: dict[str, Any],
    unit: dict[str, Any],
    score: float | None = None,
) -> dict[str, Any]:
    return {
        "id": unit["id"],
        "kind": unit["kind"],
        "label": unit_label(document, unit["id"]),
        "textPreview": text_preview(unit_text(unit)),
        "score": score,
    }


def build_edit_plan(
    document: dict[str, Any],
    target_unit: dict[str, Any],
    user_message: str,
    action: str | None = None,
) -> dict[str, Any]:
    goal = user_message.strip() or action or "Improve selected resume text"
    assertions = [
        {
            "id": "scope",
            "description": f"Only `{target_unit['id']}` changes.",
            "status": "pending",
        },
        {
            "id": "meaning",
            "description": "Preserve the factual claim unless the user asks otherwise.",
            "status": "pending",
        },
    ]
    intent_text = f"{goal} {action or ''}".lower()
    if any(token in intent_text for token in ["shorten", "concise", "tighten"]):
        assertions.append({"id": "shorter", "description": "Revised text is shorter.", "status": "pending"})
    if any(token in intent_text for token in ["quantify", "metric", "number"]):
        assertions.append({"id": "quantified", "description": "Revised text contains a metric.", "status": "pending"})
    if any(token in intent_text for token in ["keyword", "ats"]):
        assertions.append(
            {
                "id": "keywords",
                "description": "Revised text includes relevant target keywords.",
                "status": "pending",
            }
        )

    return {
        "id": f"plan_{uuid.uuid4().hex[:10]}",
        "goal": goal,
        "targetUnitId": target_unit["id"],
        "targetLabel": unit_label(document, target_unit["id"]),
        "scope": "single_unit",
        "assertions": assertions,
        "todos": [
            {"id": "resolve", "label": "Resolve target unit", "status": "done"},
            {"id": "propose", "label": "Generate scoped SEARCH/REPLACE patch", "status": "pending"},
            {"id": "verify", "label": "Verify requested intent and scope", "status": "pending"},
            {"id": "apply", "label": "Commit accepted edit", "status": "pending"},
        ],
    }


def verify_revision(
    before_text: str,
    after_text: str,
    user_message: str,
    action: str | None = None,
    keywords: list[str] | None = None,
) -> dict[str, Any]:
    """Run deterministic isolated checks over just the target unit diff."""
    intent = f"{user_message} {action or ''}".lower()
    checks: list[dict[str, Any]] = []
    before = normalize_text(before_text)
    after = normalize_text(after_text)

    def add_check(check_id: str, passed: bool, reason: str) -> None:
        checks.append({"id": check_id, "passed": passed, "reason": reason})

    add_check("changed", bool(after and after != before), "Revised text is non-empty and different.")

    if any(token in intent for token in ["shorten", "concise", "tighten"]):
        add_check("shorter", word_count(after) <= word_count(before), "Revised text is no longer than the original.")

    if any(token in intent for token in ["quantify", "metric", "number"]):
        has_metric = bool(re.search(r"(\d|%|\$|m\+|k\+)", after, re.IGNORECASE))
        add_check("quantified", has_metric, "Revised text contains a numeric or symbolic metric.")

    if any(token in intent for token in ["lead", "leadership", "owned", "managed"]):
        has_leadership = bool(re.search(r"\b(led|lead|owned|managed|directed|mentored|partnered)\b", after, re.I))
        add_check("leadership", has_leadership, "Revised text includes leadership language.")

    if any(token in intent for token in ["keyword", "ats"]):
        lowered_after = after.lower()
        matched_keywords = [kw for kw in (keywords or []) if kw.lower() in lowered_after]
        add_check("keywords", bool(matched_keywords), "Revised text includes at least one target keyword.")

    if any(token in intent for token in ["tone", "professional"]):
        add_check(
            "tone",
            not re.search(r"\b(i|me|my|we|our)\b", after, re.I),
            "Revised text avoids first-person phrasing.",
        )

    evidence = text_preview(after, 180) if after else ""
    passed = bool(evidence) and all(check["passed"] for check in checks)
    return {
        "passed": passed,
        "checks": checks,
        "evidence": evidence,
        "summary": "Verification passed." if passed else "Verification failed.",
    }


def apply_patch_to_document(
    document: dict[str, Any],
    patch: str,
    allow_verification_override: bool = False,
    verification: dict[str, Any] | None = None,
) -> dict[str, Any]:
    parts = parse_patch(patch)
    target = find_unit(document, parts.target_unit_id)
    if not target:
        raise PatchMismatchError("Target unit does not exist", "", parts.target_unit_id)
    if target.get("kind") not in TEXT_UNIT_KINDS:
        raise PatchMismatchError("Target unit is not directly editable", unit_text(target), parts.target_unit_id)

    if verification and not verification.get("passed") and not allow_verification_override:
        raise PatchMismatchError("Verification failed; override is required", unit_text(target), parts.target_unit_id)

    current = target.get("text", "")
    if current == parts.search:
        target["text"] = parts.replace
    elif normalize_for_match(current) == normalize_for_match(parts.search):
        target["text"] = parts.replace
    else:
        ratio = SequenceMatcher(None, normalize_for_match(parts.search), normalize_for_match(current)).ratio()
        if ratio >= 0.92:
            target["text"] = parts.replace
        else:
            raise PatchMismatchError(
                f"SEARCH text did not match target unit; normalized similarity was {ratio:.2f}",
                current,
                parts.target_unit_id,
            )

    document["revisionId"] = f"rev_{uuid.uuid4().hex[:12]}"
    document["updatedAt"] = utc_now()
    return document


def changed_text_units(before: dict[str, Any], after: dict[str, Any]) -> list[str]:
    before_units = {unit["id"]: unit.get("text", "") for unit in text_units(before)}
    after_units = {unit["id"]: unit.get("text", "") for unit in text_units(after)}
    changed = []
    for unit_id in sorted(set(before_units) | set(after_units)):
        if before_units.get(unit_id) != after_units.get(unit_id):
            changed.append(unit_id)
    return changed


class ResumeWorkspaceService:
    """File and git-backed workspace manager for structured resume documents."""

    def __init__(self, base_dir: Path | None = None):
        default_base = Path(
            os.getenv(
                "RESUME_WORKSPACE_DIR",
                str(Path(tempfile.gettempdir()) / "talent_promo_resume_workspaces"),
            )
        )
        self.base_dir = base_dir or default_base
        self.retention_seconds = int(os.getenv("RESUME_WORKSPACE_TTL_SECONDS", "86400"))
        self.cleanup_expired_workspaces()

    def workspace_dir(self, document_id: str) -> Path:
        safe_id = re.sub(r"[^A-Za-z0-9_.-]+", "_", document_id).strip("._") or "resume"
        return self.base_dir / safe_id

    def cleanup_expired_workspaces(self) -> None:
        """Remove stale temp workspaces so resume PII does not linger indefinitely."""
        if self.retention_seconds <= 0 or not self.base_dir.exists():
            return
        cutoff = datetime.now(UTC).timestamp() - self.retention_seconds
        for child in self.base_dir.iterdir():
            try:
                if child.is_dir() and child.stat().st_mtime < cutoff:
                    shutil.rmtree(child, ignore_errors=True)
            except OSError:
                logger.debug("Could not inspect resume workspace %s during cleanup", child)

    def refresh_document_from_html(self, document_id: str, html_content: str, progress: str) -> dict[str, Any]:
        workspace = self.workspace_dir(document_id)
        workspace.mkdir(parents=True, exist_ok=True)
        self.ensure_git_repo(document_id)

        document = parse_resume_html(document_id, html_content)
        self.write_workspace_files(document_id, document, progress)
        self.commit(document_id, "Refresh resume workspace from synced editor HTML")
        return self.load_document(document_id)

    def ensure_document(self, document_id: str, html_content: str | None = None) -> dict[str, Any]:
        workspace = self.workspace_dir(document_id)
        doc_path = workspace / "resume.json"
        if doc_path.exists():
            document = self.load_document(document_id)
            if html_content:
                incoming_hash = html_hash(html_content)
                if document.get("sourceHtmlHash") != incoming_hash:
                    rendered_hash = html_hash(render_html(document))
                    if rendered_hash == incoming_hash:
                        document["sourceHtmlHash"] = incoming_hash
                        self.write_workspace_files(document_id, document)
                        self.commit(document_id, "Update resume workspace source hash")
                        return self.load_document(document_id)
                    return self.refresh_document_from_html(
                        document_id,
                        html_content,
                        "Refreshed structured resume workspace from synced editor HTML.",
                    )
            return document
        if not html_content:
            raise ResumeWorkspaceError("No resume HTML is available to initialize the document")

        return self.refresh_document_from_html(
            document_id,
            html_content,
            "Initialized structured resume workspace.",
        )

    def load_document(self, document_id: str) -> dict[str, Any]:
        path = self.workspace_dir(document_id) / "resume.json"
        if not path.exists():
            raise ResumeWorkspaceError("Resume document has not been initialized")
        return json.loads(path.read_text(encoding="utf-8"))

    def write_workspace_files(self, document_id: str, document: dict[str, Any], progress: str | None = None) -> None:
        workspace = self.workspace_dir(document_id)
        workspace.mkdir(parents=True, exist_ok=True)
        (workspace / ".gitignore").write_text("pending/\n", encoding="utf-8")
        (workspace / "resume.json").write_text(
            json.dumps(document, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        (workspace / "resume.md").write_text(render_markdown(document), encoding="utf-8")
        if progress is not None:
            (workspace / "progress.md").write_text(progress.strip() + "\n", encoding="utf-8")

    def ensure_git_repo(self, document_id: str) -> None:
        workspace = self.workspace_dir(document_id)
        if not shutil.which("git"):
            raise ResumeWorkspaceError("git is required for resume versioning")
        if not (workspace / ".git").exists():
            self.run_git(document_id, ["init"])
            self.run_git(document_id, ["config", "user.email", "resume-editor@example.local"])
            self.run_git(document_id, ["config", "user.name", "Resume Editor"])

    def run_git(self, document_id: str, args: list[str], check: bool = True) -> subprocess.CompletedProcess[str]:
        workspace = self.workspace_dir(document_id)
        return subprocess.run(
            ["git", *args],
            cwd=workspace,
            check=check,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

    def commit(self, document_id: str, message: str) -> dict[str, Any] | None:
        self.ensure_git_repo(document_id)
        self.run_git(document_id, ["add", ".gitignore", "resume.json", "resume.md", "progress.md"])
        staged = self.run_git(document_id, ["diff", "--cached", "--quiet"], check=False)
        if staged.returncode == 0:
            return None
        self.run_git(document_id, ["commit", "-m", message])
        commit_sha = self.run_git(document_id, ["rev-parse", "HEAD"]).stdout.strip()
        return {"sha": commit_sha, "message": message}

    def save_pending_revision(self, document_id: str, revision: dict[str, Any]) -> None:
        pending_dir = self.workspace_dir(document_id) / "pending"
        pending_dir.mkdir(parents=True, exist_ok=True)
        path = pending_dir / f"{revision['revisionId']}.json"
        path.write_text(json.dumps(revision, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    def load_pending_revision(self, document_id: str, revision_id: str) -> dict[str, Any]:
        path = self.workspace_dir(document_id) / "pending" / f"{revision_id}.json"
        if not path.exists():
            raise ResumeWorkspaceError("Revision proposal was not found")
        return json.loads(path.read_text(encoding="utf-8"))

    def write_progress_for_revision(self, document_id: str, revision: dict[str, Any], status: str) -> None:
        plan = revision.get("editPlan", {})
        verification = revision.get("verification", {})
        lines = [
            f"# Resume Edit Progress: {status}",
            "",
            f"- Revision: `{revision.get('revisionId')}`",
            f"- Goal: {plan.get('goal', '')}",
            f"- Target: {plan.get('targetLabel', plan.get('targetUnitId', ''))}",
            f"- Verification: {verification.get('summary', 'not run')}",
            "",
            "## Todos",
        ]
        for todo in plan.get("todos", []):
            marker = "x" if todo.get("status") == "done" else " "
            if todo.get("id") == "apply" and status == "applied":
                marker = "x"
            lines.append(f"- [{marker}] {todo.get('label')}")
        lines.append("")
        lines.append("## Evidence")
        lines.append(verification.get("evidence", ""))
        (self.workspace_dir(document_id) / "progress.md").write_text("\n".join(lines).strip() + "\n", encoding="utf-8")

    def apply_pending_revision(
        self,
        document_id: str,
        revision_id: str,
        allow_verification_override: bool = False,
    ) -> dict[str, Any]:
        document_before = self.load_document(document_id)
        revision = self.load_pending_revision(document_id, revision_id)
        before_snapshot = json.loads(json.dumps(document_before))
        document_after = apply_patch_to_document(
            document_before,
            revision["patch"],
            allow_verification_override=allow_verification_override,
            verification=revision.get("verification"),
        )
        changed = changed_text_units(before_snapshot, document_after)
        target_unit_id = revision["targetUnit"]["id"]
        if changed != [target_unit_id]:
            raise PatchMismatchError(
                "Patch changed units outside the resolved target",
                unit_text(find_unit(before_snapshot, target_unit_id) or {}),
                target_unit_id,
            )

        rendered_html = render_html(document_after)
        document_after["sourceHtmlHash"] = html_hash(rendered_html)
        self.write_workspace_files(document_id, document_after)
        self.write_progress_for_revision(document_id, revision, "applied")
        commit_meta = self.commit(document_id, f"Apply resume edit to {target_unit_id}")
        return {
            "document": document_after,
            "resumeHtml": rendered_html,
            "resumeMarkdown": render_markdown(document_after),
            "commit": commit_meta,
            "changedUnitIds": changed,
        }

    def diff(self, document_id: str) -> dict[str, Any]:
        self.ensure_git_repo(document_id)
        log = self.run_git(document_id, ["log", "--format=%H", "--max-count=2"], check=False).stdout.splitlines()
        if len(log) < 2:
            return {"diff": "", "commit": log[0] if log else None}
        patch = self.run_git(document_id, ["show", "--stat", "--patch", "--no-ext-diff", "HEAD"]).stdout
        return {"diff": patch, "commit": log[0]}

    def undo(self, document_id: str) -> dict[str, Any]:
        self.ensure_git_repo(document_id)
        log = self.run_git(document_id, ["log", "--format=%H", "--max-count=2"], check=False).stdout.splitlines()
        if len(log) < 2:
            raise ResumeWorkspaceError("No accepted edit is available to undo")
        self.run_git(document_id, ["revert", "--no-edit", "HEAD"])
        document = self.load_document(document_id)
        rendered_html = render_html(document)
        commit_sha = self.run_git(document_id, ["rev-parse", "HEAD"]).stdout.strip()
        return {
            "document": document,
            "resumeHtml": rendered_html,
            "resumeMarkdown": render_markdown(document),
            "commit": {"sha": commit_sha, "message": "Revert latest resume edit"},
        }
