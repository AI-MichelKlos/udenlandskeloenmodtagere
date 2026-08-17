#!/usr/bin/env python3
import argparse
import json
import sys
from pathlib import Path


def load_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise ValueError(f"Missing file: {path}")
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in {path}: {exc}")


def source_codes(meta):
    codes = set()
    status = meta.get("sourceStatus", {})
    if isinstance(status, dict):
        codes.update(str(k) for k in status)
        for value in status.values():
            if isinstance(value, dict) and value.get("dataset"):
                codes.add(str(value["dataset"]))
    official = meta.get("officialApi", {})
    if isinstance(official, dict):
        codes.update(str(k) for k in official)
        for value in official.values():
            if isinstance(value, dict) and value.get("dataset"):
                codes.add(str(value["dataset"]))
    return codes


def validate(repo: Path, required_sources):
    errors = []
    warnings = []
    html = repo / "index.html"
    data_path = repo / "data" / "dashboard-data.json"
    workflow_dir = repo / ".github" / "workflows"
    if not html.is_file() or html.stat().st_size == 0:
        errors.append("index.html is missing or empty")
    try:
        data = load_json(data_path)
    except ValueError as exc:
        errors.append(str(exc))
        data = {}
    workflows = list(workflow_dir.glob("*.yml")) + list(workflow_dir.glob("*.yaml")) if workflow_dir.is_dir() else []
    if not workflows:
        warnings.append("No GitHub Actions workflow found")
    meta = data.get("meta", {}) if isinstance(data, dict) else {}
    if not isinstance(meta, dict):
        errors.append("meta must be an object")
        meta = {}
    update = meta.get("updateStatus")
    if not isinstance(update, dict):
        warnings.append("meta.updateStatus is missing")
    elif update.get("state") == "ok" and update.get("failed", []):
        errors.append("updateStatus is ok but failed list is not empty")
    known_sources = source_codes(meta)
    for code in required_sources:
        if code not in known_sources:
            errors.append(f"Required source not registered: {code}")
    source_status = meta.get("sourceStatus", {})
    if isinstance(source_status, dict):
        for code, info in source_status.items():
            if isinstance(info, dict) and info.get("state") == "ok" and not info.get("latestPeriod"):
                errors.append(f"Source {code} is ok but latestPeriod is missing")
    return errors, warnings


def main():
    parser = argparse.ArgumentParser(description="Validate a DAK dashboard repository")
    parser.add_argument("--repo", default=".")
    parser.add_argument("--require-source", action="append", default=[])
    args = parser.parse_args()
    errors, warnings = validate(Path(args.repo).resolve(), args.require_source)
    for item in warnings:
        print(f"WARNING: {item}")
    for item in errors:
        print(f"ERROR: {item}")
    if errors:
        return 1
    print("OK: dashboard repository passed structural validation")
    return 0


if __name__ == "__main__":
    sys.exit(main())
