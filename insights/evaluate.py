"""Reproducible chronological study. Run from repo root: python -m insights.evaluate."""
import argparse
import hashlib
import json
from pathlib import Path
import platform
import numpy as np
import pandas as pd
import sklearn
from sklearn.covariance import LedoitWolf
import stock_insights as calc
import insights_service as service

ROOT=Path(__file__).resolve().parent
MARKETS={'India':(['TCS.NS','INFY.NS','SBIN.NS'],'^NSEI'), 'US':(['AAPL','MSFT','NVDA'],'^GSPC')}
CONFIG={'version':calc.VERSION,'parameters':calc.PARAMETERS,'seed':42,'evaluation_fraction':.2,
        'portfolio_training':'expanding prior observations; minimum 120', 'portfolio_future_sessions':21,
        'portfolio_origin_step':21,'portfolio_weights':{'before':[.5,.5,0],'after':[1/3,1/3,1/3]},
        'movement_evaluation_step':21,'injected_return_deviation':.08,
        'universe_policy':'Fixed six-symbol universe from the approved plan; not selected by outcomes.'}


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--download',action='store_true');args=parser.parse_args()
    data_dir=ROOT/'data';out=ROOT/'artifacts';out.mkdir(exist_ok=True);data_dir.mkdir(exist_ok=True)
    (out/'configuration.json').write_text(json.dumps(CONFIG,indent=2)+'\n') # freeze before evaluation
    frames={};coverage={}; failures=[]
    for symbols,benchmark in MARKETS.values():
        for s in symbols+[benchmark]:
            stem=s.replace('^','INDEX_');csv=data_dir/(stem+'.csv');meta_file=data_dir/(stem+'.json')
            try:
                if args.download or not csv.exists():
                    f,m=service.history(s);f.to_csv(csv);meta_file.write_text(json.dumps(m,indent=2))
                f=pd.read_csv(csv,index_col=0,parse_dates=True)
                frames[s]=f;coverage[s]=json.loads(meta_file.read_text())
                coverage[s]['snapshot_sha256']=hashlib.sha256(csv.read_bytes()).hexdigest()
            except Exception as e:
                failures.append({'symbol':s,'error':type(e).__name__});print('Unavailable',s,flush=True)
    vol_rows=[];move_rows=[];event_rows=[]
    for market,(symbols,benchmark) in MARKETS.items():
        if not all(s in frames for s in symbols):continue
        r=pd.concat({s:calc.returns(frames[s]) for s in symbols},axis=1).dropna()
        first=max(120,int(len(r)*.8));cutoff=r.index[first]
        for pos in range(first,len(r)-20,21):
            train=r.iloc[:pos].to_numpy();future=r.iloc[pos:pos+21].to_numpy()
            covs={'ledoit_wolf':LedoitWolf().fit(train).covariance_, 'sample':np.cov(train,rowvar=False,ddof=1)}
            for portfolio_name, weights in CONFIG['portfolio_weights'].items():
                w=np.asarray(weights);realized=float(np.std(future@w,ddof=1)*np.sqrt(252))
                for method,cov in covs.items():
                    predicted=float(np.sqrt(max(0,w@cov@w)*252))
                    vol_rows.append(dict(market=market,portfolio=portfolio_name,origin=str(r.index[pos].date()),
                                         training_end=str(r.index[pos-1].date()),training_count=len(train),
                                         future_end=str(r.index[pos+20].date()),method=method,estimate=predicted,
                                         realized=realized,absolute_error=abs(predicted-realized)))
        if benchmark not in frames:continue
        for s in symbols:
            f=frames[s];b=frames[benchmark]
            aligned=pd.concat([calc.returns(f).rename('s'),calc.returns(b).rename('b')],axis=1).dropna()
            for date in aligned.index[aligned.index>=cutoff][::21]:
                current=f.loc[:date].copy();bm=b.loc[:date].copy()
                normal=calc.movement(current,bm)
                event_rows.append(dict(market=market,symbol=s,date=str(date.date()),stock_return=normal.get('stock_return'),
                                       market_return=normal.get('benchmark_return'),adjusted_score=normal.get('robust_score'),
                                       raw_score=normal.get('raw_robust_score'),adjusted_alert=normal.get('unusual'),
                                       annotation='NOT REVIEWED',news_cause='Not inferred'))
                prior=aligned.loc[aligned.index<date].tail(120)
                coef=np.linalg.lstsq(np.column_stack([np.ones(len(prior)),prior.b]),prior.s,rcond=None)[0]
                # Controlled interventions on the final observed return only; not historical events.
                for scenario in ['normal','broad_market_shock','stock_specific_shock','missing_stock_price']:
                    sf=current.copy();bf=bm.copy()
                    if scenario=='broad_market_shock':
                        bf.loc[date,'Close']=bf.Close.iloc[-2]*(1+aligned.loc[date,'b']-.08)
                        sf.loc[date,'Close']=sf.Close.iloc[-2]*(1+aligned.loc[date,'s']-coef[1]*.08)
                    elif scenario=='stock_specific_shock':
                        sf.loc[date,'Close']=sf.Close.iloc[-2]*(1+aligned.loc[date,'s']+.08)
                    elif scenario=='missing_stock_price':sf.loc[date,'Close']=np.nan
                    d=calc.movement(sf,bf)
                    raw=d.get('raw_robust_score');adjusted=d.get('robust_score')
                    move_rows.append(dict(market=market,symbol=s,date=str(date.date()),scenario=scenario,status=d['status'],
                                          raw_alert=abs(raw)>3.5 if raw is not None else None,
                                          adjusted_alert=abs(adjusted)>3.5 if adjusted is not None else None))
        print('Evaluated',market,flush=True)
    vol=pd.DataFrame(vol_rows);moves=pd.DataFrame(move_rows);events=pd.DataFrame(event_rows)
    vol.to_csv(out/'volatility_predictions.csv',index=False);moves.to_csv(out/'movement_interventions.csv',index=False)
    events.to_csv(out/'real_alert_review.csv',index=False)
    summary={'config':CONFIG,'environment':{'python':platform.python_version(),'numpy':np.__version__,'pandas':pd.__version__,'sklearn':sklearn.__version__,'yfinance':service.yf.__version__,'market_calendars':service.calendars.__version__},
             'source_hashes':{str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in [Path('stock_insights.py'),Path('insights_service.py'),ROOT/'evaluate.py']},
             'coverage':coverage,'failures':failures,'portfolio':[],'movement':[]}
    if len(vol):
        for keys,g in vol.groupby(['market','portfolio','method']):
            summary['portfolio'].append(dict(market=keys[0],portfolio=keys[1],method=keys[2],origins=len(g),
                                             mae_annualized_volatility=float(g.absolute_error.mean())))
    if len(moves):
        for keys,g in moves.groupby(['market','scenario']):
            summary['movement'].append(dict(market=keys[0],scenario=keys[1],cases=len(g),
                                            raw_assessable=int(g.raw_alert.notna().sum()),adjusted_assessable=int(g.adjusted_alert.notna().sum()),
                                            raw_alert_rate=float(g.raw_alert.dropna().astype(float).mean()) if g.raw_alert.notna().any() else None,
                                            adjusted_alert_rate=float(g.adjusted_alert.dropna().astype(float).mean()) if g.adjusted_alert.notna().any() else None,
                                            unavailable=int((g.status=='insufficient_history').sum())))
    (out/'evaluation.json').write_text(json.dumps(summary,indent=2,allow_nan=False)+'\n')
    lines=['# Stock Insight evaluation','', 'Recorded historical study; no future-price or usability claims.','',
           '## Portfolio volatility estimation','', '| Market | Portfolio | Method | Origins | MAE (percentage points) |', '|---|---|---|---:|---:|']
    for x in summary['portfolio']:
        lines.append(f"| {x['market']} | {x['portfolio']} | {x['method']} | {x['origins']} | {x['mae_annualized_volatility']*100:.3f} |")
    lines+=['','## Movement interventions','','Injected scenarios are controlled sensitivity checks, not ground-truth market event labels. Normal alert rates are descriptive, not false-positive rates.','',
            '| Market | Scenario | Cases | Raw alert rate | Adjusted alert rate | Unavailable |','|---|---|---:|---:|---:|---:|']
    def rate(v):return 'withheld' if v is None else f'{v*100:.1f}%'
    for x in summary['movement']:
        lines.append(f"| {x['market']} | {x['scenario']} | {x['cases']} | {rate(x['raw_alert_rate'])} | {rate(x['adjusted_alert_rate'])} | {x['unavailable']} |")
    lines+=['','## Limits','','Six predefined symbols; five-year provider snapshots. Small numbers of chronological evaluation origins; no significance or general superiority claim. Historical prices may be revised by the provider. Common-date alignment reduces coverage. Headlines are not ground-truth causes. No user study has been performed. See snapshot metadata and the separate manual alert inspection.']
    (ROOT/'RESULTS.md').write_text('\n'.join(lines)+'\n')
    print(json.dumps({'portfolio_rows':len(vol),'movement_cases':len(moves),'failures':failures}),flush=True)


if __name__=='__main__':main()
