#!/usr/bin/env python3
from __future__ import annotations
import json,re
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
import jobindsats_api as api
BASE=Path(__file__).resolve().parents[1]; OUT=BASE/'data'/'dashboard-data.json'; MONTHS=400
FOREIGN=['udenlandske statsborgere','lønindkomst i danmark','opholdsgrundlag','statsborgerskab','branche']; TOTAL=['antal lønmodtagere efter bopæl']
def pkey(p):
    m=re.fullmatch(r'(\d{4})M(\d{2})',str(p)); return (int(m.group(1)),int(m.group(2))) if m else (9999,str(p))
def ly(p):
    m=re.fullmatch(r'(\d{4})M(\d{2})',str(p)); return f'{int(m.group(1))-1}M{m.group(2)}' if m else None
def measures_foreign(rows): return api.best_col(rows,['antal'],['fuldtid','pct','procent']),api.best_col(rows,['fuldtid'],['pct','procent'])
def measure_total(rows):
    try:return api.best_col(rows,['fuldtidsbeskaeftigede'],['pct','procent'])
    except RuntimeError:return api.best_col(rows,['fuldtid'],['pct','procent'])
def series(rows,persons=None,fulltime=None):
    pc=api.best_col(rows,['periode']); g=defaultdict(lambda:{'p':0.,'f':0.,'ps':False,'fs':False})
    for r in rows:
        period=str(r.get(pc,'')).strip()
        if not period: continue
        if persons:
            v=api.num(r.get(persons));
            if v is not None:g[period]['p']+=v;g[period]['ps']=True
        if fulltime:
            v=api.num(r.get(fulltime));
            if v is not None:g[period]['f']+=v;g[period]['fs']=True
    labels=sorted(g,key=pkey); out={'labels':labels}
    if persons:out['persons']=[round(g[x]['p'],6) if g[x]['ps'] else None for x in labels]
    if fulltime:out['fulltime']=[round(g[x]['f'],6) if g[x]['fs'] else None for x in labels]
    return out
def lookup(s,k):return dict(zip(s['labels'],s[k]))
def yoy(s,k,period):
    d=lookup(s,k); prev=ly(period); a,b=d.get(period),d.get(prev); return prev,b,((a/b-1)*100 if a is not None and b not in (None,0) else None)
def total_label(x):return api.norm(x) in {'i alt','total','hele landet','alle','samlet'}
def nationalities(rows,pcol,total):
    c=api.best_col(rows,['statsborg'],distinct=True); explicit={}; tail=0.
    for r in rows:
        label=str(r.get(c) or '').strip(); v=api.num(r.get(pcol)); n=api.norm(label)
        if not label or v is None or total_label(label) or any(x in n for x in ('nordiske lande','eu eoes efta','udenlandske statsborgere')):continue
        if 'oevrige 3 lande' in n or 'oevrige tredjelande' in n or n.startswith('oevrige lande') or 'uoplyst' in n:tail+=float(v);continue
        if n not in explicit or v>explicit[n][1]:explicit[n]=(label,float(v))
    vals=sorted(explicit.values(),key=lambda x:x[1],reverse=True); chart=[{'label':l,'persons':v} for l,v in vals[:25]]; rest=sum(v for _,v in vals[25:])+tail
    if rest>0:chart.append({'label':'Øvrige lande','persons':round(rest,6)})
    top5=sum(v for _,v in vals[:5]); return {'items':chart,'representedNationalities':len(vals),'representedNationalitiesExact':tail==0,'top5Share':round(top5/total*100,4) if total else None,'aggregatedTailPresent':tail>0}
def branches(fr,tr,fp,ff,tf):
    fc=api.best_col(fr,['branche'],distinct=True);tc=api.best_col(tr,['branche'],distinct=True); F={};T={}
    for r in fr:
        lab=str(r.get(fc) or '').strip();k=api.norm(lab)
        if not lab or total_label(lab):continue
        d=F.setdefault(k,{'label':lab,'p':0.,'f':0.});a=api.num(r.get(fp));b=api.num(r.get(ff));d['p']+=float(a or 0);d['f']+=float(b or 0)
    for r in tr:
        lab=str(r.get(tc) or '').strip();k=api.norm(lab);v=api.num(r.get(tf))
        if lab and not total_label(lab) and v is not None:T[k]=(lab,float(v))
    out=[]
    for k,d in F.items():
        if k not in T:continue
        lab,den=T[k];out.append({'label':lab,'foreignPersons':round(d['p'],6),'foreignFulltime':round(d['f'],6),'totalFulltime':den,'share':round(d['f']/den*100,4) if den else None})
    out.sort(key=lambda x:x['totalFulltime'],reverse=True);high=max((x for x in out if x['share'] is not None),key=lambda x:x['share'],default=None);return out,high

