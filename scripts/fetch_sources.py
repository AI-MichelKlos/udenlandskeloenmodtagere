#!/usr/bin/env python3
from __future__ import annotations

import json
import re
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import jobindsats_api as api

BASE = Path(__file__).resolve().parents[1]
OUT = BASE / 'data' / 'dashboard-data.json'
MONTHS = 222
DETAIL_MONTHS = 120
RETENTION_MONTHS = 84

FOREIGN = ['udenlandske statsborgere', 'l\u00f8nindkomst i danmark', 'opholdsgrundlag', 'statsborgerskab', 'branche']
TOTAL = ['antal l\u00f8nmodtagere efter bop\u00e6l']
RETENTION = ['udenlandske statsborgere', 'arbejdsmarkedsstatus', 'over tid']


def pkey(period):
    m = re.fullmatch(r'(\d{4})M(\d{2})', str(period))
    return (int(m.group(1)), int(m.group(2))) if m else (9999, str(period))


def ly(period):
    m = re.fullmatch(r'(\d{4})M(\d{2})', str(period))
    return f'{int(m.group(1)) - 1}M{m.group(2)}' if m else None


def measures_foreign(rows):
    return (
        api.best_col(rows, ['antal'], ['fuldtid', 'pct', 'procent']),
        api.best_col(rows, ['fuldtid'], ['pct', 'procent']),
    )


def measure_total(rows):
    try:
        return api.best_col(rows, ['fuldtidsbeskaeftigede'], ['pct', 'procent'])
    except RuntimeError:
        return api.best_col(rows, ['fuldtid'], ['pct', 'procent'])


def series(rows, persons=None, fulltime=None):
    pc = api.best_col(rows, ['periode'])
    grouped = defaultdict(lambda: {'p': 0.0, 'f': 0.0, 'ps': False, 'fs': False})
    for row in rows:
        period = str(row.get(pc, '')).strip()
        if not period:
            continue
        if persons:
            value = api.num(row.get(persons))
            if value is not None:
                grouped[period]['p'] += value
                grouped[period]['ps'] = True
        if fulltime:
            value = api.num(row.get(fulltime))
            if value is not None:
                grouped[period]['f'] += value
                grouped[period]['fs'] = True
    labels = sorted(grouped, key=pkey)
    out = {'labels': labels}
    if persons:
        out['persons'] = [round(grouped[x]['p'], 6) if grouped[x]['ps'] else None for x in labels]
    if fulltime:
        out['fulltime'] = [round(grouped[x]['f'], 6) if grouped[x]['fs'] else None for x in labels]
    return out


def lookup(data, key):
    return dict(zip(data['labels'], data[key]))


def yoy(data, key, period):
    values = lookup(data, key)
    previous = ly(period)
    current_value = values.get(period)
    previous_value = values.get(previous)
    change = (current_value / previous_value - 1) * 100 if current_value is not None and previous_value not in (None, 0) else None
    return previous, previous_value, change


def total_label(value):
    return api.norm(value) in {'i alt', 'total', 'hele landet', 'alle', 'samlet'}


def columns(rows):
    out = []
    seen = set()
    for row in rows:
        for col in row:
            if col not in seen:
                seen.add(col)
                out.append(col)
    return out


def level_defs(hierarchy):
    levels = {}
    for item in api.walk(hierarchy):
        level_id = item.get('level_id')
        if not isinstance(level_id, str):
            continue
        raw = json.dumps(item, ensure_ascii=False)
        if level_id not in levels or len(raw) > len(json.dumps(levels[level_id], ensure_ascii=False)):
            levels[level_id] = item
    return levels


def pick_level(hierarchy, words=(), target=None, minimum=1, maximum=9999):
    candidates = []
    for level_id, item in level_defs(hierarchy).items():
        blob = api.norm(json.dumps(item, ensure_ascii=False))
        values = {x.get('value_id') for x in api.walk(item) if isinstance(x.get('value_id'), str)}
        count = len(values)
        if count < minimum or count > maximum:
            continue
        score = 0
        for word in words:
            nword = api.norm(word)
            if nword in api.norm(level_id):
                score += 220
            if nword in blob:
                score += 80
        if target is not None:
            score += max(0, 220 - abs(count - target) * 35)
        candidates.append((score, -abs((target or count) - count), -count, level_id))
    if not candidates:
        raise RuntimeError(f'Kunne ikke finde niveau i hierarki {hierarchy.get("hierarchy_id")}')
    candidates.sort(reverse=True)
    return candidates[0][3]


