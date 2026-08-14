from pathlib import Path
import hashlib, json, shutil, urllib.request, zipfile, re, subprocess, sys

ROOT = Path.cwd()
SOURCE_URL = "https://raw.githubusercontent.com/topaloglusarraf-afk/topaloglu-updates/main/update-10.0.6.zip"
SOURCE = ROOT / "_source-10.0.6.zip"
WORK = ROOT / "_build-10.0.7"
OUT = ROOT / "update-10.0.7.zip"

urllib.request.urlretrieve(SOURCE_URL, SOURCE)
if WORK.exists(): shutil.rmtree(WORK)
WORK.mkdir()
with zipfile.ZipFile(SOURCE, "r") as z: z.extractall(WORK)
app = WORK / "Topaloglu-Pazaryeri-Merkezi"
if not app.exists(): raise SystemExit("Update package root not found")

p = app / "app/service.py"
s = p.read_text(encoding="utf-8")
helper = '''\n\ndef price_protection_selected_markets():\n    """Pazaryeri fiyat kontrolüne dahil edilen kanallar. Boş kayıt = hiçbiri."""\n    all_names=[name for name,_,_ in MARKETS]\n    raw=db.runtime_all().get("price_protection_selected_markets")\n    if raw is None:\n        return set(all_names)\n    raw=str(raw).strip()\n    if raw=="":\n        return set()\n    selected={x.strip() for x in raw.split(",") if x.strip()}\n    return {x for x in selected if x in all_names}\n'''
if "def price_protection_selected_markets" not in s:
    anchor="async def run_single_product(product_code):"
    s=s.replace(anchor, helper+"\n"+anchor)

s=s.replace('''    for name,fetcher,enabled in MARKETS:\n        if not enabled():\n            continue\n        try:''','''    selected_markets=price_protection_selected_markets()\n    for name,fetcher,enabled in MARKETS:\n        if not enabled() or name not in selected_markets:\n            continue\n        try:''',1)
needle='''    for name,fetcher,enabled in MARKETS:\n        if not enabled(): continue\n        try:\n            if name=="Hepsiburada"'''
replace='''    selected_markets=price_protection_selected_markets()\n    for name,fetcher,enabled in MARKETS:\n        if not enabled() or name not in selected_markets: continue\n        try:\n            if name=="Hepsiburada"'''
if needle in s:
    s=s.replace(needle,replace,1)
else:
    raise SystemExit("run_cycle marketplace loop patch point missing")
p.write_text(s, encoding="utf-8")

p = app / "app/main.py"
s = p.read_text(encoding="utf-8")
api = '''\n@app.get("/api/price-protection/markets")\ndef price_protection_markets_get():\n    all_markets=["Trendyol","Hepsiburada","N11","Idefix","Pazarama"]\n    runtime=db.runtime_all()\n    raw=runtime.get("price_protection_selected_markets")\n    if raw is None:\n        selected=all_markets[:]\n    elif str(raw).strip()=="":\n        selected=[]\n    else:\n        selected=[x for x in all_markets if x in {v.strip() for v in str(raw).split(",") if v.strip()}]\n    return {"ok":True,"markets":all_markets,"selected":selected}\n\n@app.post("/api/price-protection/markets")\ndef price_protection_markets_save(payload: dict):\n    all_markets=["Trendyol","Hepsiburada","N11","Idefix","Pazarama"]\n    incoming=payload.get("selected") or []\n    selected=[x for x in all_markets if x in incoming]\n    db.runtime_set("price_protection_selected_markets", ",".join(selected))\n    return {"ok":True,"selected":selected}\n\n@app.post("/api/price-protection/markets/reset")\ndef price_protection_markets_reset():\n    db.runtime_set("price_protection_selected_markets", "")\n    return {"ok":True,"selected":[]}\n\n'''
if "/api/price-protection/markets" not in s:
    anchor='@app.get("/api/update/check")'
    s=s.replace(anchor,api+anchor)

s=s.replace('''"price":x.get("current_price"),"net_margin":x.get("net_margin"),\n                            "suggestion":"Pazaryeri fiyatını kontrol et"''','''"price":x.get("current_price"),"expected_price":x.get("expected_price"),\n                            "difference":x.get("difference"),"net_margin":x.get("net_margin"),\n                            "suggestion":"Pazaryeri fiyatını kontrol et"''')
p.write_text(s, encoding="utf-8")

