"""Original vector evidence charts from the reviewed evaluation tables."""
import csv
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
STATES=['ILLINOIS','INDIANA','MICHIGAN','MINNESOTA','OHIO','WISCONSIN']
SCENARIOS=['zero_raw','median_raw','p90_raw','zero_capped','median_capped','p90_capped']
BLUE,GOLD,INK='#205E85','#B86F11','#24333D'
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'axes.labelcolor':INK,'text.color':INK,
                     'axes.spines.top':False,'axes.spines.right':False,'pdf.fonttype':42,'svg.fonttype':'none','savefig.facecolor':'white'})
def table(name):
    with (ROOT/'results/evaluation'/(name+'.csv')).open(encoding='utf-8',newline='') as f:return list(csv.DictReader(f))


def main():
    out=ROOT/'figures';out.mkdir(exist_ok=True);(ROOT/'paper/images').mkdir(parents=True,exist_ok=True)
    bindings={}
    def save(fig,name):
        for suffix in ['svg','png']:fig.savefig(out/(name+'.'+suffix),dpi=180,metadata={'Creator':'Independent storm ranking study'})
        svg=out/(name+'.svg');svg.write_text('\n'.join(v.rstrip() for v in svg.read_text(encoding='utf-8').splitlines())+'\n',encoding='utf-8')
        fig.savefig(ROOT/'paper/images'/(name+'.pdf'),metadata={'Creator':'Independent storm ranking study','CreationDate':None,'ModDate':None})
        plt.close(fig)
    points=table('points');lookup={(r['scenario'],r['state']):r for r in points}
    rank=np.array([[int(lookup[scenario,state]['rank']) for scenario in SCENARIOS] for state in STATES])
    fig,ax=plt.subplots(figsize=(8.3,4.8))
    palette=ListedColormap(['#205E85','#3C789C','#B5CBD9','#C7D8E3','#DDE7EE','#EDF3F8'])
    artist=ax.imshow(rank,cmap=palette,vmin=1,vmax=6,aspect='auto')
    bindings['ranks']=[]
    for b,state in enumerate(STATES):
        for a,scenario in enumerate(SCENARIOS):
            value=int(artist.get_array()[b,a]);bindings['ranks'].append(dict(state=state,scenario=scenario,rank=value))
            ax.text(a,b,str(value),ha='center',va='center',fontsize=12,color='white' if value<=2 else INK)
    ax.set_yticks(range(6),[s.title() for s in STATES])
    ax.set_xticks(range(6),['Zero\nraw','Median\nraw','P90\nraw','Zero\ncapped','Median\ncapped','P90\ncapped'])
    ax.set_title('2020–2023 point ranks across all six accounting scenarios',loc='left',fontsize=12,pad=14)
    ax.set_xlabel('Blank-value assumption and tail treatment; rank 1 = largest mean annual share',labelpad=12)
    fig.subplots_adjust(left=.17,right=.98,top=.86,bottom=.22)
    save(fig,'scenario_ranks')
    intervals=table('intervals');lookup_i={(r['method'],r['state']):r for r in intervals if r['scenario']=='zero_raw'}
    fig,ax=plt.subplots(figsize=(8.1,4.9));bindings['intervals']=[]
    for method,offset,color,marker,label in [('event',-.14,BLUE,'o','Event reports'),('episode',.14,GOLD,'D','NWS episode blocks')]:
        for b,state in enumerate(STATES):
            row=lookup_i[method,state];point=float(lookup['zero_raw',state]['mean_annual_share'])*100
            low,high=float(row['p025'])*100,float(row['p975'])*100
            line=ax.plot([low,high],[b+offset,b+offset],color=color,linewidth=2)[0]
            dot=ax.plot(point,b+offset,marker=marker,markerfacecolor='white' if method=='event' else color,color=color,markersize=6,label=label if b==0 else None)[0]
            bindings['intervals'].append(dict(method=method,state=state,low_percent=float(line.get_xdata()[0]),high_percent=float(line.get_xdata()[1]),point_percent=float(dot.get_xdata()[0])))
    ax.set_yticks(range(6),[s.title() for s in STATES]);ax.invert_yaxis();ax.set_xlim(0,75)
    ax.set_xlabel('Mean annual share within the six-state panel (%)')
    ax.set_title('Conditional 95% resampling intervals: uncapped, blanks as zero',loc='left',fontsize=12,pad=40)
    ax.legend(frameon=False,loc='lower left',bbox_to_anchor=(0,1.01),ncol=2,fontsize=9)
    ax.grid(axis='x',alpha=.15);ax.set_axisbelow(True)
    fig.subplots_adjust(left=.17,right=.98,top=.78,bottom=.16)
    save(fig,'resampling_intervals')
    annual=table('annual');lookup_a={(r['scenario'],r['state'],int(r['year'])):r for r in annual}
    fig,axes=plt.subplots(3,2,figsize=(8.2,7.2),sharex=True,sharey=True);bindings['annual']=[]
    years=[2020,2021,2022,2023]
    for ax,state in zip(axes.flat,STATES):
        for scenario,color,marker,style,label in [('zero_raw',BLUE,'o','-','Uncapped'),('zero_capped',GOLD,'D','--','Capped at calibration P99')]:
            values=[100*float(lookup_a[scenario,state,year]['share']) for year in years]
            line=ax.plot(years,values,color=color,marker=marker,linestyle=style,linewidth=1.5,markersize=4,label=label)[0]
            for year,value in zip(line.get_xdata(),line.get_ydata()):bindings['annual'].append(dict(state=state,scenario=scenario,year=int(year),share_percent=float(value)))
        ax.set_title(state.title(),loc='left',fontsize=11);ax.set_ylim(0,100);ax.set_xticks(years)
        ax.tick_params(labelbottom=True);ax.grid(axis='y',alpha=.15);ax.set_axisbelow(True)
        ax.set_ylabel('Annual share (%)')
    fig.suptitle('Annual recorded-damage shares under the fixed tail stress',x=.04,ha='left',fontsize=12)
    handles,labels=axes.flat[0].get_legend_handles_labels()
    fig.legend(handles,labels,loc='upper center',bbox_to_anchor=(.5,.953),ncol=2,frameon=False,fontsize=9)
    fig.subplots_adjust(left=.10,right=.98,bottom=.07,top=.86,hspace=.45,wspace=.18)
    save(fig,'annual_tail_sensitivity')
    (out/'figure_bindings.json').write_text(json.dumps(bindings,indent=2)+'\n',encoding='utf-8')
    print('Exported three original vector figures with actual artist-coordinate bindings')


if __name__=='__main__':main()