def build():
    tables=api.get('tables',{'format':'json'});ft=api.find_table(tables,FOREIGN);tt=api.find_table(tables,TOTAL);fid=str(ft['table_id']);tid=str(tt['table_id'])
    fs=api.get(f'table/{fid}',{'format':'json'});ts=api.get(f'table/{tid}',{'format':'json'})
    fr=api.query(fid,fs,f'latest:{MONTHS}'); fp,ff=measures_foreign(fr); F=series(fr,fp,ff)
    tr=api.query(tid,ts,f'latest:{MONTHS}'); tf=measure_total(tr); T=series(tr,fulltime=tf)
    common=sorted(set(F['labels'])&set(T['labels']),key=pkey)
    if not F['labels'] or not T['labels'] or not common:raise RuntimeError('Manglende månedlige data eller fælles periode.')
    lf,lt,lc=F['labels'][-1],T['labels'][-1],common[-1];FL=lookup(F,'fulltime');TL=lookup(T,'fulltime');sh=[round(FL[p]/TL[p]*100,4) if FL.get(p) is not None and TL.get(p) not in (None,0) else None for p in common];sl=dict(zip(common,sh));slp=ly(lc);pp=sh[-1]-sl[slp] if sh[-1] is not None and sl.get(slp) is not None else None
    PL=lookup(F,'persons'); py=yoy(F,'persons',lf); fy=yoy(F,'fulltime',lf)
    nh=api.find_hierarchy(fs,['statsborg','nationalitet']); nl=api.select_level(nh,'nationality'); nr=api.query(fid,fs,lf,(nh,nl));np,_=measures_foreign(nr);N=nationalities(nr,np,PL[lf])
    fbh=api.find_hierarchy(fs,['branche']);tbh=api.find_hierarchy(ts,['branche']);fbl=api.select_level(fbh,'branch10');tbl=api.select_level(tbh,'branch10');fbr=api.query(fid,fs,lc,(fbh,fbl));tbr=api.query(tid,ts,lc,(tbh,tbl));bfp,bff=measures_foreign(fbr);btf=measure_total(tbr);B,H=branches(fbr,tbr,bfp,bff,btf)
    if not B:raise RuntimeError('Branchedata kunne ikke matches mellem kilderne.')
    now=datetime.now(ZoneInfo('Europe/Copenhagen')).isoformat(timespec='seconds')
    return {'meta':{'updated':now[:10],'retrievedAt':now[:10],'checkedAt':now,'sourceStatus':{'foreignWorkers':{'state':'ok','source':'Jobindsats.dk / STAR','dataset':fid,'latestPeriod':lf,'unit':'personer og fuldtidsbeskæftigede','seasonalAdjustment':'faktiske tal, ikke sæsonkorrigeret','checkedAt':now},'totalEmployees':{'state':'ok','source':'Jobindsats.dk / STAR','dataset':tid,'latestPeriod':lt,'unit':'fuldtidsbeskæftigede lønmodtagere','seasonalAdjustment':'faktiske tal, ikke sæsonkorrigeret','checkedAt':now}},'updateStatus':{'state':'ok','successful':['foreignWorkers','totalEmployees'],'failed':[],'checkedAt':now},'methodNotes':["Andelen er beregnet som udenlandske fuldtidsbeskæftigede divideret med Jobindsats-målingen 'Antal lønmodtagere efter bopæl'.","Den udenlandske serie kan også omfatte personer uden registreret bopæl i Danmark. Andelen bør derfor fortolkes med denne definitionsforskel for øje.",'Brancheandelene beregnes på seneste fælles måned og på den API-gruppering, der bedst matcher 10-grupperingen.']},'sections':{'foreignTimeSeries':{'labels':F['labels'],'persons':F['persons'],'fulltime':F['fulltime'],'kpi':{'period':lf,'persons':PL[lf],'personsLastYearPeriod':py[0],'personsLastYear':py[1],'personsYoY':round(py[2],4) if py[2] is not None else None,'fulltime':FL[lf],'fulltimeLastYearPeriod':fy[0],'fulltimeLastYear':fy[1],'fulltimeYoY':round(fy[2],4) if fy[2] is not None else None}},'share':{'labels':common,'values':sh,'kpi':{'period':lc,'value':sh[-1],'lastYearPeriod':slp,'lastYearValue':sl.get(slp),'changePp12m':round(pp,4) if pp is not None else None}},'nationalities':{'period':lf,**N},'branches':{'period':lc,'items':B,'highestShare':H}}}
def main():
    try:data=build()
    except Exception as e:
        try:data=json.loads(OUT.read_text(encoding='utf-8'))
        except Exception:data={'meta':{},'sections':{}}
        data.setdefault('meta',{})['updateStatus']={'state':'failed','successful':[],'failed':[str(e)],'checkedAt':datetime.now(ZoneInfo('Europe/Copenhagen')).isoformat(timespec='seconds')};OUT.parent.mkdir(parents=True,exist_ok=True);OUT.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');raise
    OUT.parent.mkdir(parents=True,exist_ok=True);OUT.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print('Opdateret til',data['meta']['sourceStatus']['foreignWorkers']['latestPeriod'])
if __name__=='__main__':main()
