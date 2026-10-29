"""Independent source parsing, SQL accounting and rational calibration quantiles."""
import csv
from decimal import Decimal
from fractions import Fraction
import gzip
import hashlib
import json
from pathlib import Path
import sqlite3
ROOT=Path(__file__).resolve().parents[1]
STATES=['ILLINOIS','INDIANA','MICHIGAN','MINNESOTA','OHIO','WISCONSIN']
TYPES=['Flash Flood','Flood','Hail','Thunderstorm Wind','Tornado']


def verify(root=ROOT):
    manifest=json.loads((root/'data/source/manifest.json').read_text());assert manifest['status']=='COMPLETE'
    expected=[]
    for record in manifest['files']:
        source=root/record['subset_file']
        assert hashlib.sha256(source.read_bytes()).hexdigest()==record['subset_sha256']
        with gzip.open(source,'rt',encoding='utf-8',newline='') as f:
            for row in csv.DictReader(f):
                token=row['DAMAGE_PROPERTY'].strip()
                if not token:amount=None
                else:
                    suffix=token[-1].upper() if token[-1].isalpha() else ''
                    scale={'':1,'K':10**3,'M':10**6,'B':10**9}[suffix]
                    numeric=token[:-1] if suffix else token
                    assert numeric.count('.')<=1 and all(x in '.0123456789' for x in numeric)
                    exact=Decimal(numeric)*scale*100
                    assert exact>=0 and exact==exact.to_integral_value()
                    amount=int(exact)
                expected.append(dict(source_year=record['year'],source_row=int(row['source_row']),
                    event_id=int(row['EVENT_ID']),episode_id=int(row['EPISODE_ID']),state=row['STATE'],year=int(row['YEAR']),
                    yearmonth=int(row['BEGIN_YEARMONTH']),event_type=row['EVENT_TYPE'],cz_type=row['CZ_TYPE'],wfo=row['WFO'],
                    damage_token=row['DAMAGE_PROPERTY'],damage_cents=amount))
    with (root/'data/reports.csv').open(encoding='utf-8',newline='') as f:
        exported=list(csv.DictReader(f))
    assert len(expected)==len(exported)
    comparisons=0
    for a,b in zip(expected,exported):
        assert set(a)==set(b)
        for key,value in a.items():
            assert b[key]==('' if value is None else str(value)),(key,a['event_id'])
            comparisons+=1
    db=sqlite3.connect(':memory:')
    db.execute('create table reports(event integer primary key,episode integer,state text,year integer,ym integer,type text,cz text,wfo text,amount integer)')
    db.executemany('insert into reports values(?,?,?,?,?,?,?,?,?)',[(r['event_id'],r['episode_id'],r['state'],r['year'],r['yearmonth'],r['event_type'],r['cz_type'],r['wfo'],r['damage_cents']) for r in expected])
    assert db.execute("select count(*) from reports where cz!='C' or year!=ym/100 or ym%100 not between 1 and 12 or episode<=0").fetchone()[0]==0
    query='select state,year,count(*),sum(amount is null),sum(amount=0),sum(amount>0) from reports group by state,year order by state,year'
    grouped=db.execute(query).fetchall()
    with (root/'results/source_coverage.csv').open(encoding='utf-8',newline='') as f:
        coverage=list(csv.DictReader(f))
    assert len(grouped)==len(coverage)==54
    for a,b in zip(grouped,coverage):
        assert list(a)==[b['state'],*[int(b[k]) for k in ['year','reports','missing','explicit_zero','positive']]]
        assert a[2]>=100 and a[5]>=10
    def quantile(values,numerator,denominator):
        sequence=sorted(values);position=Fraction(numerator*(len(sequence)-1),denominator);lower=position.numerator//position.denominator
        value=sequence[lower]+(position-lower)*(sequence[min(lower+1,len(sequence)-1)]-sequence[lower])
        return round(value)
    calibrated=json.loads((root/'results/calibration.json').read_text())
    all_positive=[];positive_counts={}
    for kind in TYPES:
        values=[r[0] for r in db.execute('select amount from reports where year<=2019 and type=? and amount>0',(kind,))]
        assert len(values)>=20
        all_positive.extend(values);positive_counts[kind]=len(values)
        assert calibrated['type_thresholds'][kind]==dict(positive_n=len(values),median_cents=quantile(values,1,2),p90_cents=quantile(values,9,10))
    assert calibrated['pooled_positive_n']==len(all_positive)
    assert calibrated['pooled_p99_cap_cents']==quantile(all_positive,99,100)
    assert calibrated['evaluation_used'] is False and calibrated['years']==list(range(2015,2020))
    with (root/'results/calibration_positives.csv').open(encoding='utf-8',newline='') as f:
        exported_positive=list(csv.DictReader(f))
    earlier=[r for r in expected if r['year']<=2019 and r['damage_cents'] is not None and r['damage_cents']>0]
    assert len(exported_positive)==len(earlier)
    for source,actual in zip(earlier,exported_positive):
        assert all(str(source[k])==actual[k] for k in actual)
    accounting=json.loads((root/'results/source_accounting.json').read_text())
    assert accounting['status']=='PASS_SOURCE_GATE' and not accounting['errors'] and not accounting['coverage_holds']
    assert accounting['calibration_type_positive_counts']==positive_counts
    assert accounting['selected_rows']==len(expected) and accounting['source_cells']==9*len(expected)
    original=json.loads((root/'results/ORIGINAL_EXTRACTION_CHECK.json').read_text())
    assert original['status']=='PASS' and original['checked_original_files']==9
    assert original['manifest_sha256']==accounting['manifest_sha256']==hashlib.sha256((root/'data/source/manifest.json').read_bytes()).hexdigest()
    assert original['selected_original_fields_checked']==9*len(expected)
    report={'status':'PASS','normalized_field_values_checked':comparisons,'sql_state_year_cells':len(grouped),
            'rational_calibration_thresholds_checked':11,'selected_rows':len(expected),
            'scope':'Independent token/cent parser, every normalized field, unique report grain, SQL coverage and exact rational type7 calibration. Original-to-subset certificate bound to manifest; private originals are not reread by public replay.'}
    (root/'results/INDEPENDENT_SOURCE_CHECK.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report))


if __name__=='__main__':verify()
