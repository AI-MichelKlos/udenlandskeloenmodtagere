from __future__ import annotations
import json, math, os, re, time, urllib.error, urllib.parse, urllib.request
API_ROOT='https://api.jobindsats.dk/v3'

def norm(x):
    return re.sub(r'[^a-z0-9]+',' ',str(x or '').lower().replace('æ','ae').replace('ø','oe').replace('å','aa')).strip()

def walk(x):
    if isinstance(x,dict):
        yield x
        for v in x.values(): yield from walk(v)
    elif isinstance(x,list):
        for v in x: yield from walk(v)

def blob(d):
    return norm(' '.join(f'{k} {v}' for k,v in d.items() if isinstance(v,(str,int,float))))

def num(v):
    if v is None or isinstance(v,bool): return None
    if isinstance(v,(int,float)): n=float(v)
    else:
        t=str(v).strip().replace('\xa0','').replace(' ','')
        if not t or t.lower() in {'-','.','..','null','none','nan'}: return None
        if ',' in t: t=t.replace('.','').replace(',','.')
        elif re.fullmatch(r'-?\d{1,3}(?:\.\d{3})+',t): t=t.replace('.','')
        try: n=float(t)
        except ValueError: return None
    if not math.isfinite(n): return None
    return int(n) if n.is_integer() else round(n,6)

def get(path,params=None):
    token=os.environ.get('JOBINDSATS_API_TOKEN')
    if not token: raise RuntimeError('JOBINDSATS_API_TOKEN mangler. Opret GitHub-secretet API_ADGANG.')
    url=f"{API_ROOT}/{path.lstrip('/')}"
    if params: url += '?' + urllib.parse.urlencode(params,safe=':,*')
    req=urllib.request.Request(url,headers={'Accept':'application/json','Authorization':f'Bearer {token}','User-Agent':'Danske-A-kasser-udenlandskeloenmodtagere/1.0'})
    last=None
    for attempt in range(1,4):
        try:
            with urllib.request.urlopen(req,timeout=90) as r: return json.loads(r.read().decode('utf-8-sig'))
        except urllib.error.HTTPError as e:
            last=RuntimeError(f'Jobindsats HTTP {e.code}: {e.read().decode("utf-8",errors="replace")[:500]}')
            if e.code not in {429,500,502,503,504}: raise last
        except (TimeoutError,urllib.error.URLError,ConnectionError) as e: last=e
        if attempt<3: time.sleep(attempt*10)
    raise RuntimeError(f'Jobindsats-kald fejlede: {last}')

def records(payload):
    if isinstance(payload,dict) and isinstance(payload.get('columns'),list) and isinstance(payload.get('rows'),list):
        return [dict(zip(payload['columns'],r)) for r in payload['rows']]
    if isinstance(payload,list) and all(isinstance(x,dict) for x in payload): return payload
    for key in ('data','result','results'):
        v=payload.get(key) if isinstance(payload,dict) else None
        if isinstance(v,list) and all(isinstance(x,dict) for x in v): return v
    raise RuntimeError('Uventet Jobindsats-tabelformat.')

def find_table(payload,phrases):
    entries=[]
    for d in walk(payload):
        tid=d.get('table_id')
        if not tid and isinstance(d.get('id'),str) and re.fullmatch(r'y[0-9a-z_]+',d['id'].lower()): tid=d['id']
        if tid: entries.append(({**d,'table_id':tid},blob(d)))
    if not entries: raise RuntimeError('Ingen Jobindsats-tabeller fundet.')
    wanted=[norm(p) for p in phrases]
    scored=[]
    for d,b in entries:
        score=sum((100+len(p)) if p in b else sum(4 for w in p.split() if len(w)>3 and w in b) for p in wanted)
        scored.append((score,len(b),d,b))
    scored.sort(reverse=True,key=lambda x:(x[0],x[1]))
    d,b=scored[0][2],scored[0][3]
    if any(not all(w in b for w in p.split() if len(w)>3) for p in wanted): raise RuntimeError(f'Kunne ikke identificere Jobindsats-måling sikkert. Bedste kandidat: {d.get("table_id")} {b[:220]}')
    return d

def hierarchies(spec):
    out={}
    for d in walk(spec):
        hid=d.get('hierarchy_id')
        if isinstance(hid,str) and len(json.dumps(d,ensure_ascii=False))>len(json.dumps(out.get(hid,{}),ensure_ascii=False)): out[hid]=d
    return list(out.values())

def find_hierarchy(spec,words,preferred=()):
    choices=[]
    for d in hierarchies(spec):
        hid=str(d.get('hierarchy_id')); b=norm(json.dumps(d,ensure_ascii=False)); score=0
        if hid in preferred: score+=1000-preferred.index(hid)*20
        for w in words:
            n=norm(w); score += 200 if n in norm(hid) else 0; score += 60 if n in b else 0
        choices.append((score,len(b),d))
    choices.sort(reverse=True,key=lambda x:(x[0],x[1]))
    if not choices or choices[0][0]<=0: raise RuntimeError(f'Kunne ikke finde hierarki for {words}.')
    return choices[0][2]

def country_value(h):
    for d in walk(h):
        if isinstance(d.get('value_id'),str) and ('hele landet' in blob(d) or 'hele danmark' in blob(d)): return d['value_id']
    return '/'

def select_level(h,mode):
    levels={}
    for d in walk(h):
        lid=d.get('level_id')
        if isinstance(lid,str) and len(json.dumps(d,ensure_ascii=False))>len(json.dumps(levels.get(lid,{}),ensure_ascii=False)): levels[lid]=d
    if not levels: return None
    scores=[]
    for lid,d in levels.items():
        b=norm(json.dumps(d,ensure_ascii=False)); count=len({x.get('value_id') for x in walk(d) if isinstance(x.get('value_id'),str)})
        if mode=='nationality': score=(150 if any(x in b for x in ('land','statsborg','national')) else 0)+min(count,200)
        else: score=(250 if re.search(r'(^|\D)10(\D|$)',b) else 0)+(100 if ('hovedbranche' in b or 'branchegruppe' in b) else 0)+(160-abs(10-count)*12 if 8<=count<=15 else 0)
        scores.append((score,count,lid))
    scores.sort(reverse=True); return scores[0][2]

def query(table,spec,period,breakdown=None):
    geo=find_hierarchy(spec,['område','geografi','kommune','region'],('_hele_landet','_nykom','_reko','_region'))
    params={'mgroup.*':'*','period.M':period,f'hierarchy.{geo["hierarchy_id"]}':country_value(geo),'format':'json'}
    if breakdown:
        h,level=breakdown; params[f'hierarchy.{h["hierarchy_id"]}']=f'level:{level}' if level else '*'
    return records(get(f'data/{table}',params))

def best_col(rows,include,exclude=(),distinct=False):
    cols=[]; seen=set()
    for r in rows:
        for c in r:
            if c not in seen: seen.add(c); cols.append(c)
    choices=[]
    for c in cols:
        n=norm(c); score=sum(100 for x in include if norm(x) in n)-sum(150 for x in exclude if norm(x) in n)
        if score>0:
            d=len({str(r.get(c)) for r in rows if r.get(c) not in (None,'')}); choices.append((score+(min(d,100) if distinct else 0),d,c))
    if not choices: raise RuntimeError(f'Ingen kolonne matcher {include}. Kolonner: {cols}')
    choices.sort(reverse=True); return choices[0][2]
