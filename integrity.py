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


# ==========================================================================
# Cross-record checks
# ==========================================================================
#
# Everything above examines ONE harvest event. These look across many
# records at once, which is where the harder fraud lives.
#
# A single harvest can be made internally consistent by anyone willing to
# write three numbers that agree. What is much harder to fake is a whole
# season's worth of records that still agree WITH EACH OTHER. The classic
# pattern -- buy cheap wholesale honey, sell it as your own -- produces a
# set of individually flawless harvests whose total is impossible for the
# number of hives on the ground.
#
# This is the same reasoning auditors apply as "mass balance", and it is
# accepted practice in food-fraud work. The difference here is that it
# runs on every record automatically instead of once a year by hand, and
# the corroborating number comes from a hive scale rather than from the
# operator being audited.

# Seasonal ceiling for a single hive.
#
# Set deliberately high. Apis cerana indica, which most Indian beekeepers
# keep, yields roughly 5-15 kg a year. Apis mellifera under migratory
# management, moved between flows, can reach 40-50 kg. A threshold of 40
# would therefore flag the best legitimate beekeepers in the country --
# and an alert system that punishes good operators is one people learn to
# ignore, which is worse than having no alerts at all.
#
# 60 kg is above what any single hive plausibly produces in an Indian
# season, so crossing it means honey came from somewhere else. Tune this
# per species and region before any real deployment; it is a blunt
# instrument by design.
MAX_KG_PER_HIVE_PER_SEASON = 60.0

# Honey cannot be bottled before it is harvested. A small tolerance
# covers rounding and scale drift across many records.
BATCH_TOLERANCE_KG = 1.0


def check_hive_ledger(hive_id: str, harvest_records, batches) -> tuple[str, list[str], dict]:
    """
    Reconcile everything ever harvested from one hive against everything
    ever bottled from it.

    You cannot bottle honey that was never harvested. If the batches
    attributed to a hive outweigh its recorded harvests, the surplus
    entered the supply chain from somewhere unrecorded -- which, for a
    product adulterated at a rate CSE measured at 77%, is the single most
    likely place syrup gets in.

    `harvest_records` are HarvestRecord.to_dict() shapes; `batches` are
    Batch.to_dict() shapes. Both are filtered to this hive by the caller.
    """
    harvested = 0.0
    harvest_count = 0
    for record in (harvest_records or []):
        for entry in (record.get("hives") or []):
            if isinstance(entry, dict) and entry.get("hive") == hive_id:
                # Credit the RECORDED figure, the operator's own claim.
                # Using it here means a beekeeper cannot escape this check
                # by under-reporting: doing so only tightens the ceiling.
                harvested += _num(record.get("recorded"))
                harvest_count += 1
                break          # count each record once, not once per hive row

    bottled = sum(_num(b.get("qty")) for b in (batches or [])
                  if b.get("hive") == hive_id)

    evidence = {
        "hive": hive_id,
        "harvested_kg": round(harvested, 3),
        "bottled_kg": round(bottled, 3),
        "difference_kg": round(bottled - harvested, 3),
        "harvest_count": harvest_count,
        "batch_count": len([b for b in (batches or [])
                            if b.get("hive") == hive_id]),
    }

    reasons = []
    surplus = bottled - harvested
    if surplus > BATCH_TOLERANCE_KG:
        pct = (surplus / bottled * 100) if bottled else 0
        reasons.append(
            f"{surplus:.2f} kg more honey has been batched from {hive_id} "
            f"than was ever harvested from it ({bottled:.2f} kg bottled vs "
            f"{harvested:.2f} kg harvested). {pct:.0f}% of this hive's "
            f"output has no traceable origin."
        )

    return (MISMATCH if reasons else MATCH), reasons, evidence


