/**
 * portfolio_watchlist.js — FinAssist
 * Portfolio Tracker with server-side persistence via username identity.
 * Username stored in localStorage; portfolio lives on the server (SQLite).
 */

const FinTracker = (() => {

    // ── Username identity (persisted locally, portfolio stored server-side) ──
    const LS = {
        get: k => { try { return JSON.parse(localStorage.getItem('fa_'+k)); } catch { return null; } },
        set: (k,v) => { try { localStorage.setItem('fa_'+k, JSON.stringify(v)); } catch {} },
    };

    let _username = LS.get('username') || null;  // null = not identified yet
    let _portfolioCache = [];                     // in-memory cache for fast renders

    const getUsername = () => _username;

    // ── Symbol resolver ───────────────────────────────────────────────────────
    const US = new Set(['AAPL','MSFT','GOOGL','GOOG','AMZN','META','TSLA','NVDA',
        'NFLX','AMD','INTC','JPM','BAC','V','MA','WMT','DIS','UBER','GE','BA',
        'XOM','CVX','PFE','JNJ','MRK','ABBV','LLY','UNH','GS','MS','C','WFC',
        'KO','PEP','MCD','SBUX','NKE','HD','COST','BABA','NIO','COIN','PLTR',
        'RBLX','ABNB','SHOP','SPY','QQQ','BRK.B','BRK.A','PYPL','SQ','ZM','F','GM']);
    const resolve = raw => { const s=raw.toUpperCase().trim(); if(s.includes('.'))return s; return US.has(s)?s:s+'.NS'; };
    const display = sym => sym.replace('.NS','').replace('.BO','');

    // ── Formatters ────────────────────────────────────────────────────────────
    const fmtMoney = (v, c='₹') => {
        if (v==null||isNaN(v)) return '—';
        const n=Math.abs(v), sg=v<0?'-':'';
        if (c==='₹') {
            if(n>=1e7) return sg+'₹'+(n/1e7).toFixed(2)+'Cr';
            if(n>=1e5) return sg+'₹'+(n/1e5).toFixed(2)+'L';
            return sg+'₹'+n.toLocaleString('en-IN',{minimumFractionDigits:2,maximumFractionDigits:2});
        }
        return sg+c+n.toLocaleString('en-US',{minimumFractionDigits:2,maximumFractionDigits:2});
    };
    const fmtN   = (v,d=2) => v==null?'—':parseFloat(v).toLocaleString('en-IN',{minimumFractionDigits:d,maximumFractionDigits:d});
    const fmtPct = v => v==null?'—':(v>=0?'+':'')+parseFloat(v).toFixed(2)+'%';
    const cls    = v => parseFloat(v)>=0?'pt-up':'pt-down';

    // ── API helpers ───────────────────────────────────────────────────────────
    const fetchQ = async sym => { try{ const r=await fetch(`/si/quote?symbol=${encodeURIComponent(sym)}`); const d=await r.json(); return d?.error?null:d; }catch{return null;} };
    const fetchP = async sym => { try{ const r=await fetch(`/si/profile?symbol=${encodeURIComponent(sym)}`); const d=await r.json(); return d?.error?null:d; }catch{return null;} };

    // ── Server portfolio API ──────────────────────────────────────────────────
    async function serverLoad() {
        if (!_username) return [];
        try {
            const r = await fetch(`/api/portfolio/load?username=${encodeURIComponent(_username)}`);
            const d = await r.json();
            _portfolioCache = d.holdings || [];
            return _portfolioCache;
        } catch { return _portfolioCache; }
    }

    async function serverSave(holding) {
        if (!_username) return;
        await fetch('/api/portfolio/save', {
            method: 'POST',
            headers: {'Content-Type':'application/json'},
            body: JSON.stringify({ username: _username, ...holding })
        });
    }

    async function serverDelete(symbol) {
        if (!_username) return;
        await fetch('/api/portfolio/delete', {
            method: 'POST',
            headers: {'Content-Type':'application/json'},
            body: JSON.stringify({ username: _username, symbol })
        });
    }

    // ── Toast ─────────────────────────────────────────────────────────────────
    function toast(msg, type='success') {
        const t=document.createElement('div');
        t.className=`pt-toast pt-toast-${type}`;
        t.innerHTML=`<i class="fas fa-${type==='success'?'check-circle':type==='error'?'exclamation-circle':'info-circle'}"></i> ${msg}`;
        document.body.appendChild(t);
        requestAnimationFrame(()=>t.classList.add('pt-toast-show'));
        setTimeout(()=>{t.classList.remove('pt-toast-show');setTimeout(()=>t.remove(),350);},2800);
    }

    // ── Logo ──────────────────────────────────────────────────────────────────
    function mkLogo(name, logo, sz='36px', r='10px') {
        const init=(name||'??').split(' ').filter(Boolean).slice(0,2).map(w=>w[0]).join('').toUpperCase();
        const id='i'+Math.random().toString(36).slice(2,8), fb='f'+Math.random().toString(36).slice(2,8);
        if(logo) return `<img src="${logo}" id="${id}" style="width:${sz};height:${sz};border-radius:${r};object-fit:contain;background:#fff;border:1px solid #e2e8f0;padding:4px;display:block;"
            onerror="var e=document.getElementById('${id}'),f=document.getElementById('${fb}');if(e)e.style.display='none';if(f)f.style.display='flex';">
            <div id="${fb}" class="pt-logo-fb" style="width:${sz};height:${sz};border-radius:${r};display:none;">${init}</div>`;
        return `<div class="pt-logo-fb" style="width:${sz};height:${sz};border-radius:${r};">${init}</div>`;
    }

    // ════════════════════════════════════════════════════════════════════════
    //  IDENTITY SCREEN — shown when no username is set
    // ════════════════════════════════════════════════════════════════════════
    function renderIdentityScreen() {
        const content = document.getElementById('pt-content');
        const sumBar  = document.getElementById('pt-summary-bar');
        if (sumBar) sumBar.innerHTML = '';
        if (!content) return;
        content.innerHTML = `
            <div class="pt-identity-wrap">
                <div class="pt-identity-card">
                    <div class="pt-identity-icon">
                        <i class="fas fa-user-circle"></i>
                    </div>
                    <div class="pt-identity-title">Set Your Portfolio Identity</div>
                    <div class="pt-identity-sub">
                        Choose a unique username to save and sync your portfolio across any browser or device.
                        No password or signup required — just pick a name and you're good to go.
                    </div>
                    <div class="pt-identity-input-wrap">
                        <i class="fas fa-at pt-identity-at"></i>
                        <input type="text" id="pt-username-input" class="pt-identity-input"
                               placeholder="e.g. rahul_investor"
                               maxlength="30"
                               onkeydown="if(event.key==='Enter') FinTracker.submitUsername()"
                               oninput="this.value=this.value.replace(/[^A-Za-z0-9_\-]/g,'')">
                    </div>
                    <div class="pt-identity-hint">Only letters, numbers, _ and - allowed &nbsp;·&nbsp; 2–30 characters</div>
                    <div class="pt-identity-err" id="pt-username-err"></div>
                    <button class="pt-identity-btn" onclick="FinTracker.submitUsername()">
                        <i class="fas fa-arrow-right"></i> Continue
                    </button>
                    <div class="pt-identity-note">
                        <i class="fas fa-lock-open"></i>
                        Anyone who knows your username can access your portfolio — keep it personal.
                    </div>
                </div>
            </div>`;
        setTimeout(() => document.getElementById('pt-username-input')?.focus(), 200);
    }

    async function submitUsername() {
        const inp = document.getElementById('pt-username-input');
        const err = document.getElementById('pt-username-err');
        const val = (inp?.value || '').trim();
        if (!val || val.length < 2) { if(err) err.textContent = 'Username must be at least 2 characters.'; return; }
        // Disable button while checking
        const btn = document.querySelector('.pt-identity-btn');
        if (btn) { btn.disabled = true; btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Connecting…'; }
        try {
            const r = await fetch('/api/portfolio/identify', {
                method: 'POST',
                headers: {'Content-Type':'application/json'},
                body: JSON.stringify({ username: val })
            });
            const d = await r.json();
            if (d.error) { if(err) err.textContent = d.error; if(btn){btn.disabled=false;btn.innerHTML='<i class="fas fa-arrow-right"></i> Continue';} return; }
            _username = d.username;
            LS.set('username', _username);
            updateUsernameDisplay();
            toast(`Welcome, ${_username}! 👋`, 'success');
            startPortfolioRefresh();
        } catch(e) {
            if(err) err.textContent = 'Server error — please try again.';
            if(btn){btn.disabled=false;btn.innerHTML='<i class="fas fa-arrow-right"></i> Continue';}
        }
    }

    function updateUsernameDisplay() {
        // Show username in panel header
        const badge = document.getElementById('pt-user-badge');
        if (badge) {
            if (_username) {
                badge.innerHTML = `<i class="fas fa-user-circle"></i> ${_username} <button class="pt-switch-btn" onclick="FinTracker.switchUser()" title="Switch user"><i class="fas fa-exchange-alt"></i></button>`;
                badge.style.display = 'flex';
            } else {
                badge.style.display = 'none';
            }
        }
        // Show/hide add holding button
        const addBtn = document.getElementById('pt-add-btn');
        if (addBtn) addBtn.style.display = _username ? 'inline-flex' : 'none';
    }

    function switchUser() {
        if (!confirm(`Switch user? Your current portfolio (${_username}) will still be saved on the server and you can return to it anytime.`)) return;
        _username = null;
        _portfolioCache = [];
        LS.set('username', null);
        stopPortfolioRefresh();
        updateUsernameDisplay();
        renderIdentityScreen();
    }

    // ════════════════════════════════════════════════════════════════════════
    //  PORTFOLIO
    // ════════════════════════════════════════════════════════════════════════
    let _pt = null;

    let _editMode = false; // true when editing existing holding (replace, not merge)

    function openAddHolding(pre='') {
        if (!_username) { renderIdentityScreen(); return; }
        _editMode = false;
        const m=document.getElementById('pt-modal'); if(!m)return;
        const title = document.getElementById('pt-modal-title');
        if (title) title.textContent = 'Add Holding';
        const saveBtn = document.getElementById('pt-modal-save-btn');
        if (saveBtn) saveBtn.innerHTML = '<i class="fas fa-plus"></i> Add Holding';
        document.getElementById('pt-modal-sym').value=pre||'';
        document.getElementById('pt-modal-sym').readOnly=false;
        document.getElementById('pt-modal-qty').value='';
        document.getElementById('pt-modal-avg').value='';
        document.getElementById('pt-modal-err').textContent='';
        m.classList.add('pt-modal-open');
        setTimeout(()=>document.getElementById(pre?'pt-modal-qty':'pt-modal-sym').focus(),120);
    }

    function editHolding(sym) {
        if (!_username) { renderIdentityScreen(); return; }
        const holding = _portfolioCache.find(h=>h.symbol===sym);
        if (!holding) return;
        _editMode = true;
        const m=document.getElementById('pt-modal'); if(!m)return;
        const title = document.getElementById('pt-modal-title');
        if (title) title.textContent = `Edit ${display(sym)}`;
        const saveBtn = document.getElementById('pt-modal-save-btn');
        if (saveBtn) saveBtn.innerHTML = '<i class="fas fa-save"></i> Update Holding';
        const symInput = document.getElementById('pt-modal-sym');
        symInput.value = display(sym);
        symInput.readOnly = true; // can't change symbol when editing
        document.getElementById('pt-modal-qty').value = holding.qty;
        document.getElementById('pt-modal-avg').value = holding.avg;
        document.getElementById('pt-modal-err').textContent='';
        m.classList.add('pt-modal-open');
        setTimeout(()=>document.getElementById('pt-modal-qty').focus(),120);
    }

    function closeModal(){
        document.getElementById('pt-modal')?.classList.remove('pt-modal-open');
        _editMode = false;
        const symInput = document.getElementById('pt-modal-sym');
        if (symInput) symInput.readOnly = false;
    }

    async function saveHolding() {
        const rawSym=document.getElementById('pt-modal-sym').value.trim();
        const qty=parseFloat(document.getElementById('pt-modal-qty').value);
        const avg=parseFloat(document.getElementById('pt-modal-avg').value);
        const err=document.getElementById('pt-modal-err');
        if(!rawSym){err.textContent='Please enter a stock symbol.';return;}
        if(!qty||qty<=0){err.textContent='Enter a valid quantity.';return;}
        if(!avg||avg<=0){err.textContent='Enter a valid average buy price.';return;}

        const sym = _editMode ? _portfolioCache.find(h=>display(h.symbol)===rawSym||h.symbol===rawSym)?.symbol || resolve(rawSym) : resolve(rawSym);
        const port = _portfolioCache;
        const idx = port.findIndex(h=>h.symbol===sym);
        let finalQty = qty, finalAvg = avg, addedAt = Date.now();

        if(_editMode && idx>=0){
            // Edit mode: directly replace qty and avg
            const o=port[idx];
            addedAt = o.addedAt || Date.now();
            _portfolioCache[idx] = {...o, qty:finalQty, avg:finalAvg};
            toast(`${display(sym)} updated ✏️`);
        } else if(!_editMode && idx>=0){
            // Add mode on existing: merge (recalculate avg)
            const o=port[idx]; const tq=o.qty+qty;
            finalQty = tq;
            finalAvg = parseFloat(((o.qty*o.avg+qty*avg)/tq).toFixed(4));
            addedAt  = o.addedAt || Date.now();
            _portfolioCache[idx] = {...o, qty:finalQty, avg:finalAvg};
            toast(`${display(sym)} updated — avg price recalculated`);
        } else {
            _portfolioCache.push({symbol:sym, qty:finalQty, avg:finalAvg, addedAt});
            toast(`${display(sym)} added to portfolio 📈`);
        }

        closeModal();
        renderPortfolio();
        // Persist to server
        await serverSave({symbol:sym, qty:finalQty, avg:finalAvg, added_at:addedAt});
    }

    async function removeHolding(sym) {
        if(!confirm(`Remove ${display(sym)} from your portfolio?`))return;
        _portfolioCache = _portfolioCache.filter(h=>h.symbol!==sym);
        toast(`${display(sym)} removed`,'info');
        renderPortfolio();
        await serverDelete(sym);
    }

    async function renderPortfolio() {
        const content=document.getElementById('pt-content');
        const sumBar=document.getElementById('pt-summary-bar');
        if(!content)return;

        // If no username yet — show identity screen
        if (!_username) {
            updateUsernameDisplay();
            renderIdentityScreen();
            return;
        }

        updateUsernameDisplay();

        const port = _portfolioCache;
        if(!port.length){
            if(sumBar)sumBar.innerHTML='';
            content.innerHTML=`<div class="pt-empty">
                <div class="pt-empty-icon"><i class="fas fa-chart-pie"></i></div>
                <div class="pt-empty-title">Your portfolio is empty</div>
                <div class="pt-empty-sub">Click <strong>+ Add Holding</strong> to start tracking your investments.</div>
            </div>`; return;
        }

        // skeleton
        content.innerHTML=`<div class="pt-table-wrap"><table class="pt-table">
            <thead><tr><th>Stock</th><th>Qty</th><th>Avg Buy</th><th>LTP</th><th>Invested</th><th>Curr. Value</th><th>P&amp;L</th><th>Return</th><th></th></tr></thead>
            <tbody>${port.map(()=>`<tr>${Array(9).fill(`<td><div class="pt-skel" style="height:13px;border-radius:4px;"></div></td>`).join('')}</tr>`).join('')}</tbody>
        </table></div>`;

        const results=await Promise.all(port.map(async h=>{
            const [q,p]=await Promise.all([fetchQ(h.symbol),fetchP(h.symbol)]);
            return{h,q,p};
        }));

        let totI=0,totC=0,hasLive=false;
        const rows=results.map(({h,q,p})=>{
            const ltp=q?.current??null, curr=q?.currency==='USD'?'$':'₹';
            const inv=h.qty*h.avg, cv=ltp!=null?h.qty*ltp:null;
            const pnl=cv!=null?cv-inv:null, pnlP=pnl!=null&&inv?(pnl/inv)*100:null;
            const name=p?.name||display(h.symbol);
            if(cv!=null){totI+=inv;totC+=cv;hasLive=true;}
            return `<tr class="pt-tr" onclick="showStockFromPortfolio('${h.symbol}')" style="cursor:pointer;" title="View ${display(h.symbol)}">
                <td><div class="pt-stock-cell">
                    <div class="pt-logo-wrap">${mkLogo(name,p?.logo,'34px','9px')}</div>
                    <div><div class="pt-sym">${display(h.symbol)}</div><div class="pt-cname">${name.length>18?name.slice(0,18)+'…':name}</div></div>
                </div></td>
                <td class="pt-mono">${fmtN(h.qty,h.qty%1===0?0:2)}</td>
                <td class="pt-mono">${curr}${fmtN(h.avg)}</td>
                <td class="pt-mono ${ltp!=null?(ltp>=h.avg?'pt-up':'pt-down'):''}">${ltp!=null?curr+fmtN(ltp):'—'}</td>
                <td class="pt-mono">${fmtMoney(inv,curr)}</td>
                <td class="pt-mono">${cv!=null?fmtMoney(cv,curr):'—'}</td>
                <td class="pt-mono ${pnl!=null?cls(pnl):''}">${pnl!=null?(pnl>=0?'+':'')+fmtMoney(pnl,curr):'—'}</td>
                <td class="pt-mono ${pnlP!=null?cls(pnlP):''}">${pnlP!=null?fmtPct(pnlP):'—'}</td>
                <td onclick="event.stopPropagation()">
                    <div class="pt-action-btns">
                        <button class="pt-edit-btn" onclick="FinTracker.editHolding('${h.symbol}')" title="Edit holding">
                            <i class="fas fa-pencil-alt"></i>
                        </button>
                        <button class="pt-remove-btn" onclick="FinTracker.removeHolding('${h.symbol}')" title="Remove">
                            <i class="fas fa-trash-alt"></i>
                        </button>
                    </div>
                </td>
            </tr>`;
        }).join('');

        const totPnl=totC-totI, totPct=totI>0?(totPnl/totI)*100:0;
        if(sumBar&&hasLive) sumBar.innerHTML=`<div class="pt-summary-cards">
            <div class="pt-sum-card"><div class="pt-sum-label">Invested</div><div class="pt-sum-val">${fmtMoney(totI)}</div></div>
            <div class="pt-sum-card"><div class="pt-sum-label">Current Value</div><div class="pt-sum-val">${fmtMoney(totC)}</div></div>
            <div class="pt-sum-card ${cls(totPnl)}"><div class="pt-sum-label">Total P&amp;L</div><div class="pt-sum-val">${(totPnl>=0?'+':'')+fmtMoney(totPnl)}</div></div>
            <div class="pt-sum-card ${cls(totPct)}"><div class="pt-sum-label">Returns</div><div class="pt-sum-val">${fmtPct(totPct)}</div></div>
            <div class="pt-sum-card"><div class="pt-sum-label">Holdings</div><div class="pt-sum-val">${port.length}</div></div>
        </div>`;

        content.innerHTML=`<div class="pt-table-wrap"><table class="pt-table">
            <thead><tr><th>Stock</th><th>Qty</th><th>Avg Buy</th><th>LTP</th><th>Invested</th><th>Curr. Value</th><th>P&amp;L</th><th>Return</th><th></th></tr></thead>
            <tbody>${rows}</tbody>
        </table></div>`;
    }

    async function startPortfolioRefresh() {
        stopPortfolioRefresh();
        // Load from server first, then render
        if (_username) await serverLoad();
        renderPortfolio();
        _pt = setInterval(async () => {
            if (_username) await serverLoad();
            renderPortfolio();
        }, 30000);
    }
    function stopPortfolioRefresh(){if(_pt){clearInterval(_pt);_pt=null;}}

    // Legacy watchlist stubs (panel removed)
    function startWatchlistRefresh(){}
    function stopWatchlistRefresh(){}
    function isInWatchlist(){return false;}
    function addToWatchlist(){}
    function removeFromWatchlist(){}
    function addFromInput(){}

    // ── Navigation ────────────────────────────────────────────────────────────
    window._siNavSource = null;

    window.showStockDashboard = function(sym, source) {
        window._siNavSource = source || null;
        ['#portfolioPanel','#watchlistPanel','#stockDashboardPanel','#formsContainer',
         '#resultsContainer','#messageFormeight','#welcomeScreen','#newsPanel',
         '#currencyPanel','#metalsPanel','#mfPanel','#glossaryPanel','#mfCatBar','#chatFooter']
        .forEach(s=>$(s).hide());
        stopPortfolioRefresh();
        $('#stockDashboardPanel').show();
        const backBtn = document.getElementById('si-back-btn');
        if (backBtn) {
            if (source === 'portfolio') {
                backBtn.innerHTML = '<i class="fas fa-arrow-left"></i> Back to Portfolio';
                backBtn.classList.add('back-to-portfolio');
            } else {
                backBtn.innerHTML = '<i class="fas fa-arrow-left"></i> Back';
                backBtn.classList.remove('back-to-portfolio');
            }
            backBtn.onclick = function() { siGoBack(); };
        }
        if(typeof StockDashboard!=='undefined') StockDashboard.load(sym);
    };

    window.showStockFromPortfolio = function(sym) {
        window.showStockDashboard(sym, 'portfolio');
    };

    window.siGoBack = function() {
        if (window._siNavSource === 'portfolio') {
            window._siNavSource = null;
            ['#stockDashboardPanel','#formsContainer','#resultsContainer',
             '#messageFormeight','#welcomeScreen','#newsPanel',
             '#currencyPanel','#metalsPanel','#mfPanel','#glossaryPanel',
             '#mfCatBar','#chatFooter','#watchlistPanel']
            .forEach(s=>$(s).hide());
            $('#portfolioPanel').css('display','flex');
            $('.menu-btn').removeClass('active');
            $('.menu-btn').each(function(){
                if($(this).attr('onclick') && $(this).attr('onclick').includes('portfolio'))
                    $(this).addClass('active');
            });
            startPortfolioRefresh();
        } else {
            if(typeof showForm === 'function') showForm('stock');
        }
    };

    // ── Init: restore username if already set ─────────────────────────────────
    function init() {
        updateUsernameDisplay();
    }
    // Run init after DOM ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }

    return {
        isInWatchlist, addToWatchlist, removeFromWatchlist, addFromInput,
        openAddHolding, editHolding, closeModal, saveHolding, removeHolding,
        startWatchlistRefresh, stopWatchlistRefresh,
        startPortfolioRefresh, stopPortfolioRefresh,
        submitUsername, switchUser, getUsername,
    };
})();