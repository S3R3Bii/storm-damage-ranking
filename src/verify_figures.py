import csv
import json
import math
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def table(name):
    with (ROOT/'results/evaluation'/(name+'.csv')).open(encoding='utf-8',newline='') as f:return list(csv.DictReader(f))
bindings=json.loads((ROOT/'figures/figure_bindings.json').read_text())
points={(r['scenario'],r['state']):r for r in table('points')}
intervals={(r['method'],r['state']):r for r in table('intervals') if r['scenario']=='zero_raw'}
annual={(r['scenario'],r['state'],int(r['year'])):r for r in table('annual')}
count=0
def close(a,b):
    global count
    assert math.isclose(float(a),float(b),abs_tol=1e-7,rel_tol=1e-9),(a,b)
    count+=1
assert len(bindings['ranks'])==36 and len(bindings['intervals'])==12 and len(bindings['annual'])==48
assert len({(r['state'],r['scenario']) for r in bindings['ranks']})==36
for r in bindings['ranks']:
    assert r['rank']==int(points[r['scenario'],r['state']]['rank']);count+=1
for r in bindings['intervals']:
    source=intervals[r['method'],r['state']]
    close(r['low_percent'],100*float(source['p025']));close(r['high_percent'],100*float(source['p975']))
    close(r['point_percent'],100*float(points['zero_raw',r['state']]['mean_annual_share']))
for r in bindings['annual']:close(r['share_percent'],100*float(annual[r['scenario'],r['state'],r['year']]['share']))
for name,text in [('scenario_ranks','2020'),('resampling_intervals','95%'),('annual_tail_sensitivity','Annual')]:
    svg=(ROOT/'figures'/(name+'.svg')).read_text(encoding='utf-8');assert '<svg' in svg and text in svg
report={'status':'PASS','plotted_values_checked':count,'scope':'Actual plotted matrix ranks, interval endpoints/points and annual line values against every reviewed figure-source row; SVG labels. Rendered review is separate.'}
(ROOT/'results/FIGURE_CHECK.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8');print(json.dumps(report))
