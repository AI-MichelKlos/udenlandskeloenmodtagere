#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
DATA = BASE / "data" / "dashboard-data.json"
INDEX = BASE / "index.html"


def validate():
    if not INDEX.is_file() or INDEX.stat().st_size < 1000:
        raise RuntimeError("index.html mangler eller er uventet lille")
    payload = json.loads(DATA.read_text(encoding="utf-8"))
    meta = payload.get("meta", {})
    status = meta.get("updateStatus", {})
    if status.get("state") != "ok":
        raise RuntimeError(f"Dataopdateringen er ikke ok: {status}")
    sources = meta.get("sourceStatus", {})
    for key in ("foreignWorkers", "totalEmployees"):
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


def main():
    subprocess.run([sys.executable, str(BASE / "scripts" / "fetch_sources.py")], check=True)
    validate()
    print("Dashboarddata bestod projektets kvalitetskontrol.")


if __name__ == "__main__":
    main()
