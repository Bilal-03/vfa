document.addEventListener('DOMContentLoaded', () => {
    const output = document.getElementById('research-evidence');
    if (!output) return;
    const node = (tag, text) => { const n = document.createElement(tag); n.textContent = text; return n; };
    fetch('/api/forecast/benchmark').then(r => r.json()).then(data => {
        output.replaceChildren();
        if (!data.runs?.length) { output.append(node('p',data.error || 'No completed experiments.')); return; }
        for (const run of data.runs) {
            const m=run.metadata;
            output.append(node('h3', `${m.market} · seed ${m.seed} · ${m.news_enabled ? 'Price and news study' : 'Price-only study'}`));
            output.append(node('p',`Test period ${m.split_dates.test.join(' to ')}. ${m.split_counts.test} samples. ${m.protocol}.`));
            const table=node('table',''); table.style.cssText='width:100%;text-align:left;border-collapse:collapse;font-size:14px';
            const header=node('tr',''); for(const label of ['Model','Accuracy %','Balanced accuracy %','Macro F1','MCC','Samples']) {const cell=node('th',label);cell.style.cssText='padding:10px 8px;white-space:normal';header.append(cell);} table.append(header);
            for (const [name,v] of Object.entries(run.models)) {
                const row=node('tr','');
                for(const value of [name,v.accuracy_pct.toFixed(2),v.balanced_accuracy_pct.toFixed(2),v.macro_f1.toFixed(3),v.mcc.toFixed(3),v.samples]) { const cell=node('td',String(value));cell.style.padding='8px';row.append(cell); }
                table.append(row);
            }
            output.append(table);
            const chosen=run.models.gated || run.models.technical;
            output.append(node('p','Confusion matrix: actual rows / predicted columns, Bearish, Neutral, Bullish.'));
            output.append(node('pre',chosen.confusion_matrix.map(row=>row.join('   ')).join('\n')));
        }
        output.append(node('p','Exploratory results on different market periods. Probabilities are uncalibrated. No trading-return or causal attribution claims.'));
    }).catch(() => { output.textContent='Research evidence unavailable.'; });
    const controls=node('div','');
    const select=node('select','');for(const symbol of ['TCS.NS','INFY.NS','SBIN.NS','AAPL','MSFT','NVDA']) {const option=node('option',symbol);select.append(option);}
    const polarity=node('input','');polarity.type='number';polarity.min=-1;polarity.max=1;polarity.step=.1;polarity.value='0';polarity.setAttribute('aria-label','Hypothetical sentiment polarity');
    const age=node('input','');age.type='number';age.min=0;age.max=168;age.value='24';age.setAttribute('aria-label','Hypothetical news age in hours');
    const button=node('button','Run hypothetical scenario');const result=node('p','');
    button.onclick=async()=>{try {const r=await fetch('/api/forecast/simulate',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({symbol:select.value,polarity:Number(polarity.value),age_hours:Number(age.value)})});const d=await r.json();result.textContent=d.status==='ready'?`${d.forecast.prediction}: ${Object.entries(d.forecast.probabilities).map(([k,v])=>`${k} ${(v*100).toFixed(1)}%`).join(', ')}. ${d.interpretation}`:d.error;}catch {result.textContent='Simulation unavailable.';}};
    controls.append(node('h3','Hypothetical sensitivity scenario'),node('p','Polarity −1 to +1; news age 0–168 hours. This is not observed news.'),select,polarity,age,button,result);output.after(controls);
});
