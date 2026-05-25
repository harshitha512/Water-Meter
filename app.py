from flask import Flask, request, jsonify, session, redirect, Response
import sqlite3
from functools import wraps

app = Flask(__name__)
app.secret_key = "water2024"
DB = "water.db"
USERS = {"admin": "admin123", "user1": "water456"}

# ── Database ─────────────────────────────────────────────────
def db():
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    return c

def init_db():
    c = db()
    c.execute("""CREATE TABLE IF NOT EXISTS readings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts TEXT DEFAULT (datetime('now','localtime')),
        flow REAL, liters REAL, bill REAL, price REAL)""")
    c.execute("""CREATE TABLE IF NOT EXISTS alerts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts TEXT DEFAULT (datetime('now','localtime')),
        level TEXT, msg TEXT)""")
    c.commit(); c.close()

# ── Auth ─────────────────────────────────────────────────────
def protected(f):
    @wraps(f)
    def wrap(*a, **k):
        if "user" not in session:
            return redirect("/login")
        return f(*a, **k)
    return wrap

# ── Login page HTML ───────────────────────────────────────────
LOGIN = """<!DOCTYPE html><html><head><meta charset="UTF-8">
<title>Water Meter Login</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{background:#0f172a;font-family:system-ui,sans-serif;min-height:100vh;display:flex;align-items:center;justify-content:center}
.card{background:#1e3a5f;border:1px solid #1e3a8a;border-radius:14px;padding:36px 32px;width:360px}
h2{color:#fff;font-size:20px;margin-bottom:4px;text-align:center}
.sub{color:#93c5fd;font-size:13px;text-align:center;margin-bottom:24px}
label{display:block;color:#93c5fd;font-size:11px;text-transform:uppercase;letter-spacing:.06em;margin-bottom:6px}
input{width:100%;background:#0f172a;border:1px solid #1e3a8a;border-radius:8px;padding:10px 13px;color:#fff;font-size:14px;outline:none;margin-bottom:16px}
input:focus{border-color:#3b82f6}
button{width:100%;background:#3b82f6;color:#0f172a;border:none;border-radius:8px;padding:12px;font-size:14px;font-weight:700;cursor:pointer;margin-top:4px}
button:hover{opacity:.9}
.err{background:#3a1a1a;border:1px solid #7a2a2a;border-radius:8px;padding:10px 13px;color:#ff7070;font-size:13px;margin-bottom:16px;display:none}
.hint{margin-top:18px;background:#0f172a;border:1px solid #1e3a8a;border-radius:8px;padding:10px 13px;font-size:12px;color:#93c5fd;font-family:monospace}
.logo{text-align:center;font-size:22px;font-weight:700;color:#fff;margin-bottom:6px}
.logo span{color:#3b82f6}
</style></head><body>
<div class="card">
  <div class="logo">IoT<span>dashboard</span></div>
  <h2>Water Meter</h2>
  <p class="sub">Sign in to monitor your water usage</p>
  <div class="err" id="err">Invalid username or password</div>
  <form method="POST" action="/login">
    <label>Username</label>
    <input type="text" name="username" placeholder="admin" required>
    <label>Password</label>
    <input type="password" name="password" placeholder="••••••••" required>
    <button type="submit">Sign In</button>
  </form>
  <div class="hint">admin / admin123 &nbsp;|&nbsp; user1 / water456</div>
</div>
<script>
if(location.search.includes('error'))
  document.getElementById('err').style.display='block';
</script>
</body></html>"""

