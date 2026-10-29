"""Strict units and coverage only; evaluation damage totals/ranks remain reserved."""
import csv
from decimal import Decimal,ROUND_HALF_EVEN
import gzip
import hashlib
import json
import re
from config import ROOT,STATES,TYPES,YEARS,FIELDS


def cents(token):
    text=token.strip()
    if not text:return None
    match=re.fullmatch(r'(\d+(?:\.\d+)?)([KMB]?)',text,flags=re.I)
    if not match:raise ValueError('Unrecognized damage token: '+repr(token))
    scale={'':1,'K':1000,'M':1000000,'B':1000000000}[match[2].upper()]
    value=Decimal(match[1])*scale*100
    if value!=value.to_integral_value():raise ValueError('Sub-cent source precision requires investigation')
    return int(value)


def quantile_cents(values,p):
    if not values or not 0<=p<=1:raise ValueError('Nonempty values and probability in [0,1] required')
    ordered=sorted(values);h=Decimal(str(p))*(len(ordered)-1);lower=int(h)
    result=Decimal(ordered[lower])+(h-lower)*(ordered[min(lower+1,len(ordered)-1)]-ordered[lower])
    return int(result.quantize(Decimal(1),rounding=ROUND_HALF_EVEN))


def write_csv(path,rows):
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('w',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,list(rows[0]),lineterminator='\n');w.writeheader();w.writerows(rows)


def ingest(root=ROOT):
    manifest=json.loads((root/'data/source/manifest.json').read_text(encoding='utf-8'))
    assert manifest['status']=='COMPLETE' and len(manifest['files'])==9
    rows=[];seen=set();errors=[]
    for record in manifest['files']:
        blob=(root/record['subset_file']).read_bytes()
        assert hashlib.sha256(blob).hexdigest()==record['subset_sha256']
        with gzip.open(root/record['subset_file'],'rt',encoding='utf-8',newline='') as f:
            reader=csv.DictReader(f);assert reader.fieldnames==['source_row',*FIELDS]
            selected=list(reader)
        assert len(selected)==record['selected_rows']
        for item in selected:
            assert item['STATE'] in STATES and item['EVENT_TYPE'] in TYPES and item['CZ_TYPE']=='C'
            assert all(item[k].isdigit() for k in ['EVENT_ID','EPISODE_ID','YEAR','BEGIN_YEARMONTH'])
            assert int(item['YEAR'])==record['year']==int(item['BEGIN_YEARMONTH'])//100
            assert 1<=int(item['BEGIN_YEARMONTH'])%100<=12 and item['WFO']
            assert item['EVENT_ID'] not in seen;seen.add(item['EVENT_ID'])
            try:amount=cents(item['DAMAGE_PROPERTY'])
            except ValueError as error:errors.append({'year':record['year'],'event_id':item['EVENT_ID'],'error':str(error)});amount=None
            rows.append({'source_year':record['year'],'source_row':int(item['source_row']),
                         'event_id':int(item['EVENT_ID']),'episode_id':int(item['EPISODE_ID']),
                         'state':item['STATE'],'year':int(item['YEAR']),'yearmonth':int(item['BEGIN_YEARMONTH']),
                         'event_type':item['EVENT_TYPE'],'cz_type':item['CZ_TYPE'],'wfo':item['WFO'],
                         'damage_token':item['DAMAGE_PROPERTY'],'damage_cents':amount})
    write_csv(root/'data/reports.csv',rows)
    cells=[];holds=[]
    for state in STATES:
        for year in YEARS:
            selected=[r for r in rows if r['state']==state and r['year']==year]
            cell={'state':state,'year':year,'reports':len(selected),
                  'missing':sum(r['damage_cents'] is None for r in selected),
                  'explicit_zero':sum(r['damage_cents']==0 for r in selected),
                  'positive':sum(r['damage_cents'] is not None and r['damage_cents']>0 for r in selected)}
            assert sum(cell[k] for k in ['missing','explicit_zero','positive'])==cell['reports']
            if cell['reports']<100 or cell['positive']<10:holds.append({'state':state,'year':year,'reason':'coverage below fixed100reports/10positive'})
            cells.append(cell)
    calibration_counts={t:sum(r['event_type']==t and r['year']<=2019 and r['damage_cents'] is not None and r['damage_cents']>0 for r in rows) for t in TYPES}
    for t,count in calibration_counts.items():
        if count<20:holds.append({'type':t,'reason':'fewer than20positive calibration values'})
    report={'status':'PASS_SOURCE_GATE' if not errors and not holds else 'SOURCE_HOLD',
            'source_files':9,'selected_rows':len(rows),'source_cells':len(rows)*len(FIELDS),
            'calibration_type_positive_counts':calibration_counts,'errors':errors,'coverage_holds':holds,
            'manifest_sha256':hashlib.sha256((root/'data/source/manifest.json').read_bytes()).hexdigest(),
            'scope':'Coverage and strict token parsing only. No evaluation damage total, rank, scenario or bootstrap result computed.'}
    write_csv(root/'results/source_coverage.csv',cells)
    (root/'results/source_accounting.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report))
    assert report['status']=='PASS_SOURCE_GATE','Retain source hold without weakening criteria'


if __name__=='__main__':ingest()
