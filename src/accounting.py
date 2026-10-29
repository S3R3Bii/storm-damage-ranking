"""Integer-cent scenario vectors and exact fraction ranks; no selection from outcomes."""
from fractions import Fraction
import numpy as np
from config import STATES

SCENARIOS=['zero_raw','median_raw','p90_raw','zero_capped','median_capped','p90_capped']


def scenario_values(known,event_type,calibration):
    thresholds=calibration['type_thresholds'][event_type]
    raw=[known if known is not None else fill for fill in
         [0,thresholds['median_cents'],thresholds['p90_cents']]]
    cap=calibration['pooled_p99_cap_cents']
    return raw+[min(value,cap) for value in raw]


def units(reports,calibration,method):
    if method not in ['event','episode']:raise ValueError('Unknown resampling unit')
    reports=sorted(reports,key=lambda r:(int(r['source_row']),int(r['event_id'])))
    event=np.zeros((len(reports),6,6),dtype=np.int64)
    for i,r in enumerate(reports):
        known=int(r['damage_cents']) if r['damage_cents']!='' else None
        event[i,:,STATES.index(r['state'])]=scenario_values(known,r['event_type'],calibration)
    if method=='event':
        identifiers=[int(r['event_id']) for r in reports];matrix=event
    else:
        identifiers=sorted({int(r['episode_id']) for r in reports})
        positions={key:i for i,key in enumerate(identifiers)}
        matrix=np.zeros((len(identifiers),6,6),dtype=np.int64)
        np.add.at(matrix,[positions[int(r['episode_id'])] for r in reports],event)
    # This conservative bound covers every possible n-unit resample.
    assert matrix.size and int(matrix.max())*len(matrix)<=np.iinfo(np.int64).max
    return identifiers,matrix.reshape(len(matrix),36)


def summarize(annual_totals):
    """Equal-year shares; rank on rational values to preserve exact ties."""
    if not len(annual_totals):raise ValueError('At least one annual stratum is required')
    scores=np.zeros((6,6));ranks=np.zeros((6,6),dtype=int);ties=np.zeros((6,6),dtype=int)
    for scenario in range(6):
        shares=[Fraction(0) for _ in STATES]
        for annual in annual_totals:
            numerator=[int(v) for v in annual.reshape(6,6)[scenario]]
            denominator=sum(numerator)
            if denominator<=0:raise ValueError('Undefined zero-denominator stratum; retain failure')
            shares=[old+Fraction(value,denominator)/len(annual_totals) for old,value in zip(shares,numerator)]
        order=sorted(range(6),key=lambda i:(-shares[i],STATES[i]))
        for rank,i in enumerate(order,1):
            scores[scenario,i]=float(shares[i]);ranks[scenario,i]=rank
            ties[scenario,i]=int(sum(v==shares[i] for v in shares)>1)
    return scores,ranks,ties
