#!/usr/bin/env python3
"""Adds the 'Review now' button (architect / orchestrator ad-hoc review) to the three dashboards after they are generated. Idempotent. Run from run_batch.sh after founder3d.py."""
import os
D = os.path.dirname(os.path.abspath(__file__))
MARK = "<!--review-now-->"
SNIP = MARK + r"""<style>#rv{position:fixed;left:16px;bottom:calc(env(safe-area-inset-bottom,0px) + 128px);z-index:60;font:13px -apple-system,BlinkMacSystemFont,"SF Pro Text",Helvetica,Arial,sans-serif;color:#1D1D1F}
#rv .p{border:0;border-radius:999px;padding:9px 15px;font:600 13px inherit;background:rgba(255,255,255,.88);-webkit-backdrop-filter:blur(18px);backdrop-filter:blur(18px);box-shadow:0 2px 12px rgba(0,0,0,.14),0 0 0 .5px rgba(0,0,0,.08);cursor:pointer}
#rv .b{display:none;margin-bottom:8px;width:min(300px,calc(100vw - 32px));padding:12px;border-radius:18px;background:rgba(255,255,255,.94);-webkit-backdrop-filter:blur(22px);backdrop-filter:blur(22px);box-shadow:0 8px 30px rgba(0,0,0,.18),0 0 0 .5px rgba(0,0,0,.08)}#rv.o .b{display:block}
#rv .r{display:flex;align-items:center;gap:10px;padding:8px 2px}#rv .r+.r{border-top:1px solid #EFEFF4}#rv .r div{flex:1;min-width:0}#rv .r b{display:block;font-size:13.5px}#rv .r small{color:#6E6E73;font-size:11.5px}
#rv .r button{border:0;border-radius:999px;padding:7px 13px;font:600 12.5px inherit;background:#7C5CFA;color:#fff;cursor:pointer}#rv .r button:disabled{background:#E5E5EA;color:#8E8E93}
#rv .h{font-size:11px;color:#8E8E93;padding:2px 2px 0}</style>
<div id="rv"><div class="b"><div class="r"><div><b>Solution architect</b><small id="rva">...</small></div><button data-a="review_architect">Review now</button></div><div class="r"><div><b>Orchestrator</b><small id="rvo">...</small></div><button data-a="review_orchestrator">Review now</button></div><div class="h">Runs a one-off review straight away. Neither can merge or close anything.</div></div><button class="p" id="rvp">Review now</button></div>
<script>(function(){if(window.top!==window)return;var r=document.getElementById('rv');if(!r)return;
function ago(s){if(s==null)return 'not run yet';if(s<90)return 'last ran just now';if(s<5400)return 'last ran '+Math.round(s/60)+' min ago';return 'last ran '+Math.round(s/3600)+' h ago'}
function draw(st){var v=st.review||{};[['architect','rva','review_architect'],['orchestrator','rvo','review_orchestrator']].forEach(function(x){var s=v[x[0]]||{},t=document.getElementById(x[1]),b=r.querySelector('[data-a='+x[2]+']');t.textContent=s.running?'Reviewing now...':ago(s.last_age);b.disabled=!!s.running;b.textContent=s.running?'Running':'Review now'});
var any=(v.architect||{}).running||(v.orchestrator||{}).running;document.getElementById('rvp').textContent=any?'Review running...':'Review now'}
function load(){fetch('/api/control',{cache:'no-store'}).then(function(x){return x.json()}).then(draw).catch(function(){document.getElementById('rva').textContent='Works from the Mac or phone address';document.getElementById('rvo').textContent=''})}
document.getElementById('rvp').onclick=function(){r.classList.toggle('o');load()};
r.addEventListener('click',function(e){var b=e.target.closest('button[data-a]');if(!b||b.disabled)return;b.disabled=true;b.textContent='Starting...';fetch('/api/control',{method:'POST',headers:{'Content-Type':'application/json','X-Lab':'1'},body:JSON.stringify({action:b.dataset.a})}).then(function(x){return x.json()}).then(function(s){draw(s);setTimeout(load,3000)}).catch(load)});
setInterval(function(){if(!document.hidden)load()},5000);load()})();</script>"""
for f in ("status.html", "FounderStatus.html", "FounderView3D.html"):
    p = os.path.join(D, f)
    try: h = open(p, encoding="utf-8").read()
    except OSError: continue
    if MARK in h or "</body>" not in h: continue
    i = h.rfind("</body>"); open(p + ".tmp", "w", encoding="utf-8").write(h[:i] + SNIP + h[i:]); os.replace(p + ".tmp", p)
