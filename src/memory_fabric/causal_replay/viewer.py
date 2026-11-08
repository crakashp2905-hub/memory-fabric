"""Render a self-contained, local-only CDM timeline viewer."""

from __future__ import annotations

__stability__ = "experimental"

import json
from typing import Any


def render(document: dict[str, Any]) -> str:
    payload = json.dumps(document, sort_keys=True, separators=(",", ":"))
    encoded = payload.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
    return """<!doctype html>
<html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>Memory Fabric · Decision replay</title>
<style>
*{box-sizing:border-box}body{font:16px/1.55 system-ui,sans-serif;max-width:1180px;margin:2rem auto;padding:0 1rem;color:#182536;background:#f5f7fa}
h1{font-size:1.8rem;line-height:1.2;margin:.3rem 0}.eyebrow{color:#176b62;font-weight:700;letter-spacing:.08em;text-transform:uppercase;font-size:.75rem}.note,.muted{color:#5b6878}
.hero,.step,.guide{background:#fff;border:1px solid #dce3eb;border-radius:14px;padding:1.1rem 1.3rem}.hero{border-top:4px solid #16766b;margin:1rem 0 1.25rem}.guide{margin:1.25rem 0}.guide ol{padding-left:1.3rem}.guide li{margin:.3rem 0}.timeline{display:grid;gap:.8rem}.step{box-shadow:0 2px 8px #172a3a0a}
.step h2{font-size:1.05rem;margin:0 0 .35rem}.meta{font-size:.82rem;color:#536273;overflow-wrap:anywhere}.belief{display:grid;grid-template-columns:minmax(120px,1fr) 3fr auto;gap:.7rem;align-items:center;margin:.5rem 0}.bar{height:9px;background:#e9eef5;border-radius:8px;overflow:hidden}.bar i{display:block;height:100%;background:#3177bd}.badge,.status{display:inline-block;border-radius:999px;padding:.15rem .6rem;background:#fff3d6;color:#795400;font-size:.8rem;font-weight:650}.diverge{border-color:#d19b32;background:#fffdf7}
pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#f6f8fb;padding:.75rem;border-radius:8px;font-size:.82rem}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:.7rem}.tile{padding:.8rem;background:#f6f8fb;border-radius:10px}.tile strong{display:block}.foot{font-size:.84rem;color:#5b6878;margin:1.2rem 0}
</style>
<header class="hero"><div class="eyebrow">Memory Fabric · inspectable memory</div><h1>See what informed a decision</h1><p class="note">Memory Fabric helps agents reuse relevant context, preserve where it came from, and review how evidence changed a proposal. This local timeline makes that process visible.</p><div class="grid"><div class="tile"><strong>Traceable evidence</strong>See which recorded items were present at each step.</div><div class="tile"><strong>Belief changes</strong>Follow how the modeled belief shifted over time.</div><div class="tile"><strong>Reviewable alternatives</strong>Compare a hypothetical replay with the recorded path.</div></div></header>
<section class="guide"><h2>How to use Memory Fabric</h2><ol><li>Connect an agent through a supported adapter and let it save useful, permissioned memories.</li><li>Retrieve context for a task; check source, freshness, and access before relying on it.</li><li>When a decision needs review, open its timeline and inspect the evidence and proposal at each step.</li><li>Use a counterfactual as a review aid, then route any correction through the normal governance workflow.</li></ol><p class="muted">Replay is an explanation tool. It does not grant access, change memory authority, or perform real actions.</p></section>
<h2>Decision timeline</h2><p class="note">Evidence, belief state, policy and proposal are shown for each recorded step.</p>
<main id="timeline" class="timeline"></main>
<p class="foot">Local view · no remote assets or network calls · hypothetical replay has no action authority.</p>
<script id="data" type="application/json">""" + encoded + """</script>
<script>
const data=JSON.parse(document.getElementById('data').textContent);
const root=document.getElementById('timeline');
for(const step of data.steps||[]){const card=document.createElement('section');card.className='step';
const title=document.createElement('h2');title.textContent=`Step ${step.step+1} · sequence ${step.sequence}`;card.append(title);
const meta=document.createElement('div');meta.className='meta';meta.textContent=`Policy: ${step.policy} · Proposal: ${step.proposal??'none'} · ${step.fingerprint}`;card.append(meta);
if(step.intervened){card.classList.add('diverge');const badge=document.createElement('span');badge.className='badge';badge.textContent='Hypothetical intervention window';card.append(badge)}
for(const [name,value] of Object.entries(step.belief||{})){const row=document.createElement('div');row.className='belief';const label=document.createElement('span');label.textContent=name;const bar=document.createElement('div');bar.className='bar';const fill=document.createElement('i');fill.style.width=`${Math.max(0,Math.min(1,value))*100}%`;bar.append(fill);const pct=document.createElement('strong');pct.textContent=`${(value*100).toFixed(1)}%`;row.append(label,bar,pct);card.append(row)}
const status=document.createElement('p');status.innerHTML='<span class="status">Proposal only · no action executed</span>';card.append(status);
const evidence=document.createElement('pre');evidence.textContent=JSON.stringify(step.evidence||[],null,2);card.append(evidence);root.append(card)}
</script></html>"""
