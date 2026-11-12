from __future__ import annotations

import re
from typing import Any


def summarize_facility_text(text: str, source_uri: str | None = None) -> dict[str, Any]:
    """Extract a conservative summary from ExPlanner facility definition text.

    The source files use JSON-like MATLAB expressions, so this intentionally does
    not pretend to be a complete JSON parser.
    """

    return {
        "facility": _string_field(text, "Facility"),
        "instrument": _string_field(text, "Instrument"),
        "instrument_type": _string_field(text, "Type"),
        "last_update": _string_field(text, "LastUpdate"),
        "monochromators": _named_blocks(text, "Monochromator"),
        "analyzers": _named_blocks(text, "Analyzer"),
        "collimators": _named_blocks(text, "GMCollimator"),
        "filters": _named_blocks(text, "UpstreamFilter"),
        "a4_limits": _number_list_after(text, "A4Limits"),
        "source_uri": source_uri,
        "ported_algorithm_status": "facility summary only; accessible-Q/E and resolution planning still require MATLAB fixture parity tests",
    }


def _string_field(text: str, key: str) -> str | None:
    match = re.search(rf'"{re.escape(key)}"\s*:\s*"([^"]+)"', text)
    return match.group(1) if match else None


def _named_blocks(text: str, key: str) -> list[str]:
    start = text.find(f'"{key}"')
    if start < 0:
        return []
    next_top = re.search(r'\n\s*"[A-Za-z0-9_ ]+"\s*:', text[start + len(key) + 2 :])
    end = len(text) if next_top is None else start + len(key) + 2 + next_top.start()
    block = text[start:end]
    return sorted(set(re.findall(r'"Name"\s*:\s*"([^"]+)"', block)))


def _number_list_after(text: str, key: str) -> list[float]:
    start = text.find(f'"{key}"')
    if start < 0:
        return []
    block = text[start : start + 300]
    return [float(value) for value in re.findall(r"[-+]?\d+(?:\.\d+)?", block)]