def query_custom(table, spec, period, breakdowns=(), geo_level=None):
    geo = api.find_hierarchy(spec, ['omr\u00e5de', 'geografi', 'kommune', 'region'], ('_hele_landet', '_nykom', '_reko', '_region'))
    params = {'mgroup.*': '*', 'period.M': period, 'format': 'json'}
    if geo_level:
        params[f'hierarchy.{geo["hierarchy_id"]}'] = f'level:{geo_level}'
    else:
        params[f'hierarchy.{geo["hierarchy_id"]}'] = api.country_value(geo)
    for hierarchy, level in breakdowns:
        if hierarchy['hierarchy_id'] == geo['hierarchy_id']:
            continue
        params[f'hierarchy.{hierarchy["hierarchy_id"]}'] = f'level:{level}' if level else '*'
    return api.records(api.get(f'data/{table}', params))


def nationalities(rows, pcol, total):
    c = api.best_col(rows, ['statsborg'], distinct=True)
    explicit = {}
    tail = 0.0
    for row in rows:
        label = str(row.get(c) or '').strip()
        value = api.num(row.get(pcol))
        n = api.norm(label)
        if not label or value is None or total_label(label) or any(x in n for x in ('nordiske lande', 'eu eoes efta', 'udenlandske statsborgere')):
            continue
        if 'oevrige 3 lande' in n or 'oevrige tredjelande' in n or n.startswith('oevrige lande') or 'uoplyst' in n:
            tail += float(value)
            continue
        if n not in explicit or value > explicit[n][1]:
            explicit[n] = (label, float(value))
    values = sorted(explicit.values(), key=lambda x: x[1], reverse=True)
    chart = [{'label': label, 'persons': value} for label, value in values[:25]]
    rest = sum(value for _, value in values[25:]) + tail
    if rest > 0:
        chart.append({'label': '\u00d8vrige lande', 'persons': round(rest, 6)})
    top5 = sum(value for _, value in values[:5])
    return {
        'items': chart,
        'representedNationalities': len(values),
        'representedNationalitiesExact': tail == 0,
        'top5Share': round(top5 / total * 100, 4) if total else None,
        'aggregatedTailPresent': tail > 0,
    }


def branches(foreign_rows, total_rows, fp, ff, tf):
    fc = api.best_col(foreign_rows, ['branche'], distinct=True)
    tc = api.best_col(total_rows, ['branche'], distinct=True)
    foreign = {}
    total = {}
    for row in foreign_rows:
        label = str(row.get(fc) or '').strip()
        key = api.norm(label)
        if not label or total_label(label):
            continue
        item = foreign.setdefault(key, {'label': label, 'p': 0.0, 'f': 0.0})
        pvalue = api.num(row.get(fp))
        fvalue = api.num(row.get(ff))
        item['p'] += float(pvalue or 0)
        item['f'] += float(fvalue or 0)
    for row in total_rows:
        label = str(row.get(tc) or '').strip()
        key = api.norm(label)
        value = api.num(row.get(tf))
        if label and not total_label(label) and value is not None:
            total[key] = (label, float(value))
    out = []
    for key, item in foreign.items():
        if key not in total:
            continue
        label, denominator = total[key]
        out.append({
            'label': label,
            'foreignPersons': round(item['p'], 6),
            'foreignFulltime': round(item['f'], 6),
            'totalFulltime': denominator,
            'share': round(item['f'] / denominator * 100, 4) if denominator else None,
        })
    out.sort(key=lambda x: x['totalFulltime'], reverse=True)
    highest = max((x for x in out if x['share'] is not None), key=lambda x: x['share'], default=None)
    return out, highest


