#!/usr/bin/env python3
import json
import jobindsats_api as api


def main():
    tables = api.get('tables', {'format': 'json'})
    candidates = []
    seen = set()
    for item in api.walk(tables):
        tid = item.get('table_id')
        if not tid or tid in seen:
            continue
        text = api.blob(item)
        if 'udenland' in text and 'arbejdsmarkedsstatus' in text:
            seen.add(tid)
            candidates.append((str(tid), text[:700]))
    print('RETENTION TABLE CANDIDATES', json.dumps(candidates, ensure_ascii=False))


if __name__ == '__main__':
    main()
