"""
relations.py — Turn a report's supply-chain prose into typed, directed edges.

The reports already carry direction: 供應鏈位置 groups entities under 上游 /
中游 / 下游, and 主要客戶及供應商 splits them into customers and suppliers.
Until now that lived only in the markdown layout, so the graph could say two
names co-occur but not who sells to whom. This module reads the layout once and
every consumer — network graph, theme pages — works from the same edges instead
of re-guessing from nearby text.

Edge direction is always "source supplies target":

  上游 X      -> supplies(X, subject)      X is an input to the subject
  主要供應商 X -> supplies(X, subject)
  下游 X      -> supplies(subject, X)      the subject feeds X
  主要客戶 X   -> supplies(subject, X)
  競爭對手 X   -> competes(subject, X)     symmetric, stored once
  業務簡介 X   -> mentions(subject, X)     no role stated

中游 is the subject's own position in its chain, so it yields no edge.
"""

import re
from collections import namedtuple

from utils import WIKILINK_RE

Relation = namedtuple("Relation", "source target kind")

SUPPLIES, COMPETES, MENTIONS = "supplies", "competes", "mentions"

# A role marker is a bold run containing 上游/中游/下游 — the parenthetical that
# usually follows (**上游 (設備/原料):**) is free text and deliberately ignored.
_ROLE_RE = re.compile(r"\*\*[^*]*?(上游|中游|下游)[^*]*?\*\*")

_SECTION_RE = re.compile(r"^(#{2,4}) +(.*?) *$", re.M)

# Inbound: the counterpart supplies the subject. Outbound: the subject supplies
# the counterpart. Anything else under 主要客戶及供應商 is left untyped.
_INBOUND_HEADINGS = ("主要供應商",)
_OUTBOUND_HEADINGS = ("主要客戶",)
_COMPETITOR_HEADINGS = ("競爭對手", "競爭者")


def _sections(content):
    """Split a report into {heading: body} for its ## and ### headings."""
    out = {}
    marks = list(_SECTION_RE.finditer(content))
    for i, m in enumerate(marks):
        end = marks[i + 1].start() if i + 1 < len(marks) else len(content)
        out[m.group(2)] = content[m.end():end]
    return out


def _supply_chain_roles(body):
    """Yield (role, entity) for the 供應鏈位置 body.

    A role marker applies to its own line and to every following line until the
    next marker, which is how the reports are actually written — some put the
    entities inline after the marker, others list them as bullets beneath it.
    """
    role = None
    for line in body.split("\n"):
        marker = _ROLE_RE.search(line)
        if marker:
            role = marker.group(1)
            line = line[marker.end():]
        if role:
            for name in WIKILINK_RE.findall(line):
                yield role, name


def extract_relations(content, subject):
    """Return the typed edges a single report states about its own company."""
    sections = _sections(content)
    seen = set()
    relations = []

    def add(source, target, kind):
        if source == target or not source or not target:
            return
        key = (source, target, kind)
        if key not in seen:
            seen.add(key)
            relations.append(Relation(source, target, kind))

    for role, name in _supply_chain_roles(sections.get("供應鏈位置", "")):
        if role == "上游":
            add(name, subject, SUPPLIES)
        elif role == "下游":
            add(subject, name, SUPPLIES)

    for heading, body in sections.items():
        names = WIKILINK_RE.findall(body)
        if any(h in heading for h in _INBOUND_HEADINGS):
            for name in names:
                add(name, subject, SUPPLIES)
        elif any(h in heading for h in _OUTBOUND_HEADINGS):
            for name in names:
                add(subject, name, SUPPLIES)
        elif any(h in heading for h in _COMPETITOR_HEADINGS):
            for name in names:
                add(subject, name, COMPETES)

    # Whatever the report names without stating a role still belongs in the
    # graph, just as a weaker claim than a supply relationship.
    typed = {r.target for r in relations} | {r.source for r in relations}
    for name in WIKILINK_RE.findall(sections.get("業務簡介", "")):
        if name not in typed:
            add(subject, name, MENTIONS)

    return relations