def check_hive_capacity(hive_id: str, harvest_records,
                        max_per_season: float = MAX_KG_PER_HIVE_PER_SEASON
                        ) -> tuple[str, list[str], dict]:
    """
    Total seasonal output from one hive against what a hive can produce.

    Catches the operator whose individual harvests are each plausible but
    whose annual total is not. Nothing in a single record reveals this;
    only the sum does.
    """
    total = 0.0
    count = 0
    for record in (harvest_records or []):
        for entry in (record.get("hives") or []):
            if isinstance(entry, dict) and entry.get("hive") == hive_id:
                total += _num(record.get("recorded"))
                count += 1

    evidence = {
        "hive": hive_id,
        "season_total_kg": round(total, 3),
        "harvest_count": count,
        "ceiling_kg": max_per_season,
        "excess_kg": round(max(0.0, total - max_per_season), 3),
    }

    reasons = []
    if total > max_per_season:
        reasons.append(
            f"{hive_id} has produced {total:.1f} kg across {count} harvest(s) "
            f"this season. A strong hive tops out near {max_per_season:.0f} kg, "
            f"so {total - max_per_season:.1f} kg is more than this hive could "
            f"have made."
        )

    return (MISMATCH if reasons else MATCH), reasons, evidence


def check_repeat_offender(hive_id: str, harvest_records,
                          threshold: int = 2) -> tuple[str, list[str], dict]:
    """
    Flag hives whose records keep failing.

    One mismatch is a bad day, a mis-keyed number, a faulty scale. A
    pattern is a decision. Separating the two matters: an enforcement
    system that treats every clerical error as fraud gets ignored, and
    one that never escalates gets gamed.
    """
    flagged = [r for r in (harvest_records or [])
               if r.get("status") == MISMATCH
               and any(isinstance(e, dict) and e.get("hive") == hive_id
                       for e in (r.get("hives") or []))]

    total = len([r for r in (harvest_records or [])
                 if any(isinstance(e, dict) and e.get("hive") == hive_id
                        for e in (r.get("hives") or []))])

    evidence = {
        "hive": hive_id,
        "mismatches": len(flagged),
        "total_harvests": total,
        "mismatch_rate": round(len(flagged) / total * 100, 1) if total else 0.0,
    }

    reasons = []
    if len(flagged) >= threshold:
        reasons.append(
            f"{hive_id} has {len(flagged)} flagged harvests out of {total}. "
            f"A repeated pattern, not an isolated recording error -- this "
            f"hive warrants physical inspection."
        )

    return (MISMATCH if reasons else MATCH), reasons, evidence


def audit_all(harvest_records, batches) -> dict:
    """
    Run every cross-record check across every hive that appears in the
    data, and return a ranked report.

    This is the system-wide view: not "was this harvest honest?" but
    "where in this supply chain does the arithmetic fail?"
    """
    hives = set()
    for record in (harvest_records or []):
        for entry in (record.get("hives") or []):
            if isinstance(entry, dict) and entry.get("hive"):
                hives.add(entry["hive"])
    for batch in (batches or []):
        if batch.get("hive"):
            hives.add(batch["hive"])

    findings = []
    for hive_id in sorted(hives):
        for name, check in (
            ("unaccounted_origin", lambda h: check_hive_ledger(h, harvest_records, batches)),
            ("capacity_exceeded", lambda h: check_hive_capacity(h, harvest_records)),
            ("repeat_offender", lambda h: check_repeat_offender(h, harvest_records)),
        ):
            try:
                status, reasons, evidence = check(hive_id)
            except Exception as exc:                     # noqa: BLE001
                findings.append({"hive": hive_id, "check": name,
                                 "status": MISMATCH,
                                 "reasons": [f"check failed: {exc}"],
                                 "evidence": {}})
                continue
            if status == MISMATCH:
                findings.append({"hive": hive_id, "check": name,
                                 "status": status, "reasons": reasons,
                                 "evidence": evidence})

    # Unaccounted origin is the most serious: it means honey with no
    # source entered the chain. Capacity next, then pattern.
    order = {"unaccounted_origin": 0, "capacity_exceeded": 1,
             "repeat_offender": 2}
    findings.sort(key=lambda f: (order.get(f["check"], 9), f["hive"]))

    return {
        "hives_audited": len(hives),
        "hives_flagged": len({f["hive"] for f in findings}),
        "findings": findings,
        "clean": not findings,
    }
