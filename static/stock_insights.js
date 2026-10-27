/* One accessible card; calculations and explanations come from the shared service. */
const StockInsights = (() => {
    let state = null;
    const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
    const pct = n => n == null ? 'Unavailable' : `${(n*100).toFixed(2)}%`;
    const num = n => n == null ? 'Unavailable' : Number(n).toFixed(2);
    const money = (n, c) => new Intl.NumberFormat(c==='INR'?'en-IN':'en-US', {style:'currency',currency:c,maximumFractionDigits:0}).format(n);
    const tile = (label,value,help='') => `<div class="sii-stat"><span>${esc(label)}</span><strong>${esc(value)}</strong>${help?`<small>${esc(help)}</small>`:''}</div>`;
    const facts = d => `<ul class="sii-facts">${(d.facts||[]).filter(Boolean).map(f=>`<li>${esc(f)}</li>`).join('')}</ul>`;
    function mount(symbol) {
        const host = document.getElementById('si-insights-container');
        if (!host) return;
        if (state?.controller) state.controller.abort();
        state = {symbol, tab:'portfolio-fit', amount:10000, months:3, controller:new AbortController(), sequence:0, holdings:[]};
        host.innerHTML = `<section class="si-card sii-card" aria-labelledby="sii-title">
          <div class="sii-heading"><div><div class="sii-eyebrow">UNDERSTAND BEFORE YOU INVEST</div><h3 id="sii-title">Stock Insight</h3><p>Your holdings. The market. Historical experience.</p></div><span class="sii-badge">Explainable analytics</span></div>
          <div class="sii-tabs" role="tablist" aria-label="Stock insights">${[['portfolio-fit','Portfolio Fit'],['movement','Unusual Movement'],['historical','Historical Experience']].map(([id,label],i)=>`<button type="button" id="sii-tab-${id}" role="tab" aria-selected="${i===0}" aria-controls="sii-content" data-tab="${id}" tabindex="${i===0?0:-1}">${label}</button>`).join('')}</div>
          <form id="sii-form" class="sii-controls"><label id="sii-amount-label"><span id="sii-amount-text">Additional investment (${symbol.endsWith('.NS')||symbol.endsWith('.BO')?'INR':'USD'})</span><input id="sii-amount" type="number" min="0" max="1000000000" step="any" value="10000" required></label><label id="sii-months-label" hidden>Holding period<select id="sii-months"><option value="1">1 month</option><option value="3" selected>3 months</option><option value="6">6 months</option><option value="12">12 months</option></select></label><button class="sii-primary" id="sii-update" type="submit">Analyze purchase</button></form>
          <div id="sii-content" role="tabpanel" aria-labelledby="sii-tab-portfolio-fit" aria-live="polite"></div>
          <div id="sii-meta" class="sii-meta"></div>
        </section>`;
        const tabs = [...host.querySelectorAll('[data-tab]')];
        tabs.forEach((button,i)=> {
            button.addEventListener('click',()=> select(button.dataset.tab));
            button.addEventListener('keydown',e=> {
                if (!['ArrowLeft','ArrowRight','Home','End'].includes(e.key)) return;
                e.preventDefault();
                const next=e.key==='Home'?0:e.key==='End'?2:(i+(e.key==='ArrowRight'?1:2))%3;
                tabs[next].focus(); select(tabs[next].dataset.tab);
            });
        });
        host.querySelector('form').addEventListener('submit',e=> {
            e.preventDefault();
            state.amount=Number(document.getElementById('sii-amount').value);
            state.months=Number(document.getElementById('sii-months').value);
            load();
        });
        load();
    }
    function select(tab) {
        if (!state) return;
        state.tab=tab;
        document.querySelectorAll('.sii-tabs button').forEach(b=> {
            b.setAttribute('aria-selected',String(b.dataset.tab===tab)); b.tabIndex=b.dataset.tab===tab?0:-1;
        });
        document.getElementById('sii-form').hidden=tab==='movement';
        document.getElementById('sii-months-label').hidden=tab!=='historical';
        document.getElementById('sii-amount-text').textContent=`${tab==='historical'?'Investment amount':'Additional investment'} (${state.symbol.endsWith('.NS')||state.symbol.endsWith('.BO')?'INR':'USD'})`;
        document.getElementById('sii-update').textContent=tab==='historical'?'Explore history':'Analyze purchase';
        document.getElementById('sii-content').setAttribute('aria-labelledby',`sii-tab-${tab}`);
        load();
    }
    async function request(url,options={}) {
        const response=await fetch(url,{...options,signal:state.controller.signal});
        const result=await response.json();
        if (!response.ok) throw new Error(result.error||'Insight unavailable.');
        return result;
    }
    async function load() {
        const current=state;
        const sequence=++current.sequence;
        const content=document.getElementById('sii-content');
        const meta=document.getElementById('sii-meta');
        content.innerHTML='<p class="sii-loading">Preparing your insight…</p>'; meta.textContent='';
        try {
            let d;
            const params=new URLSearchParams({symbol:current.symbol,amount:current.amount,months:current.months});
            if (current.tab==='portfolio-fit') {
                const username=typeof FinTracker!=='undefined'?FinTracker.getUsername():null;
                current.holdings=[];
                if (username) {
                    const saved=await request(`/api/portfolio/load?username=${encodeURIComponent(username)}`);
                    current.holdings=saved.holdings||[];
                }
                d=await request('/si/insights/portfolio-fit',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({symbol:current.symbol,amount:current.amount,holdings:current.holdings})});
            } else d=await request(`/si/insights/${current.tab}?${params}`);
            if (state!==current||sequence!==current.sequence) return;
            current.data=d;
            const usable=d.status==='ready'||(current.tab==='movement'&&d.status==='partial');
            if (!usable) {
                content.innerHTML=`<div class="sii-empty"><strong>${esc(d.status==='empty_portfolio'?'Make this personal':d.status==='stale'?'Waiting for current prices':'Insight unavailable')}</strong><p>${esc(d.message||'Please retry shortly.')}</p>${d.status==='empty_portfolio'?'<button type="button" class="sii-primary" id="sii-add">Open Portfolio</button>':''}</div>`;
                document.getElementById('sii-add')?.addEventListener('click',()=> { if(typeof showScreen==='function'){showScreen('portfolioScreen');if(typeof FinTracker!=='undefined')FinTracker.startPortfolioRefresh();}else if(typeof showForm==='function')showForm('portfolio'); });
            } else {
                content.innerHTML=current.tab==='portfolio-fit'?renderPortfolio(d):current.tab==='movement'?renderMovement(d):renderHistory(d);
                content.insertAdjacentHTML('beforeend',`${technical(d,current.tab)}<button type="button" class="sii-explain" id="sii-explain">Ask FinAssist to explain</button><div id="sii-explanation" class="sii-explanation" aria-live="polite"></div>`);
                document.getElementById('sii-explain').addEventListener('click',explain);
            }
            const coverage=d.coverage;
            if(d.observation_date&&!d.stale) content.insertAdjacentHTML('afterbegin',`<p class="sii-date">Using prices from ${esc(dateLabel(d.observation_date))}.</p>`);

            if(d.analysis_mode==='historical_demo') content.insertAdjacentHTML('afterbegin',`<p class="sii-warning">Historical demonstration · analysis cutoff ${esc(d.analysis_as_of)}. These are recorded historical prices, not live quotes.</p>`);
            if(d.analysis_mode==='live'&&d.stale) content.insertAdjacentHTML('afterbegin',`<p class="sii-warning">Using prices from ${esc(dateLabel(d.observation_date))}. Provider data is delayed; the latest completed session is ${esc(dateLabel(d.expected_session))}.</p>`);
            meta.textContent=[current.tab==='portfolio-fit'&&document.documentElement.dataset.portfolioStorage==='sqlite'?'Portfolio storage: this laptop':'',d.portfolio_scope, d.observation_date?`Analysis session: ${d.observation_date}`:'', coverage?`History: ${coverage.start} – ${coverage.end}`:'', d.stale?'DELAYED DATA':'',d.calculation_version].filter(Boolean).join(' · ');

        } catch(e) {
            if(state!==current||sequence!==current.sequence||e.name==='AbortError')return;
            content.innerHTML=`<div class="sii-empty"><p>${esc(e.message)}</p><button class="sii-primary" id="sii-retry" type="button">Retry insight</button></div>`;
            document.getElementById('sii-retry').addEventListener('click',load);
        }
    }
    const dateLabel = value => value ? new Intl.DateTimeFormat('en-GB',{day:'numeric',month:'short',year:'numeric',timeZone:'UTC'}).format(new Date(String(value).slice(0,10)+'T12:00:00Z')) : 'Date unavailable';
    const signed = n => n == null ? 'Unavailable' : `${n>0?'+':''}${pct(n)}`;
    const palette = ['#4f46e5','#0891b2','#b45309','#be185d','#047857','#7c3aed'];
    const takeaway = (question, title, text='') => `<p class="sii-question">${esc(question)}</p><div class="sii-takeaway"><h4>${esc(title)}</h4>${text?`<p>${esc(text)}</p>`:''}</div>`;
    const table = (caption, headings, rows) => `<div class="sii-table-wrap"><table><caption>${esc(caption)}</caption><thead><tr>${headings.map(h=>`<th scope="col">${esc(h)}</th>`).join('')}</tr></thead><tbody>${rows.map(r=>`<tr>${r.map((v,i)=>`<${i?'td':'th scope="row"'}>${esc(v)}</${i?'td':'th'}>`).join('')}</tr>`).join('')}</tbody></table></div>`;
    function technical(d, kind) {
        let body='';
        if(kind==='portfolio-fit') {
            const b=d.before,a=d.after;
            const rows=[['Largest stock allocation',pct(b.largest_stock_weight),pct(a.largest_stock_weight)],['Concentration (HHI)',num(b.concentration_hhi),num(a.concentration_hhi)],['Annualized historical volatility',pct(b.annualized_volatility),pct(a.annualized_volatility)],['Historical daily downside (5th percentile)',pct(b.daily_return_p05),pct(a.daily_return_p05)],['Historical maximum drawdown',pct(b.historical_drawdown.max_drawdown),pct(a.historical_drawdown.max_drawdown)]];
            for(const [label,values] of [['Stock',b.weights],['Sector',b.sector_exposure]]) {
                const after=label==='Stock'?a.weights:a.sector_exposure;
                Object.keys({...values,...after}).sort().forEach(k=>rows.push([`${label}: ${k}`,pct(values[k]||0),pct(after[k]||0)]));
            }
            body=table('Complete hypothetical fixed-weight comparison',['Measure','Before','After purchase'],rows)+`<p>Correlation: ${num(d.candidate_correlation)}. Most overlapping holding: ${esc(d.largest_overlap?.symbol||'Unavailable')} (correlation ${num(d.largest_overlap?.correlation)}).</p><p>${d.aligned_returns} common daily returns, ${esc(dateLabel(d.aligned_start))} – ${esc(dateLabel(d.aligned_end))}.</p><dl><dt>HHI</dt><dd>Sum of squared allocation weights. A larger value means more money is concentrated in fewer companies.</dd><dt>Annualized volatility</dt><dd>A historical measure of price swings, scaled to a year. It is not an expected gain or loss.</dd><dt>Daily downside, 5th percentile</dt><dd>About 5% of observed daily returns were at or below this value.</dd><dt>Maximum drawdown</dt><dd>The largest observed fall from an earlier peak in the hypothetical portfolio.</dd></dl>`;
        } else if(kind==='movement') {
            body=table('Exact movement measurements',['Measure','Value'],[['Stock return',signed(d.stock_return)],['Benchmark return',signed(d.benchmark_return)],['Regression-adjusted deviation',signed(d.abnormal_return)],['Robust unusualness score',num(d.robust_score)],['Raw-return robust score',num(d.raw_robust_score)],['Volume multiple',d.volume_multiple==null?'Unavailable':num(d.volume_multiple)+'×']]);
        } else body=table('Exact historical measurements',['Measure','Value'],[['Median return',pct(d.median_return)],['10th percentile return',pct(d.p10_return)],['90th percentile return',pct(d.p90_return)],['Worst holding-period return',pct(d.worst_return)],['Maximum drawdown',pct(d.drawdown.max_drawdown)],['Overlapping windows',d.window_count],['Trading sessions per window',d.horizon_sessions]]);
        return `<details class="sii-method sii-technical"><summary>Numbers and methodology</summary>${body}${facts(d)}<p>${esc(method(kind))}</p>${d.coverage?.warnings?.length?`<p>Data checks: ${esc(d.coverage.warnings.join(' '))}</p>`:''}</details>`;
    }
    function allocations(title,before,after) {
        const keys=Object.keys({...before,...after}).filter(k=>(before[k]||0)>0||(after[k]||0)>0).sort((x,y)=>(after[y]||0)-(after[x]||0)||x.localeCompare(y));
        const shown=keys.length>6?keys.slice(0,5):keys;
        const groups=shown.map(k=>({name:k,b:before[k]||0,a:after[k]||0}));
        if(keys.length>6) groups.push({name:'Other',b:keys.slice(5).reduce((n,k)=>n+(before[k]||0),0),a:keys.slice(5).reduce((n,k)=>n+(after[k]||0),0)});
        const bar=key=>`<div class="sii-stack" aria-hidden="true">${groups.map((g,i)=>`<span style="width:${g[key]*100}%;background:${palette[i]}">${g[key]>=.14?esc(pct(g[key])):''}</span>`).join('')}</div>`;
        return `<figure class="sii-visual"><figcaption>${esc(title)}</figcaption><div class="sii-bar-row"><b>Before</b>${bar('b')}</div><div class="sii-bar-row"><b>After</b>${bar('a')}</div><ul class="sii-legend">${groups.map((g,i)=>`<li><span class="sii-swatch" style="background:${palette[i]}" aria-hidden="true"></span><strong>${esc(g.name)}</strong><span>${pct(g.b)} → ${pct(g.a)}</span></li>`).join('')}</ul><p class="sii-small">Each bar represents 100% of the included portfolio.</p></figure>`;
    }
    function pairedBars(title,before,after) {
        const max=Math.max(before,after,.000001);
        return `<figure class="sii-visual"><figcaption>${esc(title)}</figcaption>${[['Before',before],['After',after]].map(([label,n])=>`<div class="sii-bar-row"><b>${label}</b><div class="sii-track" aria-hidden="true"><span style="width:${n/max*100}%"></span></div><strong>${pct(n)}</strong></div>`).join('')}<p class="sii-small">Both bars use the same scale. Historical swings do not predict future gains or losses.</p></figure>`;
    }
    function renderPortfolio(d) {
        const b=d.before,a=d.after,change=a.concentration_hhi-b.concentration_hhi;
        const spread=change < -1e-8?'Your money is spread more evenly across companies':change > 1e-8?'More of your money is concentrated in fewer companies':'Your spread across companies stays the same';
        const swing=a.annualized_volatility-b.annualized_volatility;
        const sectors=Object.keys({...b.sector_exposure,...a.sector_exposure}).sort((x,y)=>(a.sector_exposure[y]||0)-(a.sector_exposure[x]||0));
        const sector=sectors[0], sb=b.sector_exposure[sector]||0,sa=a.sector_exposure[sector]||0;
        const observations=[`Largest holding: ${pct(b.largest_stock_weight)} before → ${pct(a.largest_stock_weight)} after.`,`${sector} exposure ${Math.abs(sa-sb)<1e-8?'stays at '+pct(sa):'changes from '+pct(sb)+' to '+pct(sa)}.`, `Historical price swings ${Math.abs(swing)<1e-8?'stay the same':swing<0?'decrease':'increase'} (${pct(b.annualized_volatility)} → ${pct(a.annualized_volatility)}).`];
        const corr=d.candidate_correlation;
        return `${d.excluded_symbols?.length?`<p class="sii-warning">${esc(d.portfolio_scope)} only. Foreign-currency holdings excluded: ${esc(d.excluded_symbols.join(', '))}.</p>`:''}${takeaway('What changes if I add this stock?',spread,`Adding ${money(d.amount,d.currency)} of ${d.symbol} to holdings worth ${money(d.portfolio_value,d.currency)}. This comparison uses hypothetical fixed weights.`)}
        ${allocations('Your money across companies',b.weights,a.weights)}${allocations('Your money across industries',b.sector_exposure,a.sector_exposure)}
        <ul class="sii-observations">${observations.map(t=>`<li>${esc(t)}</li>`).join('')}</ul>${pairedBars('Historical price swings · annualized',b.annualized_volatility,a.annualized_volatility)}
        <figure class="sii-visual"><figcaption>How closely this stock has moved with your holdings</figcaption>${corr==null?'<p>Not enough price variation to measure this relationship.</p>':`<div class="sii-scale" aria-hidden="true"><span class="sii-marker" style="left:${(corr+1)*50}%"></span></div><div class="sii-scale-labels"><span>−1 · Opposite</span><span>0 · Little linear link</span><span>+1 · Similar</span></div><p><strong>Historical correlation: ${num(corr)}</strong></p>`}<p class="sii-small">Similar movements can mean overlapping exposure. This is not a buy or sell recommendation.</p></figure>`;
    }
    function renderMovement(d) {
        const signal=d.unusual===true?'Unusually large movement':d.unusual===false?'Within its usual historical range':'Only part of the market comparison is available';
        const values=[['Stock',d.stock_return], [d.benchmark_name||d.benchmark_symbol,d.benchmark_return]].filter(([,v])=>v!=null);
        const max=Math.max(...values.map(([,v])=>Math.abs(v)),.000001);
        const safeArticles=(d.news||[]).filter(a=>/^https?:\/\//i.test(a.url||''));
        const score=d.robust_score,limit=Math.max(5,score==null?0:Math.abs(score));
        return `${takeaway('Did this stock move differently from the market?',signal,`Stock move: ${signed(d.stock_return)} on ${dateLabel(d.observation_date)}.`)}
        <figure class="sii-visual"><figcaption>Stock and market · same trading session</figcaption>${values.map(([label,n])=>`<div class="sii-signed-row"><b>${esc(label)}</b><div class="sii-signed-track" aria-hidden="true"><span style="left:${n<0?50-Math.abs(n)/max*50:50}%;width:${Math.abs(n)/max*50}%;background:${n<0?'#b45309':'#4f46e5'}"></span></div><strong>${signed(n)}</strong></div>`).join('')}<div class="sii-axis"><span>← Fell</span><span>0 · No change</span><span>Rose →</span></div>${d.benchmark_return==null?'<p>Benchmark prices are unavailable for comparison; only the stock move is shown.</p>':''}</figure>
        ${d.abnormal_return==null?'<p>There is not enough aligned history to calculate the market-adjusted movement.</p>':`<div class="sii-takeaway"><h4>Beyond the usual market relationship: ${signed(d.abnormal_return)}</h4><p>The stock moved ${d.abnormal_return<0?'below':'above'} the estimate from its historical relationship with the market. This uses a fitted model, rather than simply subtracting the two returns.</p></div>`}
        ${score==null?'<p>Unusualness cannot be measured reliably with the available data.</p>':`<figure class="sii-visual"><figcaption>How unusual was the market-adjusted move?</figcaption><div class="sii-scale sii-unusual-scale" aria-hidden="true"><span class="sii-usual-zone" style="left:${(1-3.5/limit)*50}%;width:${3.5/limit*100}%"></span>${[-3.5,3.5].map(n=>`<span class="sii-threshold" style="left:${(n/limit+1)*50}%"></span>`).join('')}<span class="sii-marker" style="left:${(score/limit+1)*50}%"></span></div><div class="sii-scale-labels"><span>−${num(limit)}</span><span>0</span><span>+${num(limit)}</span></div><p><strong>Unusualness: ${num(score)}</strong> · flagged below −3.5 or above +3.5.</p>${Math.abs(score)>5?'<p>The scale expands to show this extreme value in full.</p>':''}<p class="sii-small">The shaded middle is the usual historical range. Unusual does not mean a future rise or fall.</p></figure>`}
        <div class="sii-takeaway"><h4>${d.volume_multiple==null?'Trading activity unavailable':num(d.volume_multiple)+'× its usual volume'}</h4><p>“Usual” is the median daily trading volume over the preceding 20 sessions.</p></div>
        <details class="sii-method"><summary>Recent headline context (${safeArticles.length})</summary><p>${esc(d.news_note)}</p>${safeArticles.map(a=>`<a class="sii-news" href="${esc(a.url)}" target="_blank" rel="noopener noreferrer">${esc(a.headline)}<small>${esc(a.source)} · ${esc(dateLabel(new Date(a.datetime*1000).toISOString()))}</small></a>`).join('')||'<p>No dated recent headlines available.</p>'}</details>`;
    }
    function renderHistory(d) {
        const histogram=d.distribution,max=Math.max(...histogram.map(b=>b.count),1),dd=d.drawdown;
        const spread=d.p90_value-d.p10_value;
        const pos=n=>spread>0?(n-d.p10_value)/spread*100:50;
        const startInside=d.amount>=d.p10_value&&d.amount<=d.p90_value;
        return `${takeaway('What happened to this amount in the past?',`Middle historical outcome: ${money(d.median_value,d.currency)}`,`${money(d.amount,d.currency)} held for ${d.months} month${d.months===1?'':'s'} · ${pct(d.median_return)} median return. These are recorded past experiences, not a forecast.`)}
        <figure class="sii-visual"><figcaption>Middle 80% of past ending values</figcaption><div class="sii-range" aria-hidden="true"><span class="sii-marker" style="left:${pos(d.median_value)}%"></span>${startInside?`<span class="sii-investment-marker" style="left:${pos(d.amount)}%"></span>`:''}</div><div class="sii-range-labels"><span><b>${esc(money(d.p10_value,d.currency))}</b><small>Lower end · 10th percentile</small></span><span><b>${esc(money(d.median_value,d.currency))}</b><small>Middle · median</small></span><span><b>${esc(money(d.p90_value,d.currency))}</b><small>Upper end · 90th percentile</small></span></div><p class="sii-small">A percentile shows where a value sits among past outcomes. The lower and upper markers are the 10th and 90th percentiles; tied outcomes can share the same value.${startInside?` Dashed marker: original ${money(d.amount,d.currency)} investment.`:` Original investment: ${money(d.amount,d.currency)} (outside this range).`}${spread===0?' All three values coincide; markers share the centre.':''}</p></figure>
        <figure class="sii-visual"><figcaption>Past holding periods ending in a loss</figcaption><div class="sii-loss-track" aria-hidden="true"><span style="width:${d.losing_fraction*100}%"></span></div><p><strong>${pct(d.losing_fraction)}</strong> of ${d.window_count} overlapping historical periods ended below their starting value.</p><p class="sii-small">These periods overlap and are not independent observations. This percentage is not a future chance of losing money.</p></figure>
        <details class="sii-method"><summary>Explore all historical outcomes</summary><figure class="sii-distribution"><figcaption>Historical ${d.months}-month outcomes · ${d.window_count} periods</figcaption><div class="sii-bars" aria-hidden="true">${histogram.map(b=>`<div class="sii-bin" style="height:${b.count/max*100}%;background:${b.high<=0?'#b45309':'#4f46e5'}"></div>`).join('')}</div><div class="sii-axis"><span>${esc(money(d.amount*(1+histogram[0].low),d.currency))}</span><span>Ending value →</span><span>${esc(money(d.amount*(1+histogram[histogram.length-1].high),d.currency))}</span></div>${table('All distribution bins',['Ending value / return range','Periods'],histogram.map(b=>[`${money(d.amount*(1+b.low),d.currency)} – ${money(d.amount*(1+b.high),d.currency)} (${pct(b.low)} – ${pct(b.high)})`,b.count]))}</figure></details>
        <div class="sii-grid">${tile('Worst holding-period outcome',money(d.worst_value,d.currency),`${pct(d.worst_return)} over ${d.months} month${d.months===1?'':'s'}`)}${tile('Largest fall from a previous peak',pct(dd.max_drawdown),'Across the full price history, not just the selected holding period')}</div>
        <figure class="sii-visual"><figcaption>Largest historical fall · recovery timeline</figcaption><ol class="sii-timeline"><li><b>Previous peak</b><span>${esc(dateLabel(dd.peak_date))}</span></li><li><b>Lowest point</b><span>${esc(dateLabel(dd.trough_date))}</span></li><li><b>${dd.recovery_date?'Peak reached again':'Not yet recovered'}</b><span>${dd.recovery_date?esc(dateLabel(dd.recovery_date)):'Within the available price history'}</span></li></ol><p class="sii-small">${dd.max_drawdown===0?'No fall from a previous peak was observed.':dd.recovery_date?`${dd.sessions_peak_to_recovery} observed trading sessions from peak to recovery.`:'Later prices have not reached the previous peak within this dataset.'} This timeline lists events; spacing does not represent elapsed time.</p></figure>`;
    }
    function method(tab) {
        return tab==='portfolio-fit'?'Holdings are valued at the latest common unadjusted close. Historical returns use adjusted closes on common dates without filling gaps. Ledoit–Wolf shrinkage estimates covariance; annualized volatility = square root of 252 × weighted covariance. Historical downside and drawdown use a hypothetical daily-rebalanced portfolio at fixed weights. HHI is the sum of squared stock weights; lower means less concentration. Largest overlap is positive correlation × existing weight.':tab==='movement'?'Each daily residual compares the stock return with an intercept-plus-market regression fitted to the preceding 120 aligned returns. The latest residual is compared with 60 preceding one-step residuals using (residual − median) / (1.4826 × MAD). Only completed exchange sessions are eligible, with a 15-minute provider buffer. A zero MAD makes the standardized assessment unavailable.':'For each complete window, ending adjusted close / starting adjusted close − 1 gives its return. Windows span 21, 63, 126 or 252 trading sessions. Percentiles summarize actual windows, not forecasts. Maximum drawdown measures the largest decline from a running peak; recovery means reaching that peak again. No prices are filled across missing sessions.';
    }
    async function explain() {
        const current=state,seq=current.sequence;
        const target=document.getElementById('sii-explanation');
        target.textContent='Preparing FinAssist explanation…';
        const body=new URLSearchParams({msg:`Explain ${current.tab} for ${current.symbol}`,insight_kind:current.tab,insight_symbol:current.symbol,insight_amount:current.amount,insight_months:current.months,insight_holdings:JSON.stringify(current.holdings)});
        try {
            const r=await fetch('/get',{method:'POST',body,signal:current.controller.signal});
            const text=await r.text();
            if(state===current&&seq===current.sequence)target.innerHTML=text; // server escapes its calculated facts
        } catch(e) { if(e.name!=='AbortError'&&state===current&&seq===current.sequence)target.textContent='Explanation unavailable. Please retry.'; }
    }
    return {mount};
})();