p=app/"app/static/index.html"
s=p.read_text(encoding="utf-8")
s=s.replace("Pazaryeri Merkezi v10.0.6","Pazaryeri Merkezi v10.0.7")
s=s.replace("/static/style.css?v=10.0.6","/static/style.css?v=10.0.7")
s=s.replace("/static/app.js?v=10.0.6","/static/app.js?v=10.0.7")
selector='''\n      <section class="protection-picker glass" id="protectionPicker">\n        <div class="protection-picker-copy"><span>FİYAT KORUMA KAPSAMI</span><b>Hangi pazaryerleri kontrol edilsin?</b></div>\n        <div class="protection-market-pills" id="protectionMarketPills"></div>\n        <div class="protection-picker-actions">\n          <button id="protectionAllBtn" class="protection-action">Tümünü Seç</button>\n          <button id="protectionResetBtn" class="protection-action danger">Tümünü Sıfırla</button>\n        </div>\n      </section>\n'''
if 'id="protectionPicker"' not in s:
    anchor='<section class="market-grid" id="marketStrip"></section>'
    s=s.replace(anchor,selector+'\n      '+anchor)
p.write_text(s, encoding="utf-8")

p=app/"app/static/app.js"
s=p.read_text(encoding="utf-8")
selection_js=r'''\nlet PRICE_PROTECTION_SELECTED=new Set(markets);\nasync function loadPriceProtectionMarkets(){\n  try{\n    const r=await req('/api/price-protection/markets');\n    PRICE_PROTECTION_SELECTED=new Set(r.selected||[]);\n    renderPriceProtectionMarkets();\n  }catch(e){console.error('Fiyat koruma kapsamı alınamadı',e)}\n}\nfunction renderPriceProtectionMarkets(){\n  const box=$('#protectionMarketPills');if(!box)return;\n  box.innerHTML=markets.map(m=>`<button class="protection-market-pill ${PRICE_PROTECTION_SELECTED.has(m)?'active':''}" data-protection-market="${m}"><i></i>${m}</button>`).join('');\n  box.querySelectorAll('[data-protection-market]').forEach(btn=>btn.onclick=async()=>{\n    const m=btn.dataset.protectionMarket;\n    if(PRICE_PROTECTION_SELECTED.has(m))PRICE_PROTECTION_SELECTED.delete(m);else PRICE_PROTECTION_SELECTED.add(m);\n    await savePriceProtectionMarkets();\n  });\n}\nasync function savePriceProtectionMarkets(){\n  const r=await req('/api/price-protection/markets',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({selected:[...PRICE_PROTECTION_SELECTED]})});\n  PRICE_PROTECTION_SELECTED=new Set(r.selected||[]);renderPriceProtectionMarkets();\n  toast(PRICE_PROTECTION_SELECTED.size?`${PRICE_PROTECTION_SELECTED.size} pazaryeri kontrol edilecek.`:'Tüm pazaryeri kontrolleri durduruldu.');\n}\nfunction bindProtectionPicker(){\n  $('#protectionAllBtn')?.addEventListener('click',async()=>{PRICE_PROTECTION_SELECTED=new Set(markets);await savePriceProtectionMarkets()});\n  $('#protectionResetBtn')?.addEventListener('click',async()=>{\n    const r=await req('/api/price-protection/markets/reset',{method:'POST'});\n    PRICE_PROTECTION_SELECTED=new Set(r.selected||[]);renderPriceProtectionMarkets();toast('Pazaryeri kontrol seçimi sıfırlandı.');\n  });\n  loadPriceProtectionMarkets();\n}\nif(document.readyState==='loading')document.addEventListener('DOMContentLoaded',bindProtectionPicker);else bindProtectionPicker();\n'''
if "let PRICE_PROTECTION_SELECTED" not in s:
    s += "\n"+selection_js