# ── Dashboard HTML ────────────────────────────────────────────
DASHBOARD = """<!DOCTYPE html><html><head><meta charset="UTF-8">
<title>IoT Dashboard - Water Meter</title>
<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.js"></script>
<style>
*{box-sizing:border-box;margin:0;padding:0}
:root{--bg:#f0f2f5;--card:#fff;--teal:#1a56db;--cyan:#3b82f6;--text:#1e3a5f;--muted:#6b7e78;--bdr:#e2e8e5;--nav:#0f172a}
body{background:var(--bg);font-family:system-ui,sans-serif;font-size:13px;color:var(--text)}
nav{background:var(--nav);height:50px;display:flex;align-items:center;padding:0 16px;gap:12px;position:sticky;top:0;z-index:99}
.brand{color:#fff;font-weight:700;font-size:15px}.brand span{color:var(--cyan)}
.ntitle{color:rgba(255,255,255,.5);font-size:13px;border-left:1px solid rgba(255,255,255,.1);padding-left:12px;margin-left:4px}
.ml{margin-left:auto;display:flex;align-items:center;gap:8px}
.sbtn{background:var(--cyan);color:#0f172a;font-weight:700;border:none;padding:6px 14px;border-radius:6px;cursor:pointer;font-size:12px}
.lbtn{color:rgba(255,255,255,.7);background:rgba(255,255,255,.07);border:1px solid rgba(255,255,255,.1);padding:5px 11px;border-radius:6px;font-size:12px;text-decoration:none}
.ni{color:rgba(255,255,255,.5);font-size:12px}.ni b{color:rgba(255,255,255,.85)}
.dot{width:7px;height:7px;background:#22c55e;border-radius:50%;display:inline-block;animation:p 2s infinite}
@keyframes p{0%,100%{opacity:1}50%{opacity:.4}}
.pg{padding:12px 16px;display:flex;flex-direction:column;gap:10px}
/* metrics */
.row4{display:grid;grid-template-columns:180px repeat(3,1fr);gap:10px}
@media(max-width:800px){.row4{grid-template-columns:1fr 1fr}}
.mc{background:var(--card);border:1px solid var(--bdr);border-radius:10px;padding:14px 16px}
.mc-l{font-size:11px;color:var(--muted);font-weight:500;margin-bottom:8px;text-transform:uppercase;letter-spacing:.04em}
.mc-v{font-size:26px;font-weight:700;color:var(--text);line-height:1}
.mc-u{font-size:13px;font-weight:400;color:var(--muted);margin-left:2px}
.mc-s{font-size:10px;color:var(--muted);margin-top:6px}
.device{display:flex;align-items:center;justify-content:center}
/* cum */
.row3p{display:grid;grid-template-columns:1fr 1fr 1fr 240px;gap:10px}
@media(max-width:800px){.row3p{grid-template-columns:1fr 1fr}}
.cc{background:var(--card);border:1px solid var(--bdr);border-radius:10px;padding:13px 15px}
.cc-l{font-size:11px;color:var(--muted);margin-bottom:5px;font-weight:500}
.cc-v{font-size:20px;font-weight:700;color:var(--text)}
.cc-u{font-size:11px;color:var(--muted);margin-top:2px}
.cc-t{background:#eff6ff;border-color:rgba(26,86,219,.2)}.cc-t .cc-v{color:var(--teal)}
/* charts */
.row2{display:grid;grid-template-columns:1fr 1fr;gap:10px}
@media(max-width:680px){.row2{grid-template-columns:1fr}}
.chc{background:var(--card);border:1px solid var(--bdr);border-radius:10px;padding:13px 15px}
.ch-h{display:flex;align-items:flex-start;justify-content:space-between;margin-bottom:10px}
.ch-t{font-size:12px;font-weight:600;color:var(--text)}
.ch-s{font-size:10px;color:var(--muted);margin-top:2px}
.ch-f{display:flex;justify-content:flex-end;gap:14px;margin-top:8px;font-size:11px;color:var(--muted)}
.ch-f b{color:var(--text)}
.ld{width:8px;height:8px;border-radius:50%;display:inline-block;margin-right:3px}
/* table+map */
.bot{display:grid;grid-template-columns:1fr 240px;gap:10px}
@media(max-width:800px){.bot{grid-template-columns:1fr}}
.tc{background:var(--card);border:1px solid var(--bdr);border-radius:10px;overflow:hidden}
.th{padding:9px 12px;border-bottom:1px solid var(--bdr);display:flex;align-items:center;justify-content:space-between;font-size:11px;color:var(--muted)}
table{width:100%;border-collapse:collapse}
th{background:#f0f7ff;font-size:10px;font-weight:600;color:var(--muted);text-align:left;padding:7px 10px;border-bottom:1px solid var(--bdr);white-space:nowrap;text-transform:uppercase}
td{font-size:11px;padding:7px 10px;border-bottom:1px solid var(--bdr);color:var(--text);white-space:nowrap;font-family:monospace}
tr:last-child td{border-bottom:none}
tr:hover td{background:#f0f7ff}
.mapc{background:var(--card);border:1px solid var(--bdr);border-radius:10px;overflow:hidden}
.mini-ch{background:var(--card);border:1px solid var(--bdr);border-radius:10px;padding:12px 14px}
.rbtn{background:#1a56db;color:#fff;border:none;padding:6px 13px;border-radius:6px;cursor:pointer;font-size:12px;text-decoration:none;display:inline-flex;align-items:center;gap:5px}
.rbtn:hover{opacity:.88}
.nbtn{background:rgba(255,255,255,.07);color:rgba(255,255,255,.85);border:1px solid rgba(255,255,255,.1);padding:5px 11px;border-radius:6px;cursor:pointer;font-size:14px;position:relative}
.nbtn:hover{background:rgba(255,255,255,.14)}
.al-row{display:flex;align-items:flex-start;gap:10px;padding:10px 14px;border-bottom:1px solid #f0f2f0}
.al-row:last-child{border-bottom:none}
.al-badge{font-size:10px;font-weight:700;padding:3px 8px;border-radius:6px;white-space:nowrap}
.al-warn{background:#fef3c7;color:#d97706}
.al-danger{background:#fee2e2;color:#dc2626}
.al-info{background:#dbeafe;color:#2563eb}
</style></head><body>
<nav>
  <div class="brand">IoT<span>dashboard</span></div>
  <div class="ntitle">Watermeter Monitoring</div>
  <div class="ml">
    <button class="sbtn" onclick="refresh()">⟳ SYNC</button>
    <a href="/api/report" class="rbtn" id="rpbtn">⬇ Download Report</a>
    <button class="nbtn" onclick="toggleNotif()" id="nbell">🔔 <span id="nbadge" style="display:none;background:#e53e3e;color:#fff;border-radius:10px;padding:1px 6px;font-size:10px;margin-left:2px">0</span></button>
    <span class="ni"><span class="dot"></span> <b>Active</b> <span id="ts" style="opacity:.6"></span></span>
    <a href="/logout" class="lbtn">⏻ <span id="uname">user</span></a>
  </div>
</nav>
<!-- Notifications panel -->
<div id="notif-panel" style="display:none;position:fixed;top:52px;right:12px;width:320px;background:#fff;border:1px solid #e2e8e5;border-radius:10px;box-shadow:0 8px 24px rgba(0,0,0,.12);z-index:999">
  <div style="padding:12px 14px;border-bottom:1px solid #e2e8e5;display:flex;align-items:center;justify-content:space-between">
    <span style="font-size:13px;font-weight:600;color:#1e3a5f">Notifications</span>
    <button onclick="clearNotifs()" style="background:none;border:none;color:#6b7e78;font-size:12px;cursor:pointer">Clear all</button>
  </div>
  <div id="notif-list" style="max-height:300px;overflow-y:auto;padding:8px 0">
    <div style="padding:12px 14px;color:#6b7e78;font-size:13px">No alerts yet</div>
  </div>
</div>

<div class="pg">
  <!-- METRICS -->
  <div class="row4">
    <div class="mc device">
      <svg viewBox="0 0 140 90" style="width:130px">
        <rect x="10" y="22" width="120" height="46" rx="8" fill="#0f172a" stroke="#3b82f6" stroke-width="1.5"/>
        <rect x="18" y="30" width="40" height="30" rx="3" fill="#0c1f3f" stroke="#3b82f6" stroke-width=".8"/>
        <text x="38" y="43" font-size="5.5" fill="#3b82f6" text-anchor="middle" font-family="monospace">FLOW</text>
        <text x="38" y="53" font-size="8" fill="#fff" text-anchor="middle" font-family="monospace" id="of">0.0</text>
        <text x="38" y="59" font-size="4" fill="#3b82f6" text-anchor="middle" font-family="monospace">m3/hr</text>
        <rect x="65" y="35" width="55" height="20" rx="3" fill="#0c1f3f" stroke="#3b82f6" stroke-width=".8"/>
        <text x="92" y="48" font-size="6" fill="#3b82f6" text-anchor="middle" font-family="monospace" id="ot">0.000</text>
        <circle cx="3" cy="45" r="10" fill="#0f172a" stroke="#3b82f6" stroke-width="1.5"/>
        <circle cx="137" cy="45" r="10" fill="#0f172a" stroke="#3b82f6" stroke-width="1.5"/>
      </svg>
    </div>
    <div class="mc">
      <div class="mc-l">Velocity</div>
      <div class="mc-v" id="mvel">0.00<span class="mc-u">m/s</span></div>
      <div class="mc-s" id="vel-t">Last update: --</div>
    </div>
    <div class="mc">
      <div class="mc-l">Flow Rate</div>
      <div class="mc-v" id="mflow">0.0<span class="mc-u">m³/hr</span></div>
      <div class="mc-s" id="flow-t">Last update: --</div>
    </div>
    <div class="mc">
      <div class="mc-l">Today Consumption</div>
      <div class="mc-v" id="mcons">0.000<span class="mc-u">m³</span></div>
      <div class="mc-s">Bill: <b>Rs. <span id="mbill">0.00</span></b></div>
    </div>
  </div>

  <!-- CUMULATIVE -->
  <div class="row3p">
    <div class="cc"><div class="cc-l">Positive Cumulative</div><div class="cc-v" id="cpos">0.000</div><div class="cc-u">m³</div></div>
    <div class="cc"><div class="cc-l">Negative Cumulative</div><div class="cc-v" id="cneg">0.000</div><div class="cc-u">m³</div></div>
    <div class="cc cc-t"><div class="cc-l">Cumulative Total</div><div class="cc-v" id="ctot">0.000</div><div class="cc-u">m³</div></div>
    <div class="mini-ch">
      <div class="ch-h"><div><div class="ch-t">Consumption</div><div class="ch-s">Realtime · last 12 hours</div></div></div>
      <div style="height:70px"><canvas id="mb"></canvas></div>
      <div style="font-size:10px;color:var(--muted);margin-top:5px">
        <span style="display:inline-block;width:7px;height:7px;background:#93c5fd;border-radius:50%;margin-right:4px"></span>
        Daily Avg: <b id="mavg">0.000</b> m³
      </div>
    </div>
  </div>

  <!-- CHARTS -->
  <div class="row2">
    <div class="chc">
      <div class="ch-h"><div><div class="ch-t">Velocity</div><div class="ch-s">Realtime · last 30 readings</div></div></div>
      <div style="height:150px"><canvas id="vc"></canvas></div>
      <div class="ch-f"><span><span class="ld" style="background:#93c5fd"></span>Velocity</span><span>Avg <b id="va">0.00</b></span><span>Total <b id="vt">0.00</b></span></div>
    </div>
    <div class="chc">
      <div class="ch-h"><div><div class="ch-t">Flow Rate</div><div class="ch-s">Realtime · last 30 readings</div></div></div>
      <div style="height:150px"><canvas id="fc"></canvas></div>
      <div class="ch-f"><span><span class="ld" style="background:#3b82f6"></span>Flow</span><span>Avg <b id="fa">0.00</b></span><span>Total <b id="ft">0.00</b></span></div>
    </div>
  </div>

  <!-- TABLE + MAP -->
  <div class="bot">
    <div class="tc">
      <div class="th"><span>⏱ Realtime · last day</span></div>
      <div style="overflow-x:auto">
        <table>
          <thead><tr><th>Timestamp</th><th>Flow</th><th>Unit</th><th>Velocity</th><th>Pos. Cum.</th><th>Neg. Cum.</th><th>Total</th><th>Bill (Rs.)</th></tr></thead>
          <tbody id="tb"><tr><td colspan="8" style="text-align:center;color:var(--muted);padding:16px">Waiting for data...</td></tr></tbody>
        </table>
      </div>
    </div>
    <div class="mapc">
      <svg width="100%" height="100%" viewBox="0 0 240 270" style="min-height:250px;display:block">
        <rect width="240" height="270" fill="#eff6ff"/>
        <rect x="0" y="65" width="240" height="14" fill="#fff" opacity=".7"/>
        <rect x="0" y="145" width="240" height="12" fill="#fff" opacity=".7"/>
        <rect x="0" y="205" width="240" height="12" fill="#fff" opacity=".7"/>
        <rect x="60" y="0" width="12" height="270" fill="#fff" opacity=".7"/>
        <rect x="155" y="0" width="10" height="270" fill="#fff" opacity=".7"/>
        <rect x="5" y="5" width="48" height="52" rx="3" fill="#dbeafe" stroke="#93c5fd" stroke-width="1"/>
        <rect x="78" y="5" width="65" height="52" rx="3" fill="#dbeafe" stroke="#93c5fd" stroke-width="1"/>
        <rect x="168" y="5" width="65" height="52" rx="3" fill="#dbeafe" stroke="#93c5fd" stroke-width="1"/>
        <rect x="5" y="85" width="48" height="48" rx="3" fill="#dbeafe" stroke="#93c5fd" stroke-width="1"/>
        <rect x="78" y="85" width="65" height="48" rx="3" fill="#dbeafe" stroke="#93c5fd" stroke-width="1"/>
        <rect x="168" y="85" width="65" height="48" rx="3" fill="#dbeafe" stroke="#93c5fd" stroke-width="1"/>
        <rect x="5" y="165" width="48" height="30" rx="3" fill="#dbeafe" stroke="#93c5fd" stroke-width="1"/>
        <rect x="78" y="165" width="65" height="30" rx="3" fill="#dbeafe" stroke="#93c5fd" stroke-width="1"/>
        <rect x="168" y="165" width="65" height="30" rx="3" fill="#dbeafe" stroke="#93c5fd" stroke-width="1"/>
        <rect x="5" y="225" width="48" height="35" rx="3" fill="#dbeafe" stroke="#93c5fd" stroke-width="1"/>
        <rect x="78" y="225" width="65" height="35" rx="3" fill="#dbeafe" stroke="#93c5fd" stroke-width="1"/>
        <rect x="168" y="225" width="65" height="35" rx="3" fill="#dbeafe" stroke="#93c5fd" stroke-width="1"/>
        <circle cx="120" cy="125" r="12" fill="#e53e3e" opacity=".2"/>
        <circle cx="120" cy="125" r="7" fill="#e53e3e"/>
        <circle cx="120" cy="125" r="2.5" fill="white"/>
        <rect x="128" y="108" width="56" height="16" rx="4" fill="white" stroke="#e2e8e5" stroke-width="1"/>
        <text x="156" y="120" font-size="8" font-family="system-ui" fill="#1e3a5f" text-anchor="middle" font-weight="700">IoT-0003</text>
      </svg>
    </div>
  </div>
</div>

<script>
// charts
const gc='rgba(0,0,0,0.05)',tc='#9ab0a6';
const bo={responsive:true,maintainAspectRatio:false,plugins:{legend:{display:false},tooltip:{enabled:false}},elements:{point:{radius:0}},
  scales:{x:{ticks:{color:tc,font:{size:9},maxTicksLimit:6,autoSkip:true},grid:{color:gc},border:{display:false}},
          y:{ticks:{color:tc,font:{size:9},maxTicksLimit:4},grid:{color:gc},border:{display:false},min:0}}};
const vC=new Chart(document.getElementById('vc'),{type:'line',data:{labels:[],datasets:[{data:[],borderColor:'#93c5fd',backgroundColor:'rgba(96,184,255,0.1)',fill:true,tension:0.4,borderWidth:1.5}]},options:{...bo,scales:{...bo.scales,y:{...bo.scales.y,max:2}}}});
const fC=new Chart(document.getElementById('fc'),{type:'line',data:{labels:[],datasets:[{data:[],borderColor:'#3b82f6',backgroundColor:'rgba(59,130,246,0.1)',fill:true,tension:0.4,borderWidth:1.5}]},options:{...bo,scales:{...bo.scales,y:{...bo.scales.y,max:5}}}});
const mC=new Chart(document.getElementById('mb'),{type:'bar',data:{labels:[],datasets:[{data:[],backgroundColor:'rgba(96,184,255,0.55)',borderRadius:2}]},options:{...bo,scales:{x:{display:false},y:{display:false,min:0}}}});

// state
let cumL=0,vH=[],fH=[],rows=[],tick=0,fl=false,pause=0;
function tariff(l){return l<=10000?0.005:l<=30000?0.012:0.025;}
function fmtT(t){return new Date(t).toLocaleTimeString('en-IN',{hour12:false,hour:'2-digit',minute:'2-digit'});}
function fmtDT(t){return new Date(t).toLocaleString('en-IN',{hour12:false}).replace(',',' ');}
setInterval(()=>{document.getElementById('ts').textContent='('+new Date().toLocaleTimeString()+')';},1000);

// simulate if no hardware
function sim(){
  tick++;
  if(pause>0){pause--;fl=false;}
  else if(!fl&&Math.random()<.22){fl=true;}
  else if(fl&&Math.random()<.12){fl=false;pause=Math.floor(Math.random()*3)+2;}
  const f=fl?(1.2+Math.random()*3.2):0;
  const v=f>0?(f/7.2+Math.random()*.06):0;
  cumL+=f*1000/3600*2;
  return{f:+f.toFixed(2),v:+v.toFixed(3)};
}

async function refresh(){
  let f,v,litres,bill,up;
  try{
    const d=await fetch('/api/latest').then(r=>r.json());
    if(d&&d.flow!=null&&d.flow>0){
      f=d.flow_rate;v=+(f/7.2).toFixed(3);
      litres=d.total_liters||cumL;cumL=litres;
    }else throw 0;
  }catch{
    const s=sim();f=s.f;v=s.v;litres=cumL;
  }
  up=tariff(litres);bill=litres*up;
  const t=new Date().toISOString();
  const lbl=fmtT(t);

  // update metrics
  document.getElementById('mflow').innerHTML=f.toFixed(1)+'<span class="mc-u">m³/hr</span>';
  document.getElementById('mvel').innerHTML=v.toFixed(2)+'<span class="mc-u">m/s</span>';
  document.getElementById('mcons').innerHTML=(litres/1000).toFixed(3)+'<span class="mc-u">m³</span>';
  document.getElementById('mbill').textContent=bill.toFixed(2);
  document.getElementById('cpos').textContent=(litres/1000).toFixed(3);
  document.getElementById('cneg').textContent='0.000';
  document.getElementById('ctot').textContent=(litres/1000).toFixed(3);
  document.getElementById('of').textContent=f.toFixed(1);
  document.getElementById('ot').textContent=(litres/1000).toFixed(3);
  document.getElementById('vel-t').textContent='Last update: '+new Date().toLocaleTimeString();
  document.getElementById('flow-t').textContent='Last update: '+new Date().toLocaleTimeString();

  // charts
  const MAX=30;
  vH.push({t:lbl,v});if(vH.length>MAX)vH.shift();
  fH.push({t:lbl,f});if(fH.length>MAX)fH.shift();
  vC.data.labels=vH.map(x=>x.t);vC.data.datasets[0].data=vH.map(x=>x.v);vC.update('none');
  fC.data.labels=fH.map(x=>x.t);fC.data.datasets[0].data=fH.map(x=>x.f);fC.update('none');

  // mini bar
  const hl=new Date().getHours().toString().padStart(2,'0')+':00';
  const bi=mC.data.labels.indexOf(hl);
  if(bi===-1){mC.data.labels.push(hl);mC.data.datasets[0].data.push(+(f/60*2/1000).toFixed(4));if(mC.data.labels.length>12){mC.data.labels.shift();mC.data.datasets[0].data.shift();}}
  else{mC.data.datasets[0].data[bi]+=+(f/60*2/1000).toFixed(5);}
  mC.update('none');
  const arr=mC.data.datasets[0].data;
  document.getElementById('mavg').textContent=(arr.reduce((a,b)=>a+b,0)/Math.max(1,arr.length)).toFixed(4);

  // stats
  const va=vH.map(x=>x.v),fa=fH.map(x=>x.f);
  document.getElementById('va').textContent=(va.reduce((a,b)=>a+b,0)/Math.max(1,va.length)).toFixed(2);
  document.getElementById('vt').textContent=va.reduce((a,b)=>a+b,0).toFixed(2);
  document.getElementById('fa').textContent=(fa.reduce((a,b)=>a+b,0)/Math.max(1,fa.length)).toFixed(2);
  document.getElementById('ft').textContent=fa.reduce((a,b)=>a+b,0).toFixed(2);

  // table
  rows.unshift({t,f,v,litres,bill});
  if(rows.length>15)rows.pop();
  document.getElementById('tb').innerHTML=rows.map(r=>`
    <tr><td>${fmtDT(r.t)}</td><td>${r.f.toFixed(1)}</td><td>m³/h</td>
    <td>${r.v.toFixed(3)} m/s</td><td>${(r.litres/1000).toFixed(3)}</td>
    <td>0.000</td><td>${(r.litres/1000).toFixed(3)}</td><td>${r.bill.toFixed(2)}</td></tr>`).join('');
}

// load username
fetch('/api/me').then(r=>r.json()).then(d=>{document.getElementById('uname').textContent=d.username;}).catch(()=>{});

// Notifications
let lastAlertId=0, notifOpen=false, notifList=[], notifCount=0;

function toggleNotif(){
  notifOpen=!notifOpen;
  document.getElementById('notif-panel').style.display=notifOpen?'block':'none';
  if(notifOpen){notifCount=0;document.getElementById('nbadge').style.display='none';}
}

function clearNotifs(){
  notifList=[];lastAlertId=0;notifCount=0;
  document.getElementById('notif-list').innerHTML='<div style="padding:12px 14px;color:#6b7e78;font-size:13px">No alerts</div>';
  document.getElementById('nbadge').style.display='none';
}

document.addEventListener('click',function(e){
  if(notifOpen && !document.getElementById('notif-panel').contains(e.target) && e.target.id!=='nbell'){
    notifOpen=false;document.getElementById('notif-panel').style.display='none';
  }
});

const BADGE={'warning':'al-warn','danger':'al-danger','info':'al-info'};
const LABEL={'warning':'Warning','danger':'Alert','info':'Info'};

async function checkAlerts(){
  try{
    const rows=await fetch('/api/alerts/new?since='+lastAlertId).then(r=>r.json());
    if(!rows.length) return;
    rows.forEach(a=>{
      if(a.id>lastAlertId) lastAlertId=a.id;
      notifList.unshift(a);
      notifCount++;
      // browser notification
      if(Notification.permission==='granted'){
        new Notification('Water Meter Alert',{body:a.msg,icon:''});
      }
    });
    if(notifList.length>20) notifList=notifList.slice(0,20);
    // update badge
    if(!notifOpen && notifCount>0){
      document.getElementById('nbadge').style.display='inline';
      document.getElementById('nbadge').textContent=notifCount>9?'9+':notifCount;
    }
    // update panel
    const cls=BADGE; const lbl=LABEL;
    document.getElementById('notif-list').innerHTML=notifList.map(a=>`
      <div class="al-row">
        <span class="al-badge ${cls[a.level]||'al-info'}">${lbl[a.level]||a.level}</span>
        <div>
          <div style="font-size:12px;color:#1e3a5f">${a.msg}</div>
          <div style="font-size:10px;color:#6b7e78;margin-top:2px">${a.ts}</div>
        </div>
      </div>`).join('');
  }catch(e){}
}

// Request browser notification permission
if(Notification.permission==='default') Notification.requestPermission();

refresh();
setInterval(refresh,2000);
setInterval(checkAlerts,3000);
</script></body></html>"""

