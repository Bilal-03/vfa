/**
 * stock_dashboard.js  — Fixed version
 * Fixes: chart rendering, news format, logo display, cleaner UI
 */

const StockDashboard = (() => {
    let _symbol = '';
    let _refreshTimer = null;
    let _chart = null;
    let _currentTF = '3M';
    let _chartType = 'area'; // 'area' or 'candle'

    const $id = id => document.getElementById(id);
    const fmt = (v, d=2) => v == null ? '—' : parseFloat(v).toLocaleString('en-IN', {minimumFractionDigits:d, maximumFractionDigits:d});
    const fmtPct = v => v == null ? '—' : (v>=0?'+':'') + parseFloat(v).toFixed(2) + '%';
    const fmtLarge = v => {
        if (v == null) return '—';
        const n = Math.abs(parseFloat(v));
        const sign = parseFloat(v) < 0 ? '-' : '';
        if (n >= 1e12) return sign + '₹' + (n/1e12).toFixed(2) + 'T';
        if (n >= 1e9)  return sign + '₹' + (n/1e9).toFixed(2) + 'B';
        if (n >= 1e7)  return sign + '₹' + (n/1e7).toFixed(2) + 'Cr';
        if (n >= 1e5)  return sign + '₹' + (n/1e5).toFixed(2) + 'L';
        return sign + '₹' + fmt(n);
    };
    const pctOf = v => v == null ? '—' : (parseFloat(v)*100).toFixed(2) + '%';
    const fmtVol = v => {
        if (!v) return '—';
        const n = parseInt(v);
        if (n >= 1e7) return (n/1e7).toFixed(2)+'Cr';
        if (n >= 1e5) return (n/1e5).toFixed(2)+'L';
        if (n >= 1e3) return (n/1e3).toFixed(1)+'K';
        return n.toString();
    };

    // ── Skeleton ─────────────────────────────────────────────────────────────
    function showSkeleton() {
        const d = $id('stock-dashboard');
        if (!d) return;
        d.innerHTML = `
        <div class="si-header" style="gap:16px;display:flex;align-items:center;padding:20px;border-radius:16px;margin-bottom:14px;">
            <div class="si-skel-block" style="width:52px;height:52px;border-radius:14px;flex-shrink:0;"></div>
            <div style="flex:1;display:flex;flex-direction:column;gap:8px;">
                <div class="si-skel-block" style="width:50%;height:18px;border-radius:6px;"></div>
                <div class="si-skel-block" style="width:30%;height:13px;border-radius:6px;"></div>
            </div>
            <div style="display:flex;flex-direction:column;gap:8px;align-items:flex-end;">
                <div class="si-skel-block" style="width:110px;height:26px;border-radius:6px;"></div>
                <div class="si-skel-block" style="width:80px;height:13px;border-radius:6px;"></div>
            </div>
        </div>
        <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin-bottom:14px;">
            ${[1,2,3,4].map(()=>`<div class="si-skel-block" style="height:58px;border-radius:12px;"></div>`).join('')}
        </div>
        <div class="si-skel-block" style="height:300px;border-radius:16px;margin-bottom:14px;"></div>
        <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:10px;">
            ${[1,2,3,4,5,6,7,8].map(()=>`<div class="si-skel-block" style="height:72px;border-radius:12px;"></div>`).join('')}
        </div>`;
    }

    // ── Load ─────────────────────────────────────────────────────────────────
    // ── Symbol resolver ───────────────────────────────────────────────────────
    // Known US tickers that should NOT get .NS appended
    const _US_TICKERS = new Set([
        'AAPL','MSFT','GOOGL','GOOG','AMZN','META','TSLA','NVDA','NFLX','AMD',
        'INTC','JPM','BAC','V','MA','WMT','DIS','UBER','LYFT','SNAP','TWTR',
        'BABA','JD','PDD','NIO','XPEV','BIDU','IBM','ORCL','CRM','ADBE','NOW',
        'PYPL','SQ','COIN','HOOD','SHOP','SPOT','ZM','DOCU','PLTR','RBLX','ABNB',
        'DASH','RIVN','LCID','F','GM','GE','BA','CAT','MMM','XOM','CVX','PFE',
        'JNJ','MRK','ABBV','LLY','UNH','AMGN','GILD','BIIB','MRNA','BRK.B','BRK.A',
        'GS','MS','C','WFC','USB','PNC','AXP','COF','SCHW','BLK','SPGI',
        'KO','PEP','MCD','SBUX','YUM','CMG','NKE','LULU','TGT','HD','LOW',
        'COST','TJX','ETSY','EBAY','NKLA','AMC','GME','BB','NOK',
        'SPY','QQQ','VTI','IWM','GLD','SLV','USO',
    ]);

    function resolveSymbol(raw) {
        let s = raw.toUpperCase().trim();
        // Already has an exchange suffix — use as-is
        if (s.includes('.')) return s;
        // Known US ticker — use as-is
        if (_US_TICKERS.has(s)) return s;
        // Everything else is treated as NSE India — append .NS
        return s + '.NS';
    }

    function load(symbol) {
        _symbol = resolveSymbol(symbol);
        _currentTF = '3M';
        stopAutoRefresh();
        showSkeleton();

        const inp = document.getElementById('fh-search-input');
        if (inp) inp.value = _symbol;

        fetch(`/si/dashboard?symbol=${encodeURIComponent(_symbol)}`)
            .then(r => r.json())
            .then(data => {
                if (data.error) { showError(data.error); return; }
                renderDashboard(data);
                loadChart(_symbol, _currentTF);
                loadNews(_symbol);
                _refreshTimer = setInterval(refreshQuote, 30000);
            })
            .catch(e => showError('Network error: ' + e.message));
    }

    // ── Render ────────────────────────────────────────────────────────────────
    function renderDashboard(data) {
        const { profile, quote, metrics, analyst } = data;
        const d = $id('stock-dashboard');
        if (!d) return;

        const up  = (quote.change || 0) >= 0;
        const sym = (profile.currency === 'USD') ? '$' : '₹';

        // Build company initials for avatar fallback
        const companyInitials = (profile.name || _symbol)
            .split(' ').filter(w => w.length > 0).slice(0, 2)
            .map(w => w[0]).join('').toUpperCase();

        // Logo: Google Favicon API is reliable. Show initials avatar if image fails.
        const logoId = 'si-logo-' + Date.now();
        const fbId   = 'si-fb-'   + Date.now();
        const logoHtml = profile.logo
            ? `<img src="${profile.logo}" class="si-logo" id="${logoId}"
                    onerror="
                        var el=document.getElementById('${logoId}');
                        var fb=document.getElementById('${fbId}');
                        if(el) el.style.display='none';
                        if(fb) fb.style.display='flex';
                    ">
               <div class="si-logo-fb" id="${fbId}" style="display:none;">${companyInitials}</div>`
            : `<div class="si-logo-fb">${companyInitials}</div>`;

        d.innerHTML = `

        <!-- ── HEADER ── -->
        <div class="si-header">
            <div class="si-logo-wrap">
                ${logoHtml}
            </div>
            <div class="si-header-text">
                <div class="si-company-name">${profile.name || _symbol}</div>
                <div class="si-badges">
                    <span class="si-badge">${_symbol}</span>
                    ${profile.sector ? `<span class="si-badge">${profile.sector}</span>` : ''}
                </div>
            </div>
            <div class="si-price-block">
                <div class="si-big-price" id="si-price">${sym}${fmt(quote.current)}</div>
                <div class="si-price-change ${up?'si-up':'si-down'}" id="si-change">
                    ${up?'▲':'▼'} ${Math.abs(quote.change||0).toFixed(2)} (${fmtPct(quote.change_pct)})
                </div>
                <div class="si-live-dot"><span class="si-dot"></span> LIVE · auto-refresh 30s</div>
                <div style="display:flex;gap:6px;margin-top:10px;flex-wrap:wrap;">
                    <button class="si-portfolio-btn"
                        onclick="if(typeof FinTracker !== 'undefined') FinTracker.openAddHolding('${_symbol.replace('.NS','').replace('.BO','')}')">
                        <i class="fas fa-plus"></i> Add to Portfolio
                    </button>
                </div>
            </div>
        </div>

        <!-- ── QUOTE BAR ── -->
        <div class="si-quote-bar">
            ${qi('Open',       sym+fmt(quote.open))}
            ${qi('Prev Close', sym+fmt(quote.prev_close))}
            ${qi('Day High',   sym+fmt(quote.high), 'si-up')}
            ${qi('Day Low',    sym+fmt(quote.low),  'si-down')}
            ${qi('Volume',     fmtVol(quote.volume))}
            ${qi('Avg Volume', fmtVol(quote.avg_volume))}
        </div>

        <!-- ── PRICE CHART ── -->
        <div class="si-card">
            <div class="si-card-header">
                <div class="si-card-title"><i class="fas fa-chart-area"></i> Price Chart</div>
                <div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap;">
                    <div class="si-chart-type-bar">
                        <button class="si-ct-btn active" id="si-ct-area" onclick="StockDashboard.setChartType('area')"><i class="fas fa-chart-area"></i> Area</button>
                        <button class="si-ct-btn" id="si-ct-candle" onclick="StockDashboard.setChartType('candle')"><i class="fas fa-chart-bar"></i> Candle</button>
                    </div>
                    <div class="si-tf-bar">
                        ${['1D','1W','1M','3M','6M','1Y','5Y','MAX'].map(tf =>
                            `<button class="si-tf-btn${tf===_currentTF?' active':''}" onclick="StockDashboard.changeTimeframe('${tf}')">${tf}</button>`
                        ).join('')}
                    </div>
                </div>
            </div>
            <div id="si-chart-container" style="height:320px;width:100%;position:relative;"></div>
        </div>

        <!-- ── KEY METRICS ── -->
        <div class="si-section-title"><i class="fas fa-chart-pie"></i> Key Metrics</div>
        <div class="si-metrics-grid">
            ${mc('Market Cap',   fmtLarge(metrics.market_cap || profile.market_cap))}
            ${mc('PE Ratio',     fmt(metrics.pe_ratio))}
            ${mc('52W High',     metrics.week52_high != null ? sym+fmt(metrics.week52_high) : '—', 'si-up')}
            ${mc('52W Low',      metrics.week52_low  != null ? sym+fmt(metrics.week52_low)  : '—', 'si-down')}
            ${mc('ROE',          metrics.roe != null ? pctOf(metrics.roe) : '—')}
            ${mc('Beta',         fmt(metrics.beta))}
            ${mc('Div Yield',    metrics.dividend_yield != null ? pctOf(metrics.dividend_yield) : '—')}
            ${mc('Price/Book',   fmt(metrics.price_to_book))}
            ${mc('Debt/Equity',  fmt(metrics.debt_equity))}
        </div>

        <!-- ── ANALYST + NEWS ── -->
        <div class="si-two-col">
            <div class="si-card si-analyst-card">
                <div class="si-card-title"><i class="fas fa-users"></i> Analyst Ratings</div>
                <div id="si-analyst-container">
                    ${renderAnalyst(analyst, sym, quote.current)}
                </div>
            </div>
            <div class="si-card">
                <div class="si-card-title"><i class="fas fa-newspaper"></i> Latest News</div>
                <div id="si-news-container">
                    <div class="si-loading-sm"><i class="fas fa-spinner fa-spin"></i> Loading news…</div>
                </div>
            </div>
        </div>

        <!-- ── COMPANY ABOUT ── -->
        ${profile.description ? `
        <div class="si-card">
            <div class="si-card-title"><i class="fas fa-building"></i> About ${profile.name||_symbol}</div>
            <p class="si-about-text">${profile.description}</p>
            <div class="si-about-grid">
                ${profile.industry  ? `<div class="si-about-item"><span>Industry</span><strong>${profile.industry}</strong></div>` : ''}
                ${profile.country   ? `<div class="si-about-item"><span>Country</span><strong>${profile.country}</strong></div>` : ''}
                ${profile.employees ? `<div class="si-about-item"><span>Employees</span><strong>${parseInt(profile.employees).toLocaleString('en-IN')}</strong></div>` : ''}
                ${profile.web_url   ? `<div class="si-about-item"><span>Website</span><a href="${profile.web_url}" target="_blank" class="si-link">${profile.web_url.replace(/https?:\/\//,'')}</a></div>` : ''}
            </div>
        </div>` : ''}
        `;
    }

    function qi(label, val, cls='') {
        return `<div class="si-quote-item">
            <div class="si-quote-label">${label}</div>
            <div class="si-quote-val ${cls}">${val}</div>
        </div>`;
    }

    function mc(label, val, cls='') {
        return `<div class="si-metric-card">
            <div class="si-metric-label">${label}</div>
            <div class="si-metric-val ${cls}">${val == null ? '—' : val}</div>
        </div>`;
    }

    // ── Analyst ───────────────────────────────────────────────────────────────
    function renderAnalyst(a, sym, current) {
        const total = a.total || 0;
        const analystCount = a.analyst_count || 0;
        const consensus = a.consensus || 'N/A';

        const colors = {
            'Strong Buy':  { bg:'#dcfce7', border:'#86efac', text:'#15803d', dot:'#16a34a' },
            'Buy':         { bg:'#d1fae5', border:'#6ee7b7', text:'#047857', dot:'#10b981' },
            'Hold':        { bg:'#fef9c3', border:'#fde047', text:'#a16207', dot:'#eab308' },
            'Sell':        { bg:'#fee2e2', border:'#fca5a5', text:'#b91c1c', dot:'#ef4444' },
            'Strong Sell': { bg:'#fecdd3', border:'#fda4af', text:'#9f1239', dot:'#dc2626' },
            'N/A':         { bg:'#f1f5f9', border:'#cbd5e1', text:'#475569', dot:'#94a3b8' },
        };
        const c = colors[consensus] || colors['N/A'];

        const upside = (a.target_mean && current) ? ((a.target_mean - current) / current * 100) : null;
        const upsideStr = upside != null ? (upside >= 0 ? '+' : '') + upside.toFixed(1) + '%' : null;
        const upsideColor = upside != null ? (upside >= 0 ? '#16a34a' : '#dc2626') : '#64748b';

        // Score gauge: map consensus to 0–100
        const scoreMap = {'Strong Buy':88,'Buy':70,'Hold':50,'Sell':30,'Strong Sell':12,'N/A':50};
        const score = scoreMap[consensus] || 50;
        // Gauge arc: 180deg semicircle
        const gaugePct = score / 100;
        const gaugeColor = score >= 70 ? '#16a34a' : score >= 55 ? '#22c55e' : score <= 30 ? '#dc2626' : score <= 45 ? '#ef4444' : '#eab308';

        // Rating breakdown rows
        const ratingData = [
            { label: 'Strong Buy',  count: a.strong_buy  || 0, color: '#16a34a' },
            { label: 'Buy',         count: a.buy         || 0, color: '#22c55e' },
            { label: 'Hold',        count: a.hold        || 0, color: '#eab308' },
            { label: 'Sell',        count: a.sell        || 0, color: '#ef4444' },
            { label: 'Strong Sell', count: a.strong_sell || 0, color: '#dc2626' },
        ];

        const barsHtml = ratingData.map(r => {
            const pct = total > 0 ? (r.count / total * 100) : 0;
            return `<div class="si-reco-row">
                <span class="si-reco-label">${r.label}</span>
                <div class="si-reco-bar-wrap">
                    <div class="si-reco-bar" style="width:${pct.toFixed(0)}%;background:${r.color};"></div>
                </div>
                <span class="si-reco-count" style="color:${r.count > 0 ? r.color : '#cbd5e1'}">${r.count}</span>
            </div>`;
        }).join('');

        // Target price mini-cards
        const targetHtml = a.target_mean ? `
        <div class="si-target-strip">
            <div class="si-target-mini">
                <div class="si-target-mini-label">Low</div>
                <div class="si-target-mini-val">${sym}${fmt(a.target_low || 0)}</div>
            </div>
            <div class="si-target-mini si-target-mini-mean">
                <div class="si-target-mini-label">Mean Target</div>
                <div class="si-target-mini-val si-target-mini-val-lg">${sym}${fmt(a.target_mean)}</div>
                ${upsideStr ? `<div class="si-target-upside" style="color:${upsideColor}">${upsideStr} potential</div>` : ''}
            </div>
            <div class="si-target-mini">
                <div class="si-target-mini-label">High</div>
                <div class="si-target-mini-val">${sym}${fmt(a.target_high || 0)}</div>
            </div>
        </div>` : '';

        return `
        <!-- Consensus + Gauge row -->
        <div class="si-analyst-top">
            <!-- Left: Gauge -->
            <div class="si-gauge-wrap">
                <svg class="si-gauge-svg" viewBox="0 0 120 65" xmlns="http://www.w3.org/2000/svg">
                    <!-- Track -->
                    <path d="M10,60 A50,50 0 0,1 110,60" fill="none" stroke="#f1f5f9" stroke-width="12" stroke-linecap="round"/>
                    <!-- Fill — stroke-dasharray trick on semicircle path length ~157 -->
                    <path d="M10,60 A50,50 0 0,1 110,60" fill="none" stroke="${gaugeColor}" stroke-width="12"
                          stroke-linecap="round"
                          stroke-dasharray="${(gaugePct * 157).toFixed(1)} 157"
                          style="transition:stroke-dasharray 1s ease;"/>
                    <!-- Needle dot -->
                    <circle cx="60" cy="10" r="4" fill="${gaugeColor}" opacity="0.3"/>
                </svg>
                <div class="si-gauge-label">${consensus}</div>
                <div class="si-gauge-sub">${analystCount > 0 ? analystCount + ' analysts' : total > 0 ? total + ' ratings' : 'yfinance data'}</div>
            </div>
            <!-- Right: Rating bars -->
            <div class="si-reco-section">
                ${total > 0 ? barsHtml : `<div class="si-no-ratings">
                    <i class="fas fa-info-circle"></i>
                    <span>Consensus based on yfinance recommendation key. Detailed breakdown unavailable for this stock.</span>
                </div>`}
            </div>
        </div>

        <!-- Target prices -->
        ${targetHtml}

        <!-- Source note -->
        <div class="si-analyst-src">
            <i class="fas fa-circle-info"></i>
            Data sourced from Yahoo Finance · Wall Street analyst ratings · Updated daily
        </div>`;
    }

    // ── Chart ─────────────────────────────────────────────────────────────────
    function loadChart(symbol, tf) {
        const c = $id('si-chart-container');
        if (!c) return;
        c.innerHTML = '<div class="si-loading-sm"><i class="fas fa-spinner fa-spin"></i> Loading chart…</div>';

        fetch(`/si/candle?symbol=${encodeURIComponent(symbol)}&timeframe=${tf}`)
            .then(r => r.json())
            .then(data => {
                if (data.error || !data.candles?.length) {
                    c.innerHTML = '<div class="si-chart-empty">Chart data unavailable for this timeframe.</div>';
                    return;
                }
                buildChart(c, data.candles, tf);
            })
            .catch(() => { c.innerHTML = '<div class="si-chart-empty">Failed to load chart.</div>'; });
    }

    function buildChart(container, candles, tf) {
        container.innerHTML = '';

        if (typeof LightweightCharts === 'undefined') {
            container.innerHTML = '<div class="si-chart-empty">Chart library not loaded. Please refresh.</div>';
            return;
        }

        try {
            const intraday = tf === '1D' || tf === '1W';
            candles.sort((a,b) => a.time - b.time);

            // De-duplicate by time key
            const seen = new Set();
            const unique = candles.filter(c => {
                const k = intraday ? c.time : new Date(c.time*1000).toISOString().slice(0,10);
                return seen.has(k) ? false : seen.add(k);
            });

            if (unique.length === 0) {
                container.innerHTML = '<div class="si-chart-empty">No chart data available.</div>';
                return;
            }

            const toTime = c => intraday ? c.time : new Date(c.time*1000).toISOString().slice(0,10);

            if (_chart) { try { _chart.remove(); } catch(e){} _chart = null; }

            _chart = LightweightCharts.createChart(container, {
                width: container.clientWidth || 600,
                height: 320,
                layout: { background: { color: '#ffffff' }, textColor: '#475569' },
                grid: {
                    vertLines: { color: 'rgba(226,232,240,0.6)' },
                    horzLines: { color: 'rgba(226,232,240,0.6)' }
                },
                crosshair: { mode: LightweightCharts.CrosshairMode.Normal },
                rightPriceScale: { borderColor: '#e2e8f0', scaleMargins:{ top:0.05, bottom:0.2 } },
                timeScale: {
                    borderColor: '#e2e8f0',
                    timeVisible: intraday,
                    secondsVisible: false,
                    fixLeftEdge: true,
                    fixRightEdge: true,
                },
                handleScale: { axisPressedMouseMove: true },
                handleScroll: { mouseWheel: true, pressedMouseMove: true },
            });

            // Determine if overall trend is up or down for area color
            const firstClose = unique[0].close;
            const lastClose  = unique[unique.length - 1].close;
            const trendUp    = lastClose >= firstClose;

            if (_chartType === 'area') {
                // ── Smooth area/line series ──────────────────────────────────
                const aData = unique.map(c => ({ time: toTime(c), value: c.close }));

                const areaColor  = trendUp ? 'rgba(34,197,94,0.15)' : 'rgba(239,68,68,0.1)';
                const lineColor  = trendUp ? '#16a34a' : '#dc2626';
                const topColor   = trendUp ? 'rgba(34,197,94,0.35)' : 'rgba(239,68,68,0.25)';
                const botColor   = 'rgba(255,255,255,0)';

                const as = _chart.addAreaSeries({
                    lineColor: lineColor,
                    topColor:  topColor,
                    bottomColor: botColor,
                    lineWidth: 2,
                    crosshairMarkerVisible: true,
                    crosshairMarkerRadius: 5,
                    crosshairMarkerBorderColor: lineColor,
                    crosshairMarkerBackgroundColor: '#ffffff',
                    priceLineVisible: true,
                    priceLineColor: lineColor,
                    priceLineWidth: 1,
                    priceLineStyle: LightweightCharts.LineStyle.Dashed,
                    lastValueVisible: true,
                });
                as.setData(aData);

            } else {
                // ── Candlestick series ───────────────────────────────────────
                const cData = unique.map(c => ({
                    time: toTime(c), open: c.open, high: c.high, low: c.low, close: c.close
                }));
                const cs = _chart.addCandlestickSeries({
                    upColor: '#22c55e', downColor: '#ef4444',
                    borderUpColor: '#16a34a', borderDownColor: '#dc2626',
                    wickUpColor: '#22c55e', wickDownColor: '#ef4444',
                });
                cs.setData(cData);
            }

            // ── Volume histogram (always shown at the bottom) ────────────────
            const vData = unique.map(c => ({
                time: toTime(c),
                value: c.volume,
                color: c.close >= c.open ? 'rgba(34,197,94,0.25)' : 'rgba(239,68,68,0.25)'
            }));
            const vs = _chart.addHistogramSeries({
                priceFormat: { type: 'volume' },
                priceScaleId: 'vol',
                scaleMargins: { top: 0.8, bottom: 0 }
            });
            vs.setData(vData);

            _chart.timeScale().fitContent();

            // Responsive resize
            const ro = new ResizeObserver(entries => {
                if (_chart && entries[0]) _chart.applyOptions({ width: entries[0].contentRect.width });
            });
            ro.observe(container);

        } catch (err) {
            console.error('Chart build error:', err);
            container.innerHTML = `<div class="si-chart-empty">Chart error: ${err.message}</div>`;
        }
    }

    // ── News ──────────────────────────────────────────────────────────────────
    function loadNews(symbol) {
        const c = $id('si-news-container');
        if (!c) return;

        fetch(`/si/news?symbol=${encodeURIComponent(symbol)}`)
            .then(r => r.json())
            .then(data => {
                const articles = data.articles || [];
                if (!articles.length) {
                    c.innerHTML = `<div class="si-news-empty">
                        <i class="fas fa-newspaper" style="font-size:1.5rem;color:#cbd5e1;margin-bottom:8px;"></i>
                        <p>No recent news found for ${symbol}.</p>
                    </div>`;
                    return;
                }
                c.innerHTML = articles.slice(0, 6).map(a => {
                    const dateStr = a.datetime
                        ? new Date(a.datetime * 1000).toLocaleDateString('en-IN', {day:'numeric',month:'short',year:'numeric'})
                        : '';
                    return `
                    <a href="${a.url || '#'}" target="_blank" rel="noopener" class="si-news-item">
                        <div class="si-news-title">${a.headline || 'Untitled'}</div>
                        <div class="si-news-meta">
                            ${a.source ? `<span class="si-news-source">${a.source}</span>` : ''}
                            ${dateStr ? `<span>${dateStr}</span>` : ''}
                        </div>
                    </a>`;
                }).join('');
            })
            .catch(err => {
                console.error('News fetch error:', err);
                c.innerHTML = '<div class="si-news-empty"><p>News temporarily unavailable.</p></div>';
            });
    }

    // ── Quote refresh ─────────────────────────────────────────────────────────
    function refreshQuote() {
        if (!_symbol) return;
        fetch(`/si/quote?symbol=${encodeURIComponent(_symbol)}`)
            .then(r => r.json())
            .then(q => {
                if (q.error) return;
                const priceEl = document.getElementById('si-price');
                const changeEl = document.getElementById('si-change');
                if (priceEl) {
                    const sym = q.currency === 'USD' ? '$' : '₹';
                    priceEl.textContent = sym + fmt(q.current);
                    priceEl.classList.add('si-flash');
                    setTimeout(() => priceEl.classList.remove('si-flash'), 700);
                }
                if (changeEl) {
                    const up = (q.change||0) >= 0;
                    changeEl.className = 'si-price-change ' + (up?'si-up':'si-down');
                    changeEl.innerHTML = `${up?'▲':'▼'} ${Math.abs(q.change||0).toFixed(2)} (${fmtPct(q.change_pct)})`;
                }
            }).catch(()=>{});
    }

    // ── Chart type toggle ─────────────────────────────────────────────────────
    function setChartType(type) {
        _chartType = type;
        document.querySelectorAll('.si-ct-btn').forEach(b => {
            b.classList.toggle('active', b.id === `si-ct-${type}`);
        });
        loadChart(_symbol, _currentTF);
    }

    // ── Timeframe ─────────────────────────────────────────────────────────────
    function changeTimeframe(tf) {
        _currentTF = tf;
        document.querySelectorAll('.si-tf-btn').forEach(b => b.classList.toggle('active', b.textContent===tf));
        loadChart(_symbol, tf);
    }

    // ── Error ─────────────────────────────────────────────────────────────────
    function showError(msg) {
        const d = $id('stock-dashboard');
        if (d) d.innerHTML = `
        <div class="si-error-card">
            <div style="font-size:2.5rem;margin-bottom:12px;">⚠️</div>
            <div class="si-error-title">Could not load stock data</div>
            <div class="si-error-msg">${msg}</div>
            <div class="si-error-hint">Try: RELIANCE · TCS · INFY · SUZLON · DELHIVERY · AAPL · MSFT</div>
        </div>`;
    }

    function stopAutoRefresh() {
        if (_refreshTimer) { clearInterval(_refreshTimer); _refreshTimer = null; }
        if (_chart) { try { _chart.remove(); } catch(e){} _chart = null; }
    }

    // ── Dashboard search bar with autocomplete ────────────────────────────────
    document.addEventListener('DOMContentLoaded', () => {
        const btn  = document.getElementById('fh-search-btn');
        const inp  = document.getElementById('fh-search-input');
        const drop = document.getElementById('fh-search-dropdown');

        if (!inp) return;

        // Reuse fuzzyScore if defined in page scope, else use simple includes
        function _score(str, q) {
            str = str.toLowerCase(); q = q.toLowerCase().trim();
            if (!q) return 0;
            if (str === q) return 100;
            if (str.startsWith(q)) return 90;
            if (str.includes(q)) return 70;
            let si=0,qi=0,sc=0;
            while(si<str.length&&qi<q.length){if(str[si]===q[qi]){sc++;qi++;}si++;}
            return qi===q.length?Math.round(50*sc/q.length):0;
        }

        function showDrop(val) {
            if (!drop) return;
            if (!val || val.length < 1) { drop.style.display = 'none'; return; }

            const list = (typeof STOCK_MASTER_LIST !== 'undefined') ? STOCK_MASTER_LIST : [];
            const scored = list.map(s => ({
                s,
                score: Math.max(_score(s.v, val), _score(s.l, val))
            })).filter(x => x.score > 0).sort((a,b) => b.score - a.score).slice(0,12);

            if (!scored.length) {
                drop.innerHTML = `<div style="padding:10px 14px;font-size:12px;color:#64748b;font-style:italic;">
                    Press Enter to search "<strong>${val.toUpperCase()}</strong>"</div>`;
            } else {
                drop.innerHTML = scored.map(({s}) => `
                    <div class="fh-drop-item" data-ticker="${s.v}" style="
                        padding:9px 14px;cursor:pointer;display:flex;align-items:center;
                        justify-content:space-between;gap:8px;border-bottom:1px solid #f1f5f9;
                        transition:background 0.12s;font-family:inherit;">
                        <span style="font-size:12.5px;font-weight:600;color:#0f172a;">${s.l}</span>
                        <span style="font-size:11px;font-weight:700;color:#2563eb;background:#eff6ff;
                            padding:2px 8px;border-radius:20px;white-space:nowrap;">${s.v}</span>
                    </div>`).join('');
            }
            drop.style.display = 'block';
        }

        inp.addEventListener('input', () => showDrop(inp.value.trim()));
        inp.addEventListener('focus', () => { if(inp.value.trim()) showDrop(inp.value.trim()); });

        // Click on dropdown item
        if (drop) {
            drop.addEventListener('mousedown', e => {
                const item = e.target.closest('.fh-drop-item');
                if (item) {
                    e.preventDefault();
                    const ticker = item.dataset.ticker;
                    inp.value = ticker;
                    drop.style.display = 'none';
                    load(ticker);
                }
            });
            // Hover highlight
            drop.addEventListener('mouseover', e => {
                const item = e.target.closest('.fh-drop-item');
                if (item) item.style.background = '#f8fafc';
            });
            drop.addEventListener('mouseout', e => {
                const item = e.target.closest('.fh-drop-item');
                if (item) item.style.background = '';
            });
        }

        // Enter / button submit
        function doSearch() {
            const v = inp.value.trim();
            if (!v) return;
            if (drop) drop.style.display = 'none';
            load(v);
        }

        if (btn) btn.addEventListener('click', doSearch);
        inp.addEventListener('keydown', e => {
            if (e.key === 'Enter') { doSearch(); }
            if (e.key === 'Escape' && drop) drop.style.display = 'none';
        });

        // Close dropdown on outside click
        document.addEventListener('click', e => {
            if (drop && !inp.contains(e.target) && !drop.contains(e.target)) {
                drop.style.display = 'none';
            }
        });
    });

    return { load, changeTimeframe, setChartType, stopAutoRefresh };
})();