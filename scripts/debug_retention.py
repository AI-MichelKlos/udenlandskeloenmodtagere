#!/usr/bin/env python3
import json
import sys
import jobindsats_api as api


def main():
    spec = api.get('table/y24j', {'format': 'json'})
    pop = api.find_hierarchy(spec, ['population'], ('_popbeskudl',))
    values = []
    for item in api.walk(pop):
        value_id = item.get('value_id')
        if isinstance(value_id, str):
            values.append({'value_id': value_id, 'blob': api.blob(item)[:500]})
    print('Y24J POP VALUES', json.dumps(values, ensure_ascii=False))
    sys.exit(1)


if __name__ == '__main__':
    main()
