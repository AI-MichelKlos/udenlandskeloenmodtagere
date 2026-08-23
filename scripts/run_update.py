#!/usr/bin/env python3
from __future__ import annotations

import json
import re
from pathlib import Path

import fetch_sources

BASE = Path(__file__).resolve().parents[1]
DATA = BASE / "data" / "dashboard-data.json"
INDEX = BASE / "index.html"
OFFSETS = (6, 12, 24, 36, 48, 60)


def explicit_retention(rows):
    period_col = fetch_sources.api.best_col(rows, ["periode"])
    status_col = fetch_sources.api.best_col(rows, ["arbejdsmarkedsstatus", "status"], distinct=True)
    cols = fetch_sources.columns(rows)

    pct_cols = {}
    for col in cols:
        norm = fetch_sources.api.norm(col)
        if "andel" not in norm and "pct" not in norm and "procent" not in norm:
            continue
        match = re.search(r"status\s+(6|12|24|36|48|60)\s+md", norm)
        if match:
            pct_cols[int(match.group(1))] = col
    missing = [offset for offset in OFFSETS if offset not in pct_cols]
    if missing:
        raise RuntimeError(f"Retention mangler procentkolonner for: {missing}. Kolonner: {cols}")

    grouped = {}
    for row in rows:
        period = str(row.get(period_col) or "").strip()
        status = fetch_sources.api.norm(row.get(status_col))
        if not period or not status:
            continue
        entry = grouped.setdefault(period, {"employed": {}, "benefitOnly": {}, "outside": {}})
        if status == "alene loenmodtagerbeskaeftigelse":
            bucket = "employed"
        elif status == "alene offentlig ydelse":
            bucket = "benefitOnly"
        elif status.startswith("hverken beskaeft") and "bopael" in status:
            bucket = "outside"
        else:
            continue
        for offset, col in pct_cols.items():
            value = fetch_sources.api.num(row.get(col))
            if value is not None:
                entry[bucket][offset] = float(value)

    periods = sorted(grouped, key=fetch_sources.pkey)
    if not periods:
        raise RuntimeError("Retention gav ingen genkendelige arbejdsmarkedsstatusser.")

    complete = [period for period in periods if all(offset in grouped[period]["employed"] for offset in OFFSETS)]
    if complete:
        cohort = complete[-1]
    else:
        cohort = max(periods, key=lambda period: (len(grouped[period]["employed"]), fetch_sources.pkey(period)))
    if len(grouped[cohort]["employed"]) < 2:
        raise RuntimeError("Retention havde for få brugbare beskæftigelsesandele.")

    def values(bucket):
        return [round(grouped[cohort][bucket][offset], 4) if offset in grouped[cohort][bucket] else None for offset in OFFSETS]

    return {
        "sourceLatestPeriod": periods[-1],
        "cohortPeriod": cohort,
        "offsets": list(OFFSETS),
        "employedPct": values("employed"),
        "benefitOnlyPct": values("benefitOnly"),
        "outsidePct": values("outside"),
    }


def validate():
    if not INDEX.is_file() or INDEX.stat().st_size < 1000:
        raise RuntimeError("index.html mangler eller er uventet lille")
    payload = json.loads(DATA.read_text(encoding="utf-8"))
    meta = payload.get("meta", {})
    status = meta.get("updateStatus", {})
    if status.get("state") != "ok":
        raise RuntimeError(f"Dataopdateringen er ikke ok: {status}")
    sources = meta.get("sourceStatus", {})
    required_sources = ("foreignWorkers", "totalEmployees", "residence", "residencePermits", "regions", "retention")
    for key in required_sources:
        info = sources.get(key, {})
        if info.get("state") != "ok" or not info.get("dataset") or not info.get("latestPeriod"):
            raise RuntimeError(f"Kildestatus er ikke komplet for {key}: {info}")
    sections = payload.get("sections", {})
    foreign = sections.get("foreignTimeSeries", {})
    if not foreign.get("labels") or len(foreign["labels"]) != len(foreign.get("persons", [])):
        raise RuntimeError("Tidsserien for udenlandske lønmodtagere er ikke konsistent")
    if foreign.get("kpi", {}).get("period") != foreign["labels"][-1]:
        raise RuntimeError("KPI-perioden for udenlandske lønmodtagere matcher ikke grafens seneste periode")
    share = sections.get("share", {})
    if share.get("labels") and share.get("kpi", {}).get("period") != share["labels"][-1]:
        raise RuntimeError("KPI-perioden for andelen matcher ikke grafens seneste periode")
    if not sections.get("branches", {}).get("items", []):
        raise RuntimeError("Branchegrafen har ingen data")
    if not sections.get("nationalities", {}).get("items", []):
        raise RuntimeError("Statsborgerskabsgrafen har ingen data")
    residence = sections.get("residence", {})
    if not residence.get("labels") or len(residence.get("series", [])) < 2:
        raise RuntimeError("Bopælsfordelingen mangler data")
    permits = sections.get("residencePermits", {})
    if not permits.get("labels") or not permits.get("series"):
        raise RuntimeError("Opholdsgrundlag mangler data")
    regions = sections.get("regions", {}).get("items", [])
    if len(regions) < 5:
        raise RuntimeError("Regionsfordelingen mangler regioner")
    retention = sections.get("retention", {})
    if retention.get("offsets") != list(OFFSETS) or len(retention.get("employedPct", [])) != len(OFFSETS):
        raise RuntimeError("Retention-serien er ikke konsistent")
    if sum(value is not None for value in retention.get("employedPct", [])) < 2:
        raise RuntimeError("Retention-serien mangler beskæftigelsesandele")


def main():
    fetch_sources.retention = explicit_retention
    fetch_sources.main()
    validate()
    print("Dashboarddata bestod projektets kvalitetskontrol.")


if __name__ == "__main__":
    main()
