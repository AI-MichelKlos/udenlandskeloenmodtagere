#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

import fetch_sources

BASE = Path(__file__).resolve().parents[1]
DATA = BASE / "data" / "dashboard-data.json"
INDEX = BASE / "index.html"


def robust_retention_bucket(label):
    n = fetch_sources.api.norm(label)
    if ('lonmodtager' in n or 'loenmodtager' in n) and ('beskaeft' in n or 'beskæft' in str(label).lower()):
        return 'employed'
    if 'beskaeftigelse' in n and 'offentlig' not in n and 'ydelse' not in n:
        return 'employed'
    if ('offentlig' in n and 'ydelse' in n) or 'forsorgelse' in n or 'forsoergelse' in n:
        return 'benefitOnly'
    if ('hverken' in n and ('bopael' in n or 'beskaeftigelse' in n)) or 'udvandret' in n or 'ikke bosat' in n:
        return 'outside'
    return None


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
    if len(retention.get("offsets", [])) < 2 or len(retention.get("employedPct", [])) != len(retention.get("offsets", [])):
        raise RuntimeError("Retention-serien er ikke konsistent")


def main():
    fetch_sources.retention_bucket = robust_retention_bucket
    fetch_sources.main()
    validate()
    print("Dashboarddata bestod projektets kvalitetskontrol.")


if __name__ == "__main__":
    main()
