"""Fixed scenario conventions use earlier-period known positives only."""
import csv
import hashlib
import json
from config import ROOT,TYPES
from ingest import quantile_cents,write_csv


def calibrate(root=ROOT):
    assert json.loads((root/'results/source_accounting.json').read_text())['status']=='PASS_SOURCE_GATE'
    with (root/'data/reports.csv').open(encoding='utf-8',newline='') as f:
        selected=[r for r in csv.DictReader(f) if int(r['year'])<=2019 and r['damage_cents'] and int(r['damage_cents'])>0]
    values={t:[int(r['damage_cents']) for r in selected if r['event_type']==t] for t in TYPES}
    assert all(len(v)>=20 for v in values.values())
    thresholds={t:{'positive_n':len(v),'median_cents':quantile_cents(v,.5),'p90_cents':quantile_cents(v,.9)} for t,v in values.items()}
    report={'status':'CALIBRATED_PENDING_CODE_FREEZE','years':[2015,2016,2017,2018,2019],
            'type_thresholds':thresholds,'pooled_positive_n':len(selected),
            'pooled_p99_cap_cents':quantile_cents([int(r['damage_cents']) for r in selected],.99),
            'convention':'Type7linear quantile, nearestcent ties-to-even; fixed sensitivity conventions, no optimization or fitted missingness model',
            'source_report_sha256':hashlib.sha256((root/'data/reports.csv').read_bytes()).hexdigest(),
            'evaluation_used':False}
    write_csv(root/'results/calibration_positives.csv',[{k:r[k] for k in ['source_year','source_row','event_id','state','year','event_type','damage_cents']} for r in selected])
    (root/'results/calibration.json').write_bytes((json.dumps(report,indent=2)+'\n').encode('utf-8'))
    print(json.dumps(report))


if __name__=='__main__':calibrate()
