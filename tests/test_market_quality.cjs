const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const source=fs.readFileSync('static/stock_dashboard.js','utf8').replace('return { load,','return { qualityNote, renderAnalyst, load,');
const api=vm.runInNewContext(source+'\nStockDashboard;', {Intl,Date,document:{addEventListener(){}}});
test('unavailable analyst data never renders a neutral rating gauge',()=>{
 const html=api.renderAnalyst({consensus:'N/A',total:0,data_quality:{last_error:'permission_denied'}},'₹',2500);
 assert.match(html,/Analyst ratings unavailable/);assert.ok(!html.includes('<svg'));assert.ok(!html.includes('Updated daily'));
});
test('retained and calculated values explain dates, periods, benchmark and source',()=>{
 const html=api.qualityNote({freshness:'stale',source:'Daily prices',observation_date:'2026-10-26',fetched_at:'2026-10-27T10:00:00Z',calculation:'120 aligned returns',benchmark:'^NSEI'});
 assert.match(html,/Last available/);assert.match(html,/2026-10-26/);assert.match(html,/120 aligned returns/);assert.match(html,/\^NSEI/);
 assert.ok(!api.qualityNote({source:'<script>alert(1)</script>'}).includes('<script>'));
});
