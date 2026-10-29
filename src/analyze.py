"""All declared reporting/tail scenarios and two within-year resampling units."""
import csv
import gzip
import hashlib
import io
import json
import os
from pathlib import Path
os.environ.setdefault('OPENBLAS_NUM_THREADS','1')
import numpy as np
from accounting import SCENARIOS,scenario_values,units,summarize
from config import ROOT,STATES,TYPES,REPLICATES,SEED
from ingest import write_csv


def run(root=ROOT,confirm=False):
    if confirm:
        freeze=json.loads((root/'results/CODE_FREEZE.json').read_text())
        assert freeze['status']=='FROZEN_BEFORE_EVALUATION_OUTCOMES'
        for name,digest in freeze['sha256'].items():
            assert hashlib.sha256((root/name).read_bytes()).hexdigest()==digest,name
    years=list(range(2020,2024)) if confirm else list(range(2015,2020))
    out=root/'results'/('evaluation' if confirm else 'development');out.mkdir(exist_ok=True)
    calibration=json.loads((root/'results/calibration.json').read_text())
    with (root/'data/reports.csv').open(encoding='utf-8',newline='') as f:
        reports=[r for r in csv.DictReader(f) if int(r['year']) in years]
    by_year={year:[r for r in reports if int(r['year'])==year] for year in years}
    matrices={}
    unit_manifest=[];totals=[];annual_rows=[];unit_rows=[]
    for method in ['event','episode']:
        matrices[method]=[]
        for year in years:
            identifiers,matrix=units(by_year[year],calibration,method)
            matrices[method].append(matrix)
            unit_manifest.append({'method':method,'year':year,'units':len(identifiers),'seed':SEED+100*int(method=='episode')+year})
            for identity,vector in zip(identifiers,matrix):
                for j,scenario in enumerate(SCENARIOS):
                    for k,state in enumerate(STATES):
                        if vector.reshape(6,6)[j,k]!=0:
                            unit_rows.append({'method':method,'year':year,'unit_id':identity,'scenario':scenario,'state':state,'cents':int(vector.reshape(6,6)[j,k])})
    for j,year in enumerate(years):
        total=matrices['event'][j].sum(axis=0)
        assert np.array_equal(total,matrices['episode'][j].sum(axis=0))
        totals.append(total)
        scores,ranks,ties=summarize([total])
        for a,scenario in enumerate(SCENARIOS):
            for b,state in enumerate(STATES):
                annual_rows.append({'year':year,'scenario':scenario,'state':state,'cents':int(total.reshape(6,6)[a,b]),
                                    'share':scores[a,b],'rank':int(ranks[a,b]),'exact_tie':int(ties[a,b])})
    scores,ranks,ties=summarize(totals)
    points=[];contrasts=[];leave_year=[];state_type=[]
    for a,scenario in enumerate(SCENARIOS):
        for b,state in enumerate(STATES):
            points.append({'scenario':scenario,'state':state,'mean_annual_share':scores[a,b],'rank':int(ranks[a,b]),'top_two':int(ranks[a,b]<=2),
                           'exact_tie':int(ties[a,b]),'cumulative_nominal_cents':sum(int(t.reshape(6,6)[a,b]) for t in totals)})
        for b in range(6):
            for c in range(b+1,6):
                contrasts.append({'scenario':scenario,'state_a':STATES[b],'state_b':STATES[c],'share_difference':scores[a,b]-scores[a,c]})
    for omitted in years:
        s,r,t=summarize([total for year,total in zip(years,totals) if year!=omitted])
        for a,scenario in enumerate(SCENARIOS):
            for b,state in enumerate(STATES):
                leave_year.append({'omitted_year':omitted,'scenario':scenario,'state':state,'mean_annual_share':s[a,b],'rank':int(r[a,b]),'exact_tie':int(t[a,b])})
    for year in years:
        for state in STATES:
            for kind in TYPES:
                chosen=[r for r in by_year[year] if r['state']==state and r['event_type']==kind]
                values=[int(r['damage_cents']) for r in chosen if r['damage_cents']!='']
                state_type.append({'year':year,'state':state,'event_type':kind,'reports':len(chosen),
                                   'missing':len(chosen)-len(values),'explicit_zero':sum(v==0 for v in values),
                                   'positive':sum(v>0 for v in values),'known_cents':sum(values)})
    bootstrap=[];intervals=[];frequency=[];paired=[]
    yearly_draws=[]
    for method in ['event','episode']:
        sampled=np.zeros((REPLICATES,len(years),36),dtype=np.int64)
        for j,year in enumerate(years):
            matrix=matrices[method][j];n=len(matrix)
            generator=np.random.Generator(np.random.PCG64(SEED+100*int(method=='episode')+year))
            for draw in range(REPLICATES):
                indexes=generator.integers(0,n,size=n)
                counts=np.bincount(indexes,minlength=n)
                sampled[draw,j]=counts@matrix
                yearly_draws.append({'method':method,'year':year,'replicate':draw,
                                     **{f'c{i}':int(v) for i,v in enumerate(sampled[draw,j])}})
        all_scores=np.zeros((REPLICATES,6,6));all_ranks=np.zeros((REPLICATES,6,6),dtype=int)
        for draw in range(REPLICATES):
            s,r,t=summarize(sampled[draw]);all_scores[draw]=s;all_ranks[draw]=r
            for a,scenario in enumerate(SCENARIOS):
                for b,state in enumerate(STATES):
                    bootstrap.append({'method':method,'replicate':draw,'scenario':scenario,'state':state,
                                      'mean_annual_share':s[a,b],'rank':int(r[a,b]),'exact_tie':int(t[a,b])})
        for a,scenario in enumerate(SCENARIOS):
            for b,state in enumerate(STATES):
                low,high=np.quantile(all_scores[:,a,b],[.025,.975],method='linear')
                intervals.append({'method':method,'scenario':scenario,'state':state,'p025':low,'p975':high,'width':high-low,
                                  'top_two_frequency':float(np.mean(all_ranks[:,a,b]<=2))})
                for rank in range(1,7):
                    frequency.append({'method':method,'scenario':scenario,'state':state,'rank':rank,'count':int(np.sum(all_ranks[:,a,b]==rank)),
                                      'frequency':float(np.mean(all_ranks[:,a,b]==rank))})
            for b in range(6):
                for c in range(b+1,6):
                    delta=all_scores[:,a,b]-all_scores[:,a,c];low,high=np.quantile(delta,[.025,.975],method='linear')
                    paired.append({'method':method,'scenario':scenario,'state_a':STATES[b],'state_b':STATES[c],
                                   'p025_difference':low,'p975_difference':high,'positive_frequency':float(np.mean(delta>0))})
        print(json.dumps({'phase':out.name,'unit':method,'replicates':REPLICATES,'year_strata':len(years)}),flush=True)
    envelopes=[{'state':state,'min_scenario_rank':int(ranks[:,b].min()),'max_scenario_rank':int(ranks[:,b].max()),
                'top_two_scenarios':int(np.sum(ranks[:,b]<=2))} for b,state in enumerate(STATES)]
    for name,rows in [('annual',annual_rows),('points',points),('scenario_rank_envelope',envelopes),('pairwise',contrasts),('leave_year_out',leave_year),
                       ('state_year_type',state_type),('unit_manifest',unit_manifest),('intervals',intervals),('rank_frequencies',frequency),('paired_intervals',paired)]:
        write_csv(out/(name+'.csv'),rows)
    for name,rows in [('unit_vectors',unit_rows),('bootstrap',bootstrap),('bootstrap_year_totals',yearly_draws)]:
        text=io.StringIO(newline='');writer=csv.DictWriter(text,list(rows[0]),lineterminator='\n');writer.writeheader();writer.writerows(rows)
        with (out/(name+'.csv.gz')).open('wb') as raw,gzip.GzipFile(filename='',mode='wb',fileobj=raw,mtime=0) as f:
            f.write(text.getvalue().encode('utf-8'))
    summary={'status':'COMPUTED_PENDING_INDEPENDENT_CHECKS','years':years,'reports':len(reports),'scenarios':SCENARIOS,
             'replicates_per_unit':REPLICATES,'unit_methods':['event','episode'],'evaluation_used':confirm,
             'bootstrap_rows':len(bootstrap),'source_note':'Conditional empirical reporting/tail/resampling scenarios; no identified true-loss bound or prospective risk claim.'}
    (out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n',encoding='utf-8');print(json.dumps(summary))


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('--confirm',action='store_true')
    run(confirm=parser.parse_args().confirm)