# ── Routes ───────────────────────────────────────────────────
@app.route("/login", methods=["GET","POST"])
def login():
    if request.method == "POST":
        u = request.form.get("username","").strip()
        p = request.form.get("password","").strip()
        if u in USERS and USERS[u] == p:
            session["user"] = u
            return redirect("/")
        return redirect("/login?error=1")
    return Response(LOGIN, mimetype="text/html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")

@app.route("/")
@protected
def index():
    return Response(DASHBOARD, mimetype="text/html")

@app.route("/api/me")
@protected
def me():
    return jsonify({"username": session["user"]})

@app.route("/api/data", methods=["POST"])
def receive_data():
    data = request.get_json(force=True)
    if not data:
        return jsonify({"error":"no data"}), 400
    flow  = float(data.get("flow_rate",0))
    liters= float(data.get("total_liters",0))
    bill  = float(data.get("total_bill",0))
    price = float(data.get("unit_price",0.005))
    c = db()
    c.execute("INSERT INTO readings (flow,liters,bill,price) VALUES (?,?,?,?)",(flow,liters,bill,price))
    if flow > 8.5:
        c.execute("INSERT INTO alerts (level,msg) VALUES (?,?)","warning","High flow: %.2f L/min"%flow)
    if liters > 100:
        c.execute("INSERT INTO alerts (level,msg) VALUES (?,?)","danger","High usage: %.1f L"%liters)
    c.commit(); c.close()
    return jsonify({"status":"ok"})

