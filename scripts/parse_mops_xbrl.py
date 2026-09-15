#!/usr/bin/env python3
"""Extract deterministic, provenance-preserving facts from a MOPS iXBRL file.

The Arelle dependency is intentionally imported lazily.  The repository's
existing Python 3.9 environment remains usable; Phase 2 runs in the pinned
Python >=3.10 parser environment documented in ``requirements-xbrl.txt``.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from dataclasses import asdict, dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Iterable


DECIMAL_RE = re.compile(r"^-?\d+(?:\.\d+)?$")


@dataclass(frozen=True)
class NormalizedFact:
    concept_qname: str
    namespace: str
    local_name: str
    label_zh_tw: str | None
    label_en: str | None
    label_source: str
    raw_value: str
    normalized_value: str
    raw_unit: str | None
    normalized_unit: str | None
    raw_decimals: str | None
    context_ref: str
    entity_scheme: str | None
    entity_identifier: str | None
    period_start: str | None
    period_end: str | None
    period_instant: str | None
    dimensions: tuple[tuple[str, str], ...]


def decimal_string(value: Decimal) -> str:
    """Use a stable non-exponent representation for JSON and comparisons."""
    text = format(value, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text or "0"


def normalize_decimal(raw_value: str, raw_decimals: str | None) -> Decimal:
    """Apply the project's explicit negative-decimals presentation policy.

    The source value and decimals are retained separately.  For a finite
    ``decimals=-3``, the normalized value is scaled by 10**3; ``INF`` and a
    missing decimals attribute preserve the numeric value without scaling.
    """
    value = Decimal(raw_value)
    if raw_decimals is None or raw_decimals.upper() == "INF":
        return value
    try:
        decimals = int(raw_decimals)
    except ValueError:
        return value
    return value * (Decimal(10) ** (-decimals))


def qualified_name(namespace: str | None, local_name: str | None) -> tuple[str, str, str]:
    namespace = namespace or ""
    local_name = local_name or ""
    return f"{{{namespace}}}{local_name}", namespace, local_name


def _iso(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return str(value)


def _qname_text(value: Any) -> str:
    namespace = getattr(value, "namespaceURI", None) or ""
    local = getattr(value, "localName", None) or str(value).split(":")[-1]
    return f"{{{namespace}}}{local}" if namespace else local


def _unit_signature(unit: Any) -> str:
    def side(measures: Iterable[Any]) -> str:
        return "*".join(sorted(_qname_text(item) for item in measures)) or "1"

    numerator, denominator = unit.measures
    return side(numerator) if not denominator else f"{side(numerator)}/{side(denominator)}"


def _dimensions(context: Any) -> tuple[tuple[str, str], ...]:
    result: list[tuple[str, str]] = []
    for axis, dim in getattr(context, "qnameDims", {}).items():
        member = getattr(dim, "memberQname", None)
        result.append((_qname_text(axis), _qname_text(member) if member else "typed"))
    return tuple(sorted(result))


def _labels(fact: Any, local_name: str) -> tuple[str | None, str | None, str]:
    concept = getattr(fact, "concept", None)
    if concept is not None:
        zh = concept.label(lang="zh-TW", role="http://www.xbrl.org/2003/role/label")
        en = concept.label(lang="en", role="http://www.xbrl.org/2003/role/label")
        if zh or en:
            return zh, en or local_name, "taxonomy_linkbase"
    return None, local_name, "qualified_name_local_fallback"


def extract_facts(model: Any) -> list[NormalizedFact]:
    """Extract numeric facts while tolerating missing taxonomy linkbases."""
    contexts = model.contexts
    units = model.units
    facts: list[NormalizedFact] = []
    for fact in model.facts:
        value = getattr(fact, "value", None)
        # With a missing taxonomy XSD, Arelle cannot populate ``concept`` and
        # therefore may report ``isNumeric=False`` even for numeric iXBRL
        # facts.  unitID plus a decimal lexical value is the conservative
        # fallback; tuples/text facts remain excluded.
        if value is None or (not getattr(fact, "isNumeric", False) and not getattr(fact, "unitID", None)):
            continue
        raw_value = str(value).strip()
        if not DECIMAL_RE.match(raw_value):
            continue
        qname = getattr(fact, "qname", None)
        concept_qname, namespace, local_name = qualified_name(
            getattr(qname, "namespaceURI", None), getattr(qname, "localName", None)
        )
        try:
            normalized = normalize_decimal(raw_value, getattr(fact, "decimals", None))
        except (InvalidOperation, ValueError):
            continue
        context = contexts.get(fact.contextID)
        if context is None:
            continue
        unit_id = getattr(fact, "unitID", None)
        unit = units.get(unit_id) if unit_id else None
        raw_unit = _unit_signature(unit) if unit is not None else None
        entity_scheme, entity_identifier = (None, None)
        entity = getattr(context, "entityIdentifier", None)
        if entity:
            entity_scheme, entity_identifier = str(entity[0]), str(entity[1])
        label_zh_tw, label_en, label_source = _labels(fact, local_name)
        facts.append(
            NormalizedFact(
                concept_qname=concept_qname,
                namespace=namespace,
                local_name=local_name,
                label_zh_tw=label_zh_tw,
                label_en=label_en,
                label_source=label_source,
                raw_value=raw_value,
                normalized_value=decimal_string(normalized),
                raw_unit=raw_unit,
                normalized_unit=raw_unit,
                raw_decimals=(str(fact.decimals) if fact.decimals is not None else None),
                context_ref=str(fact.contextID),
                entity_scheme=entity_scheme,
                entity_identifier=entity_identifier,
                period_start=_iso(getattr(context, "startDatetime", None)),
                period_end=_iso(getattr(context, "endDatetime", None)),
                period_instant=_iso(getattr(context, "instantDatetime", None)),
                dimensions=_dimensions(context),
            )
        )
    return sorted(
        facts,
        key=lambda item: (
            item.concept_qname,
            item.context_ref,
            item.raw_unit or "",
            item.raw_decimals or "",
            item.raw_value,
        ),
    )


def parse(path: Path) -> tuple[dict[str, Any], list[NormalizedFact]]:
    try:
        from arelle import Cntlr, Version
    except ImportError as exc:  # pragma: no cover - exercised in CLI env
        raise RuntimeError("install requirements-xbrl.txt in Python >=3.10") from exc

    diagnostic_log = Path("/tmp/mops-xbrl-arelle.log")
    controller = Cntlr.Cntlr(logFileName=str(diagnostic_log))
    model = controller.modelManager.load(str(path))
    if model is None:
        raise RuntimeError("Arelle could not load the supplied instance")
    facts = extract_facts(model)
    metadata = {
        "input_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "input_filename": path.name,
        "parser": "arelle-release",
        "parser_version": Version.version,
        "facts_total": len(tuple(model.facts)),
        "numeric_facts": len(facts),
        "contexts": len(model.contexts),
        "units": len(model.units),
        "diagnostic_count": len(getattr(model, "errors", ())),
        "labels": {
            "zh-TW": "unavailable_without_taxonomy_linkbase",
            "english": "local-name fallback",
        },
    }
    return metadata, facts


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    metadata, facts = parse(args.input)
    payload = {"metadata": metadata, "facts": [asdict(item) for item in facts]}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(metadata, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