def residence(rows, pcol):
    pc = api.best_col(rows, ['periode'])
    cc = api.best_col(rows, ['bop\u00e6l', 'bopael'], distinct=True)
    grouped = defaultdict(lambda: {'dk': 0.0, 'commuter': 0.0, 'dk_seen': False, 'commuter_seen': False})
    for row in rows:
        period = str(row.get(pc) or '').strip()
        label = str(row.get(cc) or '').strip()
        value = api.num(row.get(pcol))
        if not period or not label or value is None:
            continue
        n = api.norm(label)
        if 'uden bopael i danmark' in n or ('uden' in n and 'bopael' in n and 'danmark' in n):
            grouped[period]['commuter'] += float(value)
            grouped[period]['commuter_seen'] = True
        elif 'bopael i danmark' in n or ('danmark' in n and 'bopael' in n and 'uden' not in n):
            grouped[period]['dk'] += float(value)
            grouped[period]['dk_seen'] = True
    labels = sorted([p for p, values in grouped.items() if values['dk_seen'] or values['commuter_seen']], key=pkey)
    if not labels:
        raise RuntimeError('Bop\u00e6lsfordelingen gav ingen genkendelige kategorier.')
    dk = [round(grouped[p]['dk'], 6) if grouped[p]['dk_seen'] else None for p in labels]
    commuter = [round(grouped[p]['commuter'], 6) if grouped[p]['commuter_seen'] else None for p in labels]
    last = labels[-1]
    dk_last = grouped[last]['dk'] if grouped[last]['dk_seen'] else None
    commuter_last = grouped[last]['commuter'] if grouped[last]['commuter_seen'] else None
    total = (dk_last or 0) + (commuter_last or 0)
    return {
        'period': last,
        'labels': labels,
        'series': [
            {'label': 'Bop\u00e6l i Danmark', 'values': dk},
            {'label': 'Pendlere uden bop\u00e6l i Danmark', 'values': commuter},
        ],
        'kpi': {
            'resident': round(dk_last, 6) if dk_last is not None else None,
            'commuters': round(commuter_last, 6) if commuter_last is not None else None,
            'commuterShare': round(commuter_last / total * 100, 4) if commuter_last is not None and total else None,
        },
    }


def category_timeseries(rows, category_col, value_col, max_categories=9):
    pc = api.best_col(rows, ['periode'])
    grouped = defaultdict(lambda: defaultdict(float))
    seen = defaultdict(set)
    labels_by_key = {}
    for row in rows:
        period = str(row.get(pc) or '').strip()
        label = str(row.get(category_col) or '').strip()
        value = api.num(row.get(value_col))
        if not period or not label or value is None or total_label(label):
            continue
        key = api.norm(label)
        if not key or key in {'uoplyst', 'ukendt'}:
            continue
        grouped[period][key] += float(value)
        seen[period].add(key)
        labels_by_key.setdefault(key, label)
    periods = sorted(grouped, key=pkey)
    if not periods:
        raise RuntimeError('Kategorifordelingen gav ingen data.')
    last = periods[-1]
    ranked = sorted(grouped[last], key=lambda key: grouped[last][key], reverse=True)
    keep = ranked[:max_categories]
    rest = [key for key in labels_by_key if key not in keep]
    out_series = []
    for key in keep:
        out_series.append({'label': labels_by_key[key], 'values': [round(grouped[p].get(key), 6) if key in seen[p] else None for p in periods]})
    if rest:
        values = []
        for period in periods:
            amount = sum(grouped[period].get(key, 0.0) for key in rest)
            present = any(key in seen[period] for key in rest)
            values.append(round(amount, 6) if present else None)
        if any(value not in (None, 0) for value in values):
            out_series.append({'label': '\u00d8vrige', 'values': values})
    latest_items = []
    for entry in out_series:
        value = entry['values'][-1]
        latest_items.append({'label': entry['label'], 'persons': value})
    latest_items.sort(key=lambda x: (x['persons'] is not None, x['persons'] or 0), reverse=True)
    return {'period': last, 'labels': periods, 'series': out_series, 'items': latest_items}


