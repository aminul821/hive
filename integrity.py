"""
integrity.py
------------
The Harvest Integrity Engine, server-side.

Previously these checks ran in the browser, which meant the operator being
audited controlled the auditor. Anyone could open devtools, edit
`harvestRecords`, and produce a clean history. Moving the rules here makes
the verdict something the operator cannot author.

Input shape matches what static/js/app.js already builds:

    {
      "hives":     [{"hive": "H001", "before": 48.2, "after": 40.1}, ...],
      "extracted": 7.9,      # honey actually extracted
      "recorded":  8.0,      # weight the operator wrote down
      "moisture":  17.5
    }

The physical argument: honey removed from a hive must equal the hive's
weight drop, and the weight written down must equal what was extracted.
Where those disagree beyond sensor tolerance, something is wrong --
either the record or the honey.

Pure Python, no Flask or SQLAlchemy imports, so it is unit-testable on its
own.
"""

from __future__ import annotations

# Hive scales are accurate to roughly 100g; allow a little more for
# handling losses (comb fragments, spillage, residue in the extractor).
ABS_TOLERANCE_KG = 0.5
REL_TOLERANCE = 0.05          # 5%

# Honey left behind in the extractor and lines. Extracting materially
# LESS than the hive lost is normal up to a point; well beyond it,
# honey went somewhere unrecorded.
MAX_EXTRACTION_SHORTFALL = 0.25   # 25%

MAX_SAFE_MOISTURE = 20.0      # above this, honey ferments

MATCH = "MATCH"          # frontend styles on this exact string
MISMATCH = "MISMATCH"


def _num(value, fallback=0.0) -> float:
    try:
        if value is None:
            return fallback
        return float(value)
    except (TypeError, ValueError):
        return fallback


def total_drop(hives) -> float:
    """Sum of (pre-harvest - post-harvest) across every hive in the event."""
    total = 0.0
    for entry in (hives or []):
        if not isinstance(entry, dict):
            continue
        total += _num(entry.get("before")) - _num(entry.get("after"))
    return round(total, 3)


def evaluate(payload: dict) -> tuple[str, list[str], dict]:
    """
    Run every rule.

    Returns (status, reasons, evidence). Never raises -- a rules engine
    that crashes on a malformed record is a rules engine that gets
    wrapped in a try/except and ignored.
    """
    reasons: list[str] = []
    hives = payload.get("hives") or []

    drop = _num(payload.get("drop")) or total_drop(hives)
    extracted = _num(payload.get("extracted"))
    recorded = _num(payload.get("recorded"))
    moisture = payload.get("moisture")

    evidence = {
        "drop_kg": round(drop, 3),
        "extracted_kg": round(extracted, 3),
        "recorded_kg": round(recorded, 3),
        "hive_count": len(hives),
    }

    # -- per-hive sanity ------------------------------------------------
    for entry in hives:
        if not isinstance(entry, dict):
            continue
        name = entry.get("hive", "?")
        before, after = _num(entry.get("before")), _num(entry.get("after"))
        if after > before + 0.01:
            reasons.append(
                f"{name}: hive gained weight during extraction "
                f"({before:.1f} kg to {after:.1f} kg), which is not possible"
            )

    if drop <= 0 and (extracted > 0 or recorded > 0):
        reasons.append(
            "honey was reported but no hive lost any weight"
        )

    # -- recorded vs extracted -----------------------------------------
    # The operator's number against what actually came out.
    tolerance = max(ABS_TOLERANCE_KG, extracted * REL_TOLERANCE)
    delta = recorded - extracted
    evidence["recorded_vs_extracted_kg"] = round(delta, 3)
    evidence["tolerance_kg"] = round(tolerance, 3)

    if abs(delta) > tolerance:
        if delta > 0:
            reasons.append(
                f"{delta:.2f} kg more honey was recorded than extracted "
                f"-- unaccounted honey entering the batch"
            )
        else:
            reasons.append(
                f"{abs(delta):.2f} kg less honey was recorded than extracted "
                f"-- possible diversion before weighing"
            )

    # -- extracted vs hive weight drop ----------------------------------
    # The strongest check available: the comparison number comes from the
    # hive scale, not from the person filing the record.
    if drop > 0:
        surplus = extracted - drop
        evidence["extracted_vs_drop_kg"] = round(surplus, 3)

        if surplus > max(ABS_TOLERANCE_KG, drop * REL_TOLERANCE):
            reasons.append(
                f"{surplus:.2f} kg more honey was extracted than the hives "
                f"lost in weight -- honey from an unrecorded source"
            )
        else:
            shortfall = (drop - extracted) / drop
            if shortfall > MAX_EXTRACTION_SHORTFALL:
                reasons.append(
                    f"only {extracted:.2f} kg extracted from a {drop:.2f} kg "
                    f"weight drop ({shortfall * 100:.0f}% unaccounted)"
                )

    # -- moisture --------------------------------------------------------
    if moisture is not None:
        m = _num(moisture)
        evidence["moisture_pct"] = m
        if m > MAX_SAFE_MOISTURE:
            reasons.append(
                f"moisture {m:.1f}% is above the {MAX_SAFE_MOISTURE:.0f}% "
                f"fermentation threshold -- unripe or watered honey"
            )

    status = MISMATCH if reasons else MATCH
    return status, reasons, evidence
