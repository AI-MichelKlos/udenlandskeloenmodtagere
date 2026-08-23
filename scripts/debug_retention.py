#!/usr/bin/env python3
import json
import sys
import jobindsats_api as api


def main():
    spec = api.get('table/y24j', {'format': 'json'})
    summaries = []
    for h in api.hierarchies(spec):
        summaries.append({
            'hierarchy_id': h.get('hierarchy_id'),
            'blob': api.blob(h)[:1200],
        })
    print('Y24J HIERARCHIES', json.dumps(summaries, ensure_ascii=False))
    sys.exit(1)


if __name__ == '__main__':
    main()