def regions(rows, pcol, fcol, national_total):
    area_col = api.best_col(rows, ['omr\u00e5de', 'omraade', 'region'], distinct=True)
    out = []
    for row in rows:
        label = str(row.get(area_col) or '').strip()
        if not label or total_label(label):
            continue
        n = api.norm(label)
        if 'region' not in n and n not in {'hovedstaden', 'sjaelland', 'syddanmark', 'midtjylland', 'nordjylland'}:
            continue
        persons = api.num(row.get(pcol))
        fulltime = api.num(row.get(fcol))
        if persons is None:
            continue
        out.append({
            'label': label,
            'persons': persons,
            'fulltime': fulltime,
            'shareOfForeignWorkers': round(float(persons) / national_total * 100, 4) if national_total else None,
        })
    unique = {}
    for item in out:
        key = api.norm(item['label'])
        if key not in unique or item['persons'] > unique[key]['persons']:
            unique[key] = item
    out = sorted(unique.values(), key=lambda x: x['persons'], reverse=True)
    if len(out) < 5:
        raise RuntimeError(f'Regionsfordelingen gav kun {len(out)} genkendelige regioner.')
    return out


def offset_from_text(value):
    text = api.norm(value)
    for offset in (60, 48, 36, 24, 12, 6):
        if re.search(rf'(^|\D){offset}(\D|$)', text):
            return offset
    return None


def retention_bucket(label):
    n = api.norm(label)
    if 'lonmodtagerbeskaeftigelse' in n or 'loenmodtagerbeskaeftigelse' in n:
        return 'employed'
    if 'alene offentlig ydelse' in n:
        return 'benefitOnly'
    if 'hverken' in n and 'bopael' in n:
        return 'outside'
    return None


def retention(rows):
    pc = api.best_col(rows, ['periode'])
    cols = columns(rows)
    status_col = None
    best_status_score = -1
    for col in cols:
        values = {api.norm(row.get(col)) for row in rows if row.get(col) not in (None, '')}
        score = sum(1 for value in values if retention_bucket(value)) * 20
        if 'arbejdsmarkedsstatus' in api.norm(col):
            score += 10
        if score > best_status_score:
            best_status_score = score
            status_col = col
    if not status_col or best_status_score <= 0:
        raise RuntimeError(f'Kunne ikke identificere arbejdsmarkedsstatus. Kolonner: {cols}')

    offset_col = None
    offset_col_score = 0
    for col in cols:
        if col == status_col or col == pc:
            continue
        offsets = {offset_from_text(row.get(col)) for row in rows if row.get(col) not in (None, '')}
        offsets.discard(None)
        if len(offsets) > offset_col_score:
            offset_col_score = len(offsets)
            offset_col = col

    data = defaultdict(lambda: defaultdict(lambda: defaultdict(float)))
    present = defaultdict(lambda: defaultdict(set))
    offsets = (6, 12, 24, 36, 48, 60)

    if offset_col and offset_col_score >= 2:
        value_candidates = []
        for col in cols:
            n = api.norm(col)
            numeric_count = sum(api.num(row.get(col)) is not None for row in rows)
            if numeric_count and ('pct' in n or 'procent' in n or 'andel' in n):
                value_candidates.append((numeric_count, col))
        if not value_candidates:
            raise RuntimeError(f'Kunne ikke finde procentkolonne i retention-data. Kolonner: {cols}')
        value_col = sorted(value_candidates, reverse=True)[0][1]
        for row in rows:
            period = str(row.get(pc) or '').strip()
            bucket = retention_bucket(row.get(status_col))
            offset = offset_from_text(row.get(offset_col))
            value = api.num(row.get(value_col))
            if period and bucket and offset in offsets and value is not None:
                data[period][offset][bucket] += float(value)
                present[period][offset].add(bucket)
    else:
        measure_cols = {}
        for col in cols:
            n = api.norm(col)
            offset = offset_from_text(col)
            if offset in offsets and ('pct' in n or 'procent' in n or 'andel' in n):
                measure_cols[offset] = col
        if len(measure_cols) < 2:
            raise RuntimeError(f'Kunne ikke identificere retention-m\u00e5linger. Kolonner: {cols}')
        for row in rows:
            period = str(row.get(pc) or '').strip()
            bucket = retention_bucket(row.get(status_col))
            if not period or not bucket:
                continue
            for offset, col in measure_cols.items():
                value = api.num(row.get(col))
                if value is not None:
                    data[period][offset][bucket] += float(value)
                    present[period][offset].add(bucket)

    periods = sorted(data, key=pkey)
    if not periods:
        raise RuntimeError('Retention-m\u00e5lingen gav ingen anvendelige perioder.')

    def employed_value(period, offset):
        return round(data[period][offset].get('employed'), 4) if 'employed' in present[period][offset] else None

    complete = [period for period in periods if all(employed_value(period, offset) is not None for offset in offsets)]
    if complete:
        cohort = complete[-1]
    else:
        cohort = max(periods, key=lambda period: (sum(employed_value(period, offset) is not None for offset in offsets), pkey(period)))
    employed = [employed_value(cohort, offset) for offset in offsets]
    if sum(value is not None for value in employed) < 2:
        raise RuntimeError('Retention-m\u00e5lingen havde for f\u00e5 brugbare nedslag for en kohorte.')

    def values_for(bucket):
        result = []
        for offset in offsets:
            value = data[cohort][offset].get(bucket)
            result.append(round(value, 4) if bucket in present[cohort][offset] else None)
        return result

    return {
        'sourceLatestPeriod': periods[-1],
        'cohortPeriod': cohort,
        'offsets': list(offsets),
        'employedPct': employed,
        'benefitOnlyPct': values_for('benefitOnly'),
        'outsidePct': values_for('outside'),
    }