start=s.find("function renderWallAlerts(rows){")
end=s.find("\nfunction renderWallMarkets",start)
if start<0 or end<0: raise SystemExit("renderWallAlerts block missing")
new_renderer=r'''function renderWallAlerts(rows){\n  const list=$('#wallAlertList'); if(!list)return;\n  const title=$('#wallListTitle');\n  if(!rows.length){\n    if(title)title.textContent='Aktif fiyat alarmı yok';\n    list.innerHTML=`<div class="wall-empty wall-empty-premium"><div class="wall-checkmark">✓</div><div><b>Fiyatlar güvende</b><span>Kritik veya uyarı seviyesinde aktif fiyat kaydı yok.</span></div></div>`;\n    return;\n  }\n  const criticalCount=rows.filter(x=>['LOSS','CRITICAL'].includes(x.status)).length;\n  if(title)title.textContent=criticalCount?`${criticalCount} kritik fiyat hatası`:`${rows.length} fiyat uyarısı`;\n  list.innerHTML=rows.slice(0,12).map((x,i)=>{\n    const isCritical=['LOSS','CRITICAL'].includes(x.status);\n    const diff=Number(x.difference||0);\n    const expected=x.expected_price;\n    return `<article class="wall-risk-card ${isCritical?'critical':'warning'}">\n      <div class="wall-risk-rank">${String(i+1).padStart(2,'0')}</div>\n      <div class="wall-risk-main"><div class="wall-risk-top"><span class="wall-risk-market">${escapeHtml(x.marketplace||'—')}</span><span class="wall-risk-status">${statusLabel(x.status)}</span></div><h3>${escapeHtml(x.name||'Ürün adı yok')}</h3><code>${escapeHtml(x.barcode||x.product_code||'—')}</code></div>\n      <div class="wall-risk-prices"><div><span>PAZARYERİ</span><strong>${money(x.price)}</strong></div><div><span>BEKLENEN</span><strong>${expected!=null?money(expected):'—'}</strong></div></div>\n      <div class="wall-risk-diff ${diff<0?'negative':'positive'}"><span>FARK</span><strong>${x.difference!=null?money(x.difference):x.net_margin!=null?money(x.net_margin):'—'}</strong></div>\n    </article>`;\n  }).join('');\n}\n'''
s=s[:start]+new_renderer+s[end:]
old="const on=!!H.connections[n], s=D.by_market[n]||{}, r=D.runtime||{};"
new="const on=!!H.connections[n], selected=PRICE_PROTECTION_SELECTED.has(n), s=D.by_market[n]||{}, r=D.runtime||{};"
s=s.replace(old,new)
s=s.replace('`<article class="market-card glass ${health}">','`<article class="market-card glass ${health} ${selected?\'\':\'market-excluded\'}">')
s=s.replace("${on?'Bağlı':'Bağlantı bekliyor'}","${!selected?'Kontrol dışı':on?'Bağlı':'Bağlantı bekliyor'}",1)
p.write_text(s, encoding="utf-8")

p=app/"app/static/style.css"
s=p.read_text(encoding="utf-8")
s += r'''\n.protection-picker{margin:12px 14px;padding:13px 15px;display:grid;grid-template-columns:auto 1fr auto;align-items:center;gap:16px;border-radius:16px}.protection-picker-copy{display:flex;flex-direction:column;gap:3px}.protection-picker-copy span{font-size:7px;letter-spacing:.13em;color:#8290a4}.protection-picker-copy b{font-size:10px}.protection-market-pills{display:flex;gap:7px;justify-content:center;flex-wrap:wrap}.protection-market-pill{border:1px solid rgba(255,255,255,.08);background:#151d29;color:#778397;border-radius:999px;padding:8px 11px;font-size:8px;font-weight:700;cursor:pointer}.protection-market-pill i{display:inline-block;width:7px;height:7px;border-radius:50%;background:#485465;margin-right:6px}.protection-market-pill.active{color:#eafbf5;border-color:rgba(68,215,154,.32);background:rgba(68,215,154,.08)}.protection-market-pill.active i{background:#44d79a;box-shadow:0 0 10px rgba(68,215,154,.55)}.protection-picker-actions{display:flex;gap:6px}.protection-action{border:1px solid rgba(255,255,255,.08);background:#1a2330;color:#c4ccd7;border-radius:9px;padding:8px 10px;font-size:7px;font-weight:700;cursor:pointer}.protection-action.danger{color:#ff8b8b;border-color:rgba(255,86,86,.2)}.market-card.market-excluded{opacity:.42;filter:saturate(.45)}\n.wall-status.wall-critical{border-color:rgba(255,69,69,.52)!important;background:radial-gradient(circle at 8% 50%,rgba(255,62,62,.22),transparent 22%),linear-gradient(115deg,rgba(88,13,20,.68),rgba(16,23,34,.98) 58%)!important;box-shadow:0 0 0 1px rgba(255,65,65,.12),0 0 46px rgba(255,34,34,.14)}.wall-status.wall-critical .wall-status-light{background:#ff3c48!important;box-shadow:0 0 0 12px rgba(255,60,72,.08),0 0 40px rgba(255,60,72,.7)!important}.has-critical-price .wall-status.wall-critical{animation:criticalPanelPulse 1.35s ease-in-out infinite}@keyframes criticalPanelPulse{0%,100%{box-shadow:0 0 0 1px rgba(255,65,65,.14),0 0 28px rgba(255,34,34,.10)}50%{box-shadow:0 0 0 2px rgba(255,65,65,.38),0 0 58px rgba(255,34,34,.26)}}.wall-alert-list{display:grid!important;gap:8px!important;padding:12px!important;align-content:start}.wall-risk-card{display:grid;grid-template-columns:42px minmax(240px,1fr) minmax(220px,.8fr) 130px;align-items:center;gap:12px;padding:13px 15px;border-radius:14px;background:#111925;border:1px solid rgba(255,255,255,.06)}.wall-risk-card.critical{border-color:rgba(255,71,71,.22);background:linear-gradient(90deg,rgba(95,18,25,.24),#111925 22%)}.wall-risk-card.warning{border-color:rgba(245,180,61,.18)}.wall-risk-rank{font-size:14px;font-weight:900;color:#475468}.wall-risk-card.critical .wall-risk-rank{color:#ff5a63}.wall-risk-top{display:flex;gap:7px;align-items:center;margin-bottom:4px}.wall-risk-market,.wall-risk-status{font-size:7px;font-weight:800;border-radius:999px;padding:4px 7px}.wall-risk-market{background:#1b2635;color:#aab5c5}.wall-risk-card.critical .wall-risk-status{background:rgba(255,69,78,.12);color:#ff767d}.wall-risk-card.warning .wall-risk-status{background:rgba(245,180,61,.12);color:#f5c15d}.wall-risk-main h3{font-size:10px;margin:0 0 4px;color:#edf2f8}.wall-risk-main code{font-size:7px;color:#77859a;background:none}.wall-risk-prices{display:grid;grid-template-columns:1fr 1fr;gap:8px}.wall-risk-prices div,.wall-risk-diff{padding:8px 10px;border-radius:10px;background:rgba(255,255,255,.025)}.wall-risk-prices span,.wall-risk-diff span{display:block;font-size:6px;letter-spacing:.08em;color:#6f7d91;margin-bottom:3px}.wall-risk-prices strong,.wall-risk-diff strong{font-size:10px}.wall-risk-diff.negative strong{color:#ff646d}.wall-risk-diff.positive strong{color:#f0bd58}.wall-empty-premium{display:flex!important;align-items:center;justify-content:center;gap:12px;min-height:170px!important}.wall-empty-premium .wall-checkmark{width:40px;height:40px;display:grid;place-items:center;border-radius:50%;background:rgba(65,211,151,.10);color:#45d59a;font-size:18px}@media(max-width:1000px){.protection-picker{grid-template-columns:1fr}.protection-market-pills{justify-content:flex-start}.wall-risk-card{grid-template-columns:34px 1fr}.wall-risk-prices,.wall-risk-diff{grid-column:2}}\n'''
p.write_text(s, encoding="utf-8")

