"""Isolated minimized-snapshot replay, with all CSV values checked against this edition."""
import csv
import gzip
import hashlib
import json
import math
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
ROOT=Path(__file__).resolve().parents[1]


def main():
    count=0;exact=0
    with tempfile.TemporaryDirectory(prefix='storm-ranking-replay-') as directory:
        replay=Path(directory)
        for folder in ['src','tests','data/source']:
            shutil.copytree(ROOT/folder,replay/folder,ignore=shutil.ignore_patterns('__pycache__'))
        shutil.copy2(ROOT/'PROTOCOL.md',replay/'PROTOCOL.md')
        (replay/'results').mkdir()
        for name in ['CODE_FREEZE.json','ORIGINAL_EXTRACTION_CHECK.json']:
            shutil.copy2(ROOT/'results'/name,replay/'results'/name)
        commands=[('ingest.py',[]),('calibrate.py',[]),('verify_source.py',[]),('analyze.py',[]),('verify_analysis.py',[]),
                  ('analyze.py',['--confirm']),('verify_analysis.py',['--confirm'])]
        for script,args in commands:
            process=subprocess.run([sys.executable,str(replay/'src'/script),*args],cwd=replay,capture_output=True,text=True)
            if process.returncode:raise AssertionError(script+'\n'+process.stdout+process.stderr)
        paths=[Path('data/reports.csv'),Path('results/source_coverage.csv'),Path('results/calibration_positives.csv')]
        for phase in ['development','evaluation']:
            paths.extend(p.relative_to(ROOT) for p in sorted((ROOT/'results'/phase).glob('*.csv*')))
        discrete={'source_year','source_row','event_id','episode_id','year','yearmonth','damage_cents','reports','missing','explicit_zero','positive',
                  'positive_n','cumulative_nominal_cents','known_cents','cents','rank','top_two','exact_tie','replicate','units','seed','unit_id',
                  'omitted_year','count','min_scenario_rank','max_scenario_rank','top_two_scenarios'}
        for relative in paths:
            opener=gzip.open if relative.suffix=='.gz' else open
            with opener(ROOT/relative,'rt',encoding='utf-8',newline='') as f:retained=list(csv.DictReader(f))
            with opener(replay/relative,'rt',encoding='utf-8',newline='') as f:rebuilt=list(csv.DictReader(f))
            assert len(retained)==len(rebuilt),relative
            for a,b in zip(retained,rebuilt):
                assert set(a)==set(b)
                for key in a:
                    if key in discrete or (key.startswith('c') and key[1:].isdigit()):
                        assert a[key]==b[key],(relative,key);exact+=1
                    else:
                        try:left,right=float(a[key]),float(b[key])
                        except ValueError:assert a[key]==b[key],(relative,key)
                        else:
                            assert math.isfinite(left) and math.isfinite(right) and math.isclose(left,right,abs_tol=1e-7,rel_tol=1e-9),(relative,key)
                            count+=1
        for name in ['source_accounting.json','calibration.json']:
            assert json.loads((ROOT/'results'/name).read_text())==json.loads((replay/'results'/name).read_text())
        for phase in ['development','evaluation']:
            assert json.loads((replay/'results'/phase/'INDEPENDENT_CHECK.json').read_text())['status']=='PASS'
    frozen=json.loads((ROOT/'results/CODE_FREEZE.json').read_text())
    for name,digest in frozen['sha256'].items():assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==digest,name
    report={'status':'PASS','exact_discrete_or_cent_fields_rebuilt':exact,'floating_fields_rebuilt':count,
            'absolute_tolerance':1e-7,'relative_tolerance':1e-9,
            'scope':'Every minimized-source cell, calibration and source gate, scenario, unit vector, bootstrap annual cent total, score, rank and summary freshly rebuilt in isolation. Independent SQL/rational/indexed-row checks rerun. Excluded private originals and PDF rendering are not part of this public replay.'}
    (ROOT/'results/REPLAY_CHECK.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8');print(json.dumps(report))


if __name__=='__main__':main()