def build():
    tables = api.get('tables', {'format': 'json'})
    foreign_table = api.find_table(tables, FOREIGN)
    total_table = api.find_table(tables, TOTAL)
    retention_table = api.find_table(tables, RETENTION)
    fid = str(foreign_table['table_id'])
    tid = str(total_table['table_id'])
    rid = str(retention_table['table_id'])

    fs = api.get(f'table/{fid}', {'format': 'json'})
    ts = api.get(f'table/{tid}', {'format': 'json'})
    rs = api.get(f'table/{rid}', {'format': 'json'})

    foreign_rows = api.query(fid, fs, f'latest:{MONTHS}')
    fp, ff = measures_foreign(foreign_rows)
    foreign_series = series(foreign_rows, fp, ff)

    total_rows = api.query(tid, ts, f'latest:{MONTHS}')
    tf = measure_total(total_rows)
    total_series = series(total_rows, fulltime=tf)

    common = sorted(set(foreign_series['labels']) & set(total_series['labels']), key=pkey)
    if not foreign_series['labels'] or not total_series['labels'] or not common:
        raise RuntimeError('Manglende m\u00e5nedlige data eller f\u00e6lles periode.')

    lf = foreign_series['labels'][-1]
    lt = total_series['labels'][-1]
    lc = common[-1]
    foreign_fulltime = lookup(foreign_series, 'fulltime')
    total_fulltime = lookup(total_series, 'fulltime')
    shares = [round(foreign_fulltime[p] / total_fulltime[p] * 100, 4) if foreign_fulltime.get(p) is not None and total_fulltime.get(p) not in (None, 0) else None for p in common]
    share_lookup = dict(zip(common, shares))
    share_last_year = ly(lc)
    pp_change = shares[-1] - share_lookup[share_last_year] if shares[-1] is not None and share_lookup.get(share_last_year) is not None else None

    foreign_persons = lookup(foreign_series, 'persons')
    persons_yoy = yoy(foreign_series, 'persons', lf)
    fulltime_yoy = yoy(foreign_series, 'fulltime', lf)

    nationality_h = api.find_hierarchy(fs, ['statsborg', 'nationalitet'])
    nationality_l = api.select_level(nationality_h, 'nationality')
    nationality_rows = api.query(fid, fs, lf, (nationality_h, nationality_l))
    nationality_p, _ = measures_foreign(nationality_rows)
    nationality_data = nationalities(nationality_rows, nationality_p, foreign_persons[lf])

    foreign_branch_h = api.find_hierarchy(fs, ['branche'])
    total_branch_h = api.find_hierarchy(ts, ['branche'])
    foreign_branch_l = api.select_level(foreign_branch_h, 'branch10')
    total_branch_l = api.select_level(total_branch_h, 'branch10')
    foreign_branch_rows = api.query(fid, fs, lc, (foreign_branch_h, foreign_branch_l))
    total_branch_rows = api.query(tid, ts, lc, (total_branch_h, total_branch_l))
    branch_fp, branch_ff = measures_foreign(foreign_branch_rows)
    branch_tf = measure_total(total_branch_rows)
    branch_data, highest_branch = branches(foreign_branch_rows, total_branch_rows, branch_fp, branch_ff, branch_tf)
    if not branch_data:
        raise RuntimeError('Branchedata kunne ikke matches mellem kilderne.')

    residence_h = api.find_hierarchy(fs, ['bop\u00e6lsland', 'bop\u00e6l', 'bopaelsland', 'bopael'])
    residence_l = pick_level(residence_h, ['bop\u00e6l', 'bopael'], target=2, minimum=2, maximum=10)
    residence_rows = query_custom(fid, fs, f'latest:{DETAIL_MONTHS}', [(residence_h, residence_l)])
    residence_p, _ = measures_foreign(residence_rows)
    residence_data = residence(residence_rows, residence_p)

    permit_h = api.find_hierarchy(fs, ['opholdsgrundlag'])
    permit_l = pick_level(permit_h, ['opholdsgrundlag', 'gruppe'], target=9, minimum=4, maximum=20)
    permit_rows = query_custom(fid, fs, f'latest:{DETAIL_MONTHS}', [(permit_h, permit_l)])
    permit_p, _ = measures_foreign(permit_rows)
    permit_col = api.best_col(permit_rows, ['opholdsgrundlag'], distinct=True)
    permit_data = category_timeseries(permit_rows, permit_col, permit_p, max_categories=9)

    geo_h = api.find_hierarchy(fs, ['omr\u00e5de', 'geografi', 'kommune', 'region'], ('_hele_landet', '_nykom', '_reko', '_region'))
    region_l = pick_level(geo_h, ['region'], target=5, minimum=5, maximum=8)
    region_rows = query_custom(fid, fs, lf, geo_level=region_l)
    region_p, region_f = measures_foreign(region_rows)
    region_data = regions(region_rows, region_p, region_f, foreign_persons[lf])

    retention_status_h = api.find_hierarchy(rs, ['arbejdsmarkedsstatus', 'status'], ('_ams_status',))
    retention_rows = query_custom(rid, rs, f'latest:{RETENTION_MONTHS}', [(retention_status_h, None)])
    retention_data = retention(retention_rows)

    now = datetime.now(ZoneInfo('Europe/Copenhagen')).isoformat(timespec='seconds')
    sources = {
        'foreignWorkers': {'state': 'ok', 'source': 'Jobindsats.dk / STAR', 'dataset': fid, 'latestPeriod': lf, 'unit': 'personer og fuldtidsbesk\u00e6ftigede', 'seasonalAdjustment': 'faktiske tal, ikke s\u00e6sonkorrigeret', 'checkedAt': now},
        'totalEmployees': {'state': 'ok', 'source': 'Jobindsats.dk / STAR', 'dataset': tid, 'latestPeriod': lt, 'unit': 'fuldtidsbesk\u00e6ftigede l\u00f8nmodtagere', 'seasonalAdjustment': 'faktiske tal, ikke s\u00e6sonkorrigeret', 'checkedAt': now},
        'residence': {'state': 'ok', 'source': 'Jobindsats.dk / STAR', 'dataset': fid, 'latestPeriod': residence_data['period'], 'unit': 'personer', 'seasonalAdjustment': 'faktiske tal, ikke s\u00e6sonkorrigeret', 'checkedAt': now},
        'residencePermits': {'state': 'ok', 'source': 'Jobindsats.dk / STAR', 'dataset': fid, 'latestPeriod': permit_data['period'], 'unit': 'personer', 'seasonalAdjustment': 'faktiske tal, ikke s\u00e6sonkorrigeret', 'checkedAt': now},
        'regions': {'state': 'ok', 'source': 'Jobindsats.dk / STAR', 'dataset': fid, 'latestPeriod': lf, 'unit': 'personer og fuldtidsbesk\u00e6ftigede', 'seasonalAdjustment': 'faktiske tal, ikke s\u00e6sonkorrigeret', 'checkedAt': now},
        'retention': {'state': 'ok', 'source': 'Jobindsats.dk / STAR', 'dataset': rid, 'latestPeriod': retention_data['sourceLatestPeriod'], 'selectedCohort': retention_data['cohortPeriod'], 'unit': 'andel, pct.', 'seasonalAdjustment': 'ikke relevant', 'checkedAt': now},
    }
    successful = list(sources)
    method_notes = [
        "Andelen er beregnet som udenlandske fuldtidsbesk\u00e6ftigede divideret med Jobindsats-m\u00e5lingen 'Antal l\u00f8nmodtagere efter bop\u00e6l'.",
        'Bop\u00e6lsstatus f\u00f8lger CPR-registreringen. Personer uden registreret bop\u00e6l i Danmark, men med l\u00f8nindkomst i Danmark, vises som pendlere.',
        'Geografi er opgjort efter arbejdsstedets placering, ikke den ansattes bop\u00e6l.',
        'Opholdsgrundlag er det senest registrerede opholdsgrundlag i m\u00e5neden. Samme person kan kun have \u00e9t opholdsgrundlag i en m\u00e5nedsopg\u00f8relse.',
        'Arbejdsmarkedsstatus over tid omfatter udenlandske statsborgere med l\u00f8nmodtagerbesk\u00e6ftigelse i den valgte m\u00e5ned. RUT-besk\u00e6ftigelse indg\u00e5r ikke i denne m\u00e5ling.',
        'Brancheandelene beregnes p\u00e5 seneste f\u00e6lles m\u00e5ned og p\u00e5 den API-gruppering, der bedst matcher 10-grupperingen.',
    ]

    return {
        'meta': {
            'updated': now[:10],
            'retrievedAt': now[:10],
            'checkedAt': now,
            'sourceStatus': sources,
            'updateStatus': {'state': 'ok', 'successful': successful, 'failed': [], 'checkedAt': now},
            'methodNotes': method_notes,
        },
        'sections': {
            'foreignTimeSeries': {
                'labels': foreign_series['labels'],
                'persons': foreign_series['persons'],
                'fulltime': foreign_series['fulltime'],
                'kpi': {
                    'period': lf,
                    'persons': foreign_persons[lf],
                    'personsLastYearPeriod': persons_yoy[0],
                    'personsLastYear': persons_yoy[1],
                    'personsYoY': round(persons_yoy[2], 4) if persons_yoy[2] is not None else None,
                    'fulltime': foreign_fulltime[lf],
                    'fulltimeLastYearPeriod': fulltime_yoy[0],
                    'fulltimeLastYear': fulltime_yoy[1],
                    'fulltimeYoY': round(fulltime_yoy[2], 4) if fulltime_yoy[2] is not None else None,
                },
            },
            'share': {'labels': common, 'values': shares, 'kpi': {'period': lc, 'value': shares[-1], 'lastYearPeriod': share_last_year, 'lastYearValue': share_lookup.get(share_last_year), 'changePp12m': round(pp_change, 4) if pp_change is not None else None}},
            'nationalities': {'period': lf, **nationality_data},
            'branches': {'period': lc, 'items': branch_data, 'highestShare': highest_branch},
            'residence': residence_data,
            'residencePermits': permit_data,
            'regions': {'period': lf, 'items': region_data},
            'retention': retention_data,
        },
    }


def main():
    try:
        data = build()
    except Exception as exc:
        try:
            data = json.loads(OUT.read_text(encoding='utf-8'))
        except Exception:
            data = {'meta': {}, 'sections': {}}
        data.setdefault('meta', {})['updateStatus'] = {
            'state': 'failed',
            'successful': [],
            'failed': [str(exc)],
            'checkedAt': datetime.now(ZoneInfo('Europe/Copenhagen')).isoformat(timespec='seconds'),
        }
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        raise
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print('Opdateret til', data['meta']['sourceStatus']['foreignWorkers']['latestPeriod'])


if __name__ == '__main__':
    main()
