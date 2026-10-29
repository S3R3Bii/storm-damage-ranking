"""Bind manuscript tables and key claims to independent evidence and reviewed PDF bytes."""
import csv
import hashlib
import json
from pathlib import Path
import subprocess
from pypdf import PdfReader
ROOT=Path(__file__).resolve().parents[1]
STATES=['ILLINOIS','INDIANA','MICHIGAN','MINNESOTA','OHIO','WISCONSIN']


def main():
    text=(ROOT/'paper/main.tex').read_text(encoding='utf-8')
    pdf=PdfReader(ROOT/'paper/manuscript.pdf');assert len(pdf.pages)==8
    pages=[p.extract_text() for p in pdf.pages];assert all(len(p)>200 for p in pages)
    assert 'not peer reviewed' in pages[0] and 'python -m unittest discover -s tests -v' in pages[-1]
    assert 'python src/check_reproduction.py' in pages[-1]
    def table(name):
        with (ROOT/'results/evaluation'/(name+'.csv')).open(encoding='utf-8',newline='') as f:return list(csv.DictReader(f))
    points={(r['scenario'],r['state']):r for r in table('points')}
    envelopes={r['state']:r for r in table('scenario_rank_envelope')}
    intervals={(r['method'],r['state']):r for r in table('intervals') if r['scenario']=='zero_raw'}
    with (ROOT/'results/source_coverage.csv').open(encoding='utf-8',newline='') as f:
        coverage=[r for r in csv.DictReader(f) if int(r['year'])>=2020]
    for state in STATES:
        name=state.title();point=points['zero_raw',state];envelope=envelopes[state]
        expected=name+' & '+f"{100*float(point['mean_annual_share']):.1f}"+' & '+envelope['min_scenario_rank']+'--'+envelope['max_scenario_rank']+' & '+envelope['top_two_scenarios']
        assert expected in text,expected
        counts={k:sum(int(r[k]) for r in coverage if r['state']==state) for k in ['reports','missing','explicit_zero','positive']}
        expected=name+' & '+' & '.join(f'{counts[k]:,}' for k in ['reports','missing','explicit_zero','positive'])
        assert expected in text,expected
        event,episode=intervals['event',state],intervals['episode',state]
        expected=name+' & '+' & '.join(f'{100*float(value):.1f}' for value in [event['width'],episode['width'],episode['top_two_frequency']])
        assert expected in text,expected
        assert float(episode['width'])>float(event['width'])
    calibration=json.loads((ROOT/'results/calibration.json').read_text())
    for kind,values in calibration['type_thresholds'].items():
        expected=kind+' & '+f"{values['positive_n']:,}"+' & '+f"{values['median_cents']/100:,.0f}"+' & '+f"{values['p90_cents']/100:,.0f}"
        assert expected in text,expected
    assert '\\$'+f"{calibration['pooled_p99_cap_cents']/100:,.0f}" in text
    assert calibration['pooled_positive_n']==8307
    for state in ['ILLINOIS','MICHIGAN','MINNESOTA']:
        for scenario in ['zero_raw','p90_capped']:
            assert f"{100*float(points[scenario,state]['mean_annual_share']):.1f}\\%" in text
    for method in ['event','episode']:
        row=intervals[method,'MICHIGAN']
        expected='['+f"{100*float(row['p025']):.1f}"+'\\%, '+f"{100*float(row['p975']):.1f}"+'\\%]'
        assert expected in text,expected
    annual={(r['scenario'],r['state'],int(r['year'])):r for r in table('annual')}
    for scenario in ['zero_raw','zero_capped']:
        assert f"{100*float(annual[scenario,'ILLINOIS',2023]['share']):.1f}\\%" in text
    leave=table('leave_year_out')
    assert next(r['rank'] for r in leave if r['scenario']=='zero_raw' and r['state']=='ILLINOIS' and r['omitted_year']=='2023')=='4'
    assert all(r['rank']=='1' for r in leave if r['scenario']=='zero_raw' and r['state']=='MICHIGAN')
    units=table('unit_manifest');assert sum(int(r['units']) for r in units if r['method']=='episode')==2660
    assert sum(int(r['reports']) for r in coverage)==20289 and sum(int(r['missing']) for r in coverage)==2435
    assert sum(int(r['explicit_zero']) for r in coverage)==12032
    manifest=json.loads((ROOT/'data/source/manifest.json').read_text())
    assert sum(r['original_csv_rows'] for r in manifest['files'])==569666
    assert sum(r['selected_rows'] for r in manifest['files'])==44666
    original=json.loads((ROOT/'results/ORIGINAL_EXTRACTION_CHECK.json').read_text());assert original['selected_original_fields_checked']==401994
    review=json.loads((ROOT/'paper/REVIEW.json').read_text())
    certificates={}
    for name,digest in review['publication_certificate_sha256'].items():
        blob=subprocess.check_output(['git','show','HEAD:'+name],cwd=ROOT)
        assert hashlib.sha256(blob).hexdigest()==digest,name;certificates[name]=json.loads(blob)
    assert certificates['results/development/INDEPENDENT_CHECK.json']['numeric_or_discrete_values_checked']==874218
    assert certificates['results/evaluation/INDEPENDENT_CHECK.json']['numeric_or_discrete_values_checked']==738546
    assert max(c['maximum_float_difference'] for c in certificates.values())<1.7e-16
    replay=json.loads((ROOT/'results/REPLAY_CHECK.json').read_text())
    assert replay['exact_discrete_or_cent_fields_rebuilt']==1855811 and replay['floating_fields_rebuilt']==147422
    scope=json.loads((ROOT/'paper/PUBLICATION_SCOPE.json').read_text())
    assert scope['scope']=='independent-program-study' and scope['formal_submission_target'] is False and len(scope['public_files'])==5
    for name,digest in scope['public_files'].items():assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==digest,name
    freeze=json.loads((ROOT/'results/CODE_FREEZE.json').read_text())
    for name,digest in freeze['sha256'].items():assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==digest,name
    catalog=pdf.trailer['/Root'];assert '/EmbeddedFiles' not in catalog.get('/Names',{}) and '/JavaScript' not in catalog.get('/Names',{})
    action=catalog.get('/OpenAction')
    if isinstance(action,dict):assert action.get('/S')=='/GoTo'
    for page in pdf.pages:
        assert '/AA' not in page
        for annotation in page.get('/Annots',[]):
            item=annotation.get_object();assert item.get('/Subtype')!='/FileAttachment' and '/AA' not in item
            if '/A' in item:assert item['/A'].get('/S') in ['/URI','/GoTo']
    report={'status':'PASS','pages':8,'scope':'All four manuscript tables, scenario/rank/coverage claims, source counts, thresholds, interval widths/endpoints, leave-year findings, unit counts and committed independent diagnostic certificates; exact paper hashes, readable command text and bounded PDF active-content checks.',
            'limitations':'Rendered review is separate; no peer-review, measurement-accuracy, accessibility-conformance or universal security claim.'}
    (ROOT/'results/INDEPENDENT_PAPER_CHECK.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8');print(json.dumps(report))


if __name__=='__main__':main()
