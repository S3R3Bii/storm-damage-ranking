"""Independent SQL cent vectors, rational ranks and indexed-row bootstrap reconstruction."""
import csv
from fractions import Fraction
import gzip
import json
import math
import os
from pathlib import Path
import sqlite3
os.environ.setdefault('OPENBLAS_NUM_THREADS','1')
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
STATES=['ILLINOIS','INDIANA','MICHIGAN','MINNESOTA','OHIO','WISCONSIN']
TYPES=['Flash Flood','Flood','Hail','Thunderstorm Wind','Tornado']
SCENARIOS=['zero_raw','median_raw','p90_raw','zero_capped','median_capped','p90_capped']


def verify(root=ROOT,confirm=False):
    years=list(range(2020,2024)) if confirm else list(range(2015,2020))
    out=root/'results'/('evaluation' if confirm else 'development')
    def table(name):
        path=out/(name+'.csv')
        opener=gzip.open if not path.exists() else open
        if not path.exists():path=out/(name+'.csv.gz')
        with opener(path,'rt',encoding='utf-8',newline='') as f:return list(csv.DictReader(f))
    with (root/'data/reports.csv').open(encoding='utf-8',newline='') as f:
        reports=[r for r in csv.DictReader(f) if int(r['year']) in years]
    calibration=json.loads((root/'results/calibration.json').read_text())
    db=sqlite3.connect(':memory:')
    db.execute('create table source(year integer,event integer,episode integer,rownum integer,state text,type text,known integer)')
    db.execute('create table loss(year integer,event integer,episode integer,state text,scenario integer,cents integer)')
    source=[];loss=[]
    for r in reports:
        known=int(r['damage_cents']) if r['damage_cents'] else None
        year,event,episode=int(r['year']),int(r['event_id']),int(r['episode_id'])
        source.append((year,event,episode,int(r['source_row']),r['state'],r['event_type'],known))
        threshold=calibration['type_thresholds'][r['event_type']]
        base=[known if known is not None else substitute for substitute in [0,threshold['median_cents'],threshold['p90_cents']]]
        amounts=base+[min(v,calibration['pooled_p99_cap_cents']) for v in base]
        loss.extend((year,event,episode,r['state'],scenario,value) for scenario,value in enumerate(amounts))
    db.executemany('insert into source values(?,?,?,?,?,?,?)',source)
    db.executemany('insert into loss values(?,?,?,?,?,?)',loss)
    count=0;maximum=0.0;tables={}
    def compare(name,expected,actual=None):
        nonlocal count,maximum
        given=table(name) if actual is None else actual
        assert len(given)==len(expected),(name,len(given),len(expected))
        for want,have in zip(expected,given):
            assert set(want)==set(have),(name,set(want),set(have))
            for key,value in want.items():
                if isinstance(value,str):assert value==have[key],(name,key)
                elif isinstance(value,(int,np.integer)):
                    assert str(int(value))==have[key],(name,key,value,have[key])
                    count+=1
                else:
                    delta=abs(float(value)-float(have[key]));maximum=max(maximum,delta)
                    assert math.isclose(float(value),float(have[key]),rel_tol=1e-9,abs_tol=1e-7),(name,key,value,have[key])
                    count+=1
        tables[name]=len(expected)
    def fractions(annual):
        result=[];rank=[];tie=[]
        for scenario in range(6):
            state_shares=[]
            for state in range(6):
                value=sum((Fraction(int(a[scenario,state]),sum(int(v) for v in a[scenario])) for a in annual),Fraction(0))/len(annual)
                state_shares.append(value)
            ordered=sorted(range(6),key=lambda i:(-state_shares[i],STATES[i]))
            rank.append([ordered.index(i)+1 for i in range(6)])
            tie.append([int(state_shares.count(value)>1) for value in state_shares])
            result.append(state_shares)
        return result,rank,tie
    matrices={};unit_rows=[];manifest=[]
    for method,field in [('event','event'),('episode','episode')]:
        matrices[method]=[]
        for year in years:
            query='select event from source where year=? order by rownum,event' if method=='event' else 'select distinct episode from source where year=? order by episode'
            ids=[r[0] for r in db.execute(query,(year,))]
            positions={identity:i for i,identity in enumerate(ids)}
            matrix=np.zeros((len(ids),6,6),dtype=np.int64)
            query=f'select {field},scenario,state,sum(cents) from loss where year=? group by {field},scenario,state'
            for identity,scenario,state,value in db.execute(query,(year,)):
                matrix[positions[identity],scenario,STATES.index(state)]=value
            assert int(matrix.max())*len(matrix)<=2**63-1
            matrices[method].append(matrix)
            manifest.append(dict(method=method,year=year,units=len(ids),seed=20261029+100*int(method=='episode')+year))
            for identity,vector in zip(ids,matrix):
                for a,scenario in enumerate(SCENARIOS):
                    for b,state in enumerate(STATES):
                        if vector[a,b]:unit_rows.append(dict(method=method,year=year,unit_id=identity,scenario=scenario,state=state,cents=int(vector[a,b])))
    compare('unit_manifest',manifest);compare('unit_vectors',unit_rows)
    totals=[]
    for year in years:
        matrix=np.zeros((6,6),dtype=np.int64)
        for scenario,state,value in db.execute('select scenario,state,sum(cents) from loss where year=? group by scenario,state',(year,)):
            matrix[scenario,STATES.index(state)]=value
        totals.append(matrix)
    annual=[]
    for year,total in zip(years,totals):
        shares,ranks,ties=fractions([total])
        for a,scenario in enumerate(SCENARIOS):
            for b,state in enumerate(STATES):
                annual.append(dict(year=year,scenario=scenario,state=state,cents=int(total[a,b]),share=float(shares[a][b]),rank=ranks[a][b],exact_tie=ties[a][b]))
    compare('annual',annual)
    shares,ranks,ties=fractions(totals)
    points=[];pairwise=[]
    for a,scenario in enumerate(SCENARIOS):
        for b,state in enumerate(STATES):
            points.append(dict(scenario=scenario,state=state,mean_annual_share=float(shares[a][b]),rank=ranks[a][b],top_two=int(ranks[a][b]<=2),
                               exact_tie=ties[a][b],cumulative_nominal_cents=sum(int(v[a,b]) for v in totals)))
        for b in range(6):
            for c in range(b+1,6):pairwise.append(dict(scenario=scenario,state_a=STATES[b],state_b=STATES[c],share_difference=float(shares[a][b]-shares[a][c])))
    compare('points',points);compare('pairwise',pairwise)
    compare('scenario_rank_envelope',[dict(state=state,min_scenario_rank=min(v[b] for v in ranks),max_scenario_rank=max(v[b] for v in ranks),
                                          top_two_scenarios=sum(v[b]<=2 for v in ranks)) for b,state in enumerate(STATES)])
    leave=[]
    for omitted in years:
        s,r,t=fractions([v for year,v in zip(years,totals) if year!=omitted])
        for a,scenario in enumerate(SCENARIOS):
            for b,state in enumerate(STATES):leave.append(dict(omitted_year=omitted,scenario=scenario,state=state,mean_annual_share=float(s[a][b]),rank=r[a][b],exact_tie=t[a][b]))
    compare('leave_year_out',leave)
    state_type=[]
    for year in years:
        for state in STATES:
            for kind in TYPES:
                n,missing,zero,positive,total=db.execute('select count(*),sum(known is null),sum(known=0),sum(known>0),sum(known) from source where year=? and state=? and type=?',(year,state,kind)).fetchone()
                state_type.append(dict(year=year,state=state,event_type=kind,reports=n,missing=missing or 0,explicit_zero=zero or 0,positive=positive or 0,known_cents=total or 0))
    compare('state_year_type',state_type)
    saved_totals={(r['method'],int(r['year']),int(r['replicate'])):r for r in table('bootstrap_year_totals')}
    assert len(saved_totals)==2*len(years)*1000
    saved_bootstrap=table('bootstrap');expected_bootstrap=[];intervals=[];frequencies=[];paired=[]
    def percentile(values,num,den):
        sequence=sorted(values);position=Fraction(num*(len(sequence)-1),den);low=position.numerator//position.denominator
        return float(sequence[low]+float(position-low)*(sequence[min(low+1,len(sequence)-1)]-sequence[low]))
    for method in ['event','episode']:
        generated=np.zeros((1000,len(years),6,6),dtype=np.int64)
        for j,year in enumerate(years):
            matrix=matrices[method][j];n=len(matrix)
            generator=np.random.Generator(np.random.PCG64(20261029+100*int(method=='episode')+year))
            for draw in range(1000):
                # Primary uses bincount @ matrix; this path adds indexed rows.
                indexes=generator.integers(low=0,high=n,size=n)
                generated[draw,j]=np.sum(matrix[indexes],axis=0,dtype=np.int64)
                given=saved_totals[method,year,draw]
                assert all(int(given['c'+str(i)])==int(value) for i,value in enumerate(generated[draw,j].reshape(36)))
                count+=36
        score_draws=np.zeros((1000,6,6));rank_draws=np.zeros((1000,6,6),dtype=int)
        for draw in range(1000):
            s,r,t=fractions(generated[draw]);score_draws[draw]=[[float(v) for v in row] for row in s];rank_draws[draw]=r
            for a,scenario in enumerate(SCENARIOS):
                for b,state in enumerate(STATES):expected_bootstrap.append(dict(method=method,replicate=draw,scenario=scenario,state=state,mean_annual_share=float(s[a][b]),rank=r[a][b],exact_tie=t[a][b]))
        for a,scenario in enumerate(SCENARIOS):
            for b,state in enumerate(STATES):
                values=list(score_draws[:,a,b]);low,high=percentile(values,1,40),percentile(values,39,40)
                intervals.append(dict(method=method,scenario=scenario,state=state,p025=low,p975=high,width=high-low,
                                      top_two_frequency=sum(int(v)<=2 for v in rank_draws[:,a,b])/1000))
                for rank in range(1,7):
                    n=sum(int(v)==rank for v in rank_draws[:,a,b])
                    frequencies.append(dict(method=method,scenario=scenario,state=state,rank=rank,count=n,frequency=n/1000))
            for b in range(6):
                for c in range(b+1,6):
                    delta=list(score_draws[:,a,b]-score_draws[:,a,c])
                    paired.append(dict(method=method,scenario=scenario,state_a=STATES[b],state_b=STATES[c],
                                       p025_difference=percentile(delta,1,40),p975_difference=percentile(delta,39,40),positive_frequency=sum(v>0 for v in delta)/1000))
        print(json.dumps({'phase':out.name,'unit':method,'all_draws_reconstructed':1000}),flush=True)
    compare('bootstrap',expected_bootstrap,saved_bootstrap);compare('intervals',intervals);compare('rank_frequencies',frequencies);compare('paired_intervals',paired)
    summary=json.loads((out/'summary.json').read_text())
    assert summary['years']==years and summary['reports']==len(reports) and summary['scenarios']==SCENARIOS
    assert summary['evaluation_used']==confirm and summary['bootstrap_rows']==72000 and summary['replicates_per_unit']==1000
    report={'status':'PASS','numeric_or_discrete_values_checked':count,'maximum_float_difference':maximum,'absolute_tolerance':1e-7,'relative_tolerance':1e-9,
            'integer_cents_and_discrete_ranks':'Exact equality required','tables':tables,
            'scope':'Independent SQL unit/annual accounting, rational point/leave-year ranks, every regenerated bootstrap annual cent total, score, rank, interval, frequency and paired contrast. No primary helper imported.',
            'rng_limit':'Both implementations use documented NumPy PCG64 streams. Indexed-row addition independently checks primary count-weighted aggregation; this is not independent RNG-library certification.'}
    (out/'INDEPENDENT_CHECK.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8');print(json.dumps(report))


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('--confirm',action='store_true')
    verify(confirm=parser.parse_args().confirm)