(app/"VERSION").write_text("10.0.7", encoding="utf-8")
p=app/"README.md"
s=p.read_text(encoding="utf-8").replace("10.0.6","10.0.7")
s += "\n\n## 10.0.7 — Fiyat koruma kapsamı ve kritik ekran\n- Pazaryerleri tek tek fiyat kontrolüne dahil/haric edilebilir.\n- Tümünü Seç ve Tümünü Sıfırla kontrolleri eklendi; seçimler SQLite runtime içinde kalıcıdır.\n- Otomatik 5 dakikalık kontrol ve tek ürün kontrolü seçili pazaryerlerine uyar.\n- Kritik ortak ekran ve bozuk fiyat kartları sade, uzaktan okunabilir şekilde yenilendi.\n"
p.write_text(s, encoding="utf-8")

for py in app.rglob("*.py"):
    subprocess.run([sys.executable,"-m","py_compile",str(py)],check=True)
try:
    subprocess.run(["node","--check",str(app/"app/static/app.js")],check=True)
except FileNotFoundError:
    pass

if OUT.exists(): OUT.unlink()
with zipfile.ZipFile(OUT,"w",zipfile.ZIP_DEFLATED) as z:
    for f in app.rglob("*"):
        if f.is_file() and "__pycache__" not in f.parts:
            z.write(f,Path("Topaloglu-Pazaryeri-Merkezi")/f.relative_to(app))
sha=hashlib.sha256(OUT.read_bytes()).hexdigest()
manifest={"version":"10.0.7","published_at":"2026-08-14","notes":"Pazaryeri kontrol kapsamı seçilebilir hale getirildi; kritik hata ekranı ve sorunlu fiyat kartları yeniden tasarlandı.","package_url":"https://raw.githubusercontent.com/topaloglusarraf-afk/topaloglu-updates/main/update-10.0.7.zip","sha256":sha}
(ROOT/"latest.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding="utf-8")
shutil.rmtree(WORK,ignore_errors=True); SOURCE.unlink(missing_ok=True)
print("Built",OUT,sha)
