"""Explicit laptop portfolio storage. Never automatically replaces cloud storage."""
from contextlib import contextmanager
import math
from pathlib import Path
import re
import sqlite3
import time
from flask import current_app, jsonify, request


@contextmanager
def database():
    path=Path(current_app.config['PORTFOLIO_SQLITE_PATH'])
    path.parent.mkdir(parents=True,exist_ok=True)
    db=sqlite3.connect(path,timeout=5)
    db.row_factory=sqlite3.Row
    db.execute('PRAGMA foreign_keys=ON')
    db.execute('CREATE TABLE IF NOT EXISTS users (username TEXT PRIMARY KEY COLLATE NOCASE, created_at INTEGER NOT NULL)')
    db.execute('CREATE TABLE IF NOT EXISTS holdings (username TEXT COLLATE NOCASE REFERENCES users(username), symbol TEXT, qty REAL NOT NULL, avg REAL NOT NULL, added_at INTEGER NOT NULL, PRIMARY KEY(username,symbol))')
    try:
        with db:yield db
    finally:db.close()


def username(value):
    if not isinstance(value,str) or not re.fullmatch(r'[A-Za-z0-9_\-]{2,30}',value.strip()):
        raise ValueError('Username must be 2–30 letters, numbers, _ or -.')
    return value.strip()


def holding(h):
    if not isinstance(h,dict):raise ValueError('Invalid holding.')
    from insights_service import symbol
    s=symbol(h.get('symbol'))
    q=float(h.get('qty',0));a=float(h.get('avg',0))
    if not math.isfinite(q) or not math.isfinite(a) or not 0<q<=1e12 or not 0<a<=1e12:
        raise ValueError('Quantity and average price must be positive finite values.')
    added=int(h.get('added_at') or h.get('addedAt') or time.time()*1000)
    if not 0<added<2**63:raise ValueError('Invalid holding timestamp.')
    return s,q,a,added


def intercept():
    if current_app.config.get('PORTFOLIO_STORAGE')!='sqlite' or not request.path.startswith('/api/portfolio/'):
        return None
    action=request.path.rsplit('/',1)[-1]
    if action not in {'identify','load','save','delete','sync'}:return None
    expected='GET' if action=='load' else 'POST'
    if request.method!=expected:return jsonify({'error':'Method not allowed'}),405
    payload=request.args if expected=='GET' else request.get_json(silent=True)
    if payload is None or (expected=='POST' and not isinstance(payload,dict)):
        return jsonify({'error':'A JSON object is required.'}),400
    try:
        user=username(payload.get('username'))
        # Validate replacement holdings BEFORE beginning the deleting transaction.
        if action=='save':item=holding(payload)
        elif action=='sync':
            items=payload.get('holdings',[])
            if not isinstance(items,list) or len(items)>500:raise ValueError('Invalid holdings list.')
            items=[holding(h) for h in items]
            if len({h[0] for h in items})!=len(items):raise ValueError('Duplicate symbols in replacement holdings.')
        elif action=='delete':
            from insights_service import symbol
            delete_symbol=symbol(payload.get('symbol'))
        with database() as db:
            existing=db.execute('SELECT username,created_at FROM users WHERE username=?',(user,)).fetchone()
            if existing:user=existing['username']
            if action=='load':
                rows=db.execute('SELECT symbol,qty,avg,added_at FROM holdings WHERE username=? ORDER BY added_at,symbol',(user,)).fetchall()
                return jsonify(storage='sqlite',holdings=[dict(symbol=r['symbol'],qty=r['qty'],avg=r['avg'],addedAt=r['added_at']) for r in rows])
            if action=='delete':
                db.execute('DELETE FROM holdings WHERE username=? AND symbol=?',(user,delete_symbol))
                return jsonify(ok=True,storage='sqlite')
            created=int(time.time()) if existing is None else existing['created_at']
            db.execute('INSERT OR IGNORE INTO users VALUES (?,?)',(user,created))
            if action=='identify':return jsonify(ok=True,username=user,created_at=created,storage='sqlite')
            if action=='sync':db.execute('DELETE FROM holdings WHERE username=?',(user,))
            for s,q,a,added in ([item] if action=='save' else items):
                db.execute('INSERT INTO holdings VALUES (?,?,?,?,?) ON CONFLICT(username,symbol) DO UPDATE SET qty=excluded.qty,avg=excluded.avg,added_at=excluded.added_at',(user,s,q,a,added))
            return jsonify(ok=True,storage='sqlite')
    except (ValueError,TypeError,OverflowError):
        return jsonify({'error':'Check username, symbol, quantity and average price.'}),400
    except sqlite3.Error:
        current_app.logger.exception('Local portfolio storage unavailable')
        return jsonify({'error':'Local portfolio storage unavailable.'}),503


def configure(app):
    app.config['PORTFOLIO_STORAGE']=app.config.get('PORTFOLIO_STORAGE','supabase')
    app.config['PORTFOLIO_SQLITE_PATH']=app.config.get('PORTFOLIO_SQLITE_PATH',str(Path(app.instance_path)/'portfolio.sqlite3'))
    app.before_request(intercept)
