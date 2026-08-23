#!/usr/bin/env python3
import json
import jobindsats_api as api
import fetch_sources as fs


def main():
    tables = api.get('tables', {'format': 'json'})
    table = api.find_table(tables, fs.RETENTION)
    tid = str(table['table_id'])
    spec = api.get(f'table/{tid}', {'format': 'json'})
    status_h = api.find_hierarchy(spec, ['arbejdsmarkedsstatus', 'status'], ('_ams_status',))
    rows = fs.query_custom(tid, spec, 'latest:84', [(status_h, None)])
    print('RETENTION DEBUG table', tid, 'rows', len(rows))
    print('RETENTION DEBUG columns', fs.columns(rows))
    print('RETENTION DEBUG sample', json.dumps(rows[:12], ensure_ascii=False))


if __name__ == '__main__':
    main()