@app.route("/api/latest")
@protected
def latest():
    c = db()
    row = c.execute("SELECT * FROM readings ORDER BY id DESC LIMIT 1").fetchone()
    c.close()
    return jsonify(dict(row)) if row else jsonify({"flow_rate":0,"total_liters":0,"total_bill":0,"unit_price":0.005})

@app.route("/api/history")
@protected
def history():
    c = db()
    rows = c.execute("SELECT ts,flow,liters,bill FROM readings ORDER BY id DESC LIMIT 30").fetchall()
    c.close()
    return jsonify([dict(r) for r in reversed(rows)])

@app.route("/api/alerts")
@protected
def alerts():
    c = db()
    rows = c.execute("SELECT * FROM alerts ORDER BY id DESC LIMIT 10").fetchall()
    c.close()
    return jsonify([dict(r) for r in rows])


@app.route("/api/alerts/new")
@protected
def alerts_new():
    since = request.args.get("since", "0")
    c = db()
    rows = c.execute("SELECT * FROM alerts WHERE id > ? ORDER BY id DESC LIMIT 5", (since,)).fetchall()
    c.close()
    return jsonify([dict(r) for r in rows])

@app.route("/api/report")
@protected
def report():
    import csv, io
    c = db()
    rows = c.execute("SELECT ts,flow,liters,bill,price FROM readings ORDER BY id DESC").fetchall()
    c.close()
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(["Timestamp","Flow (m3/hr)","Total Liters","Bill (Rs.)","Unit Price (Rs./L)","Velocity (m/s)"])
    for r in rows:
        vel = round(r["flow"]/7.2, 3) if r["flow"] else 0
        w.writerow([r["ts"], round(r["flow"],2), round(r["liters"],4), round(r["bill"],3), round(r["price"],5), vel])
    output = out.getvalue()
    return Response(output, mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=water_meter_report.csv"})

if __name__ == "__main__":
    init_db()
    print("")
    print("  Water Meter --> http://localhost:8080/login")
    print("  username: admin   password: admin123")
    print("  username: user1   password: water456")
    print("")
import os
port = int(os.environ.get("PORT", 8080))
app.run(host="0.0.0.0", port=port, debug=False)
