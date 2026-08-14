from pathlib import Path
import urllib.request, hashlib, json, subprocess, sys

ROOT=Path.cwd(); OUT=ROOT/'direct'/'10.1.4'; BASE='https://raw.githubusercontent.com/topaloglusarraf-afk/topaloglu-updates/main/'
SOURCES={
 'app/db.py':'direct/10.1.2/app/db.py',
 'app/service.py':'direct/10.1.2/app/service.py',
 'app/main.py':'direct/10.1.3/app/main.py',
 'app/static/app.js':'direct/10.1.3/app/static/app.js',
 'app/static/style.css':'direct/10.1.3/app/static/style.css',
}
for rel,src in SOURCES.items():
    p=OUT/rel; p.parent.mkdir(parents=True,exist_ok=True); p.write_bytes(urllib.request.urlopen(BASE+src).read())

# db.py: strict ET-only product boundary + purge old non-ET records + filter marketplace catalog.
p=OUT/'app/db.py'; s=p.read_text(encoding='utf-8')
marker='def init_db():'
insert='''def _has_et(value):\n    return "ET" in str(value or "").upper()\n\ndef product_has_et(p):\n    # T-Soft tarafında stok kodu farklı alanlarda gelebilir; barkod, ürün kodu veya tedarikçi stok kodundan en az birinde ET zorunlu.\n    return any(_has_et(p.get(k)) for k in ("barcode","product_code","supplier_product_code"))\n\ndef market_row_has_et(r):\n    # Pazaryeri kataloglarında kullanıcı kuralı gereği yalnız barkod veya stok kodunda ET bulunan satırlar tutulur.\n    return _has_et(r.get("barcode")) or _has_et(r.get("stock_code"))\n\ndef purge_non_et_products():\n    with conn() as c:\n        rows=c.execute("""SELECT product_code FROM products WHERE\n            UPPER(COALESCE(barcode,'')) NOT LIKE '%ET%' AND\n            UPPER(COALESCE(product_code,'')) NOT LIKE '%ET%' AND\n            UPPER(COALESCE(supplier_product_code,'')) NOT LIKE '%ET%'""").fetchall()\n        codes=[r["product_code"] for r in rows]\n        if codes:\n            marks=','.join('?' for _ in codes)\n            c.execute(f"DELETE FROM market_prices WHERE product_code IN ({marks})",codes)\n            c.execute(f"DELETE FROM manual_mappings WHERE product_code IN ({marks})",codes)\n            c.execute(f"DELETE FROM products WHERE product_code IN ({marks})",codes)\n        return len(codes)\n\n'''
if insert not in s:
    s=s.replace(marker,insert+marker,1)
# guard upsert
s=s.replace('def upsert_product(p, auto_group):\n    with conn() as c:', 'def upsert_product(p, auto_group):\n    if not product_has_et(p): return False\n    with conn() as c:',1)
# strict list_products
s=s.replace('return [dict(r) for r in c.execute("SELECT * FROM products ORDER BY product_code LIMIT ?",(limit,)).fetchall()]', 'return [dict(r) for r in c.execute("""SELECT * FROM products WHERE UPPER(COALESCE(barcode,\'\')) LIKE \'%ET%\' OR UPPER(COALESCE(product_code,\'\')) LIKE \'%ET%\' OR UPPER(COALESCE(supplier_product_code,\'\')) LIKE \'%ET%\' ORDER BY product_code LIMIT ?""",(limit,)).fetchall()]',1)
# filter marketplace catalogs before storage
old="def replace_catalog(marketplace, rows):\n    with conn() as c:"
new="def replace_catalog(marketplace, rows):\n    rows=[r for r in rows if market_row_has_et(r)]\n    with conn() as c:"
s=s.replace(old,new,1)
p.write_text(s,encoding='utf-8',newline='\n')

# service.py: filter at T-Soft fetch boundary and use runtime tolerance dynamically.
p=OUT/'app/service.py'; s=p.read_text(encoding='utf-8')
old='''async def sync_tsoft():\n    items=await fetch_products()\n    for p in items: db.upsert_product(p,auto_group(p["name"],p["category"]))\n    db.runtime_set("last_tsoft_success",now())\n    db.runtime_set("tsoft_product_count",len(items))\n    db.log("INFO",f"T-Soft senkronu tamamlandı: {len(items)} ürün.")\n    return len(items)'''
new='''async def sync_tsoft():\n    incoming=await fetch_products()\n    items=[p for p in incoming if db.product_has_et(p)]\n    purged=db.purge_non_et_products()\n    for p in items: db.upsert_product(p,auto_group(p["name"],p["category"]))\n    db.runtime_set("last_tsoft_success",now())\n    db.runtime_set("tsoft_product_count",len(items))\n    db.runtime_set("tsoft_non_et_filtered",max(0,len(incoming)-len(items)))\n    db.log("INFO",f"T-Soft senkronu: {len(items)} ET ürün alındı; {len(incoming)-len(items)} ET dışı ürün reddedildi; {purged} eski kayıt temizlendi.")\n    return len(items)'''
if old not in s: raise SystemExit('sync_tsoft patch point missing')
s=s.replace(old,new,1)
s=s.replace('tolerance=float(settings.alert_tolerance_tl or 1000)', 'try:\n        tolerance=float(db.runtime_all().get("alert_tolerance_tl") or 1300)\n    except Exception:\n        tolerance=1300.0',1)
p.write_text(s,encoding='utf-8',newline='\n')

# main.py: one-time 1300 TL seed, no mutation of immutable settings, strict ET filter in HB extension.
p=OUT/'app/main.py'; s=p.read_text(encoding='utf-8')
old='''    db.init_db()\n    try:\n        saved=db.runtime_all().get("alert_tolerance_tl")\n        if saved not in (None,""):\n            settings.alert_tolerance_tl=float(saved)\n    except Exception:\n        pass'''
new='''    db.init_db()\n    purged=db.purge_non_et_products()\n    runtime=db.runtime_all()\n    if runtime.get("tolerance_seed_1014")!="1":\n        db.runtime_set("alert_tolerance_tl","1300")\n        db.runtime_set("tolerance_seed_1014","1")\n        db.log("INFO","Alarm toleransı v10.1.4 ile 1300 TL olarak ayarlandı.","Sistem")\n    if purged:\n        db.log("INFO",f"ET kuralı: {purged} eski ET dışı ürün tamamen temizlendi.","Sistem")'''
if old not in s: raise SystemExit('startup patch point missing')
s=s.replace(old,new,1)
# health value from runtime
s=s.replace('return {"ok":True,"interval":settings.interval_minutes,"alert_tolerance_tl":settings.alert_tolerance_tl,', 'return {"ok":True,"interval":settings.interval_minutes,"alert_tolerance_tl":float(db.runtime_all().get("alert_tolerance_tl") or 1300),',1)
# tolerance GET/POST replace immutable settings use
s=s.replace('return {"ok":True,"value":float(settings.alert_tolerance_tl)}', 'return {"ok":True,"value":float(db.runtime_all().get("alert_tolerance_tl") or 1300)}',1)
s=s.replace('''    settings.alert_tolerance_tl=value\n    db.runtime_set("alert_tolerance_tl",str(value))''','''    db.runtime_set("alert_tolerance_tl",str(value))''',1)
# HB extension: never import rows with no ET in barcode or stock code
needle='''        barcode=str(r.get("barcode") or "").strip(); sku=str(r.get("stock_code") or "").strip(); title=str(r.get("title") or "").strip(); price=r.get("price"); stock=r.get("stock")\n        candidates=[]'''
replace='''        barcode=str(r.get("barcode") or "").strip(); sku=str(r.get("stock_code") or "").strip(); title=str(r.get("title") or "").strip(); price=r.get("price"); stock=r.get("stock")\n        if "ET" not in barcode.upper() and "ET" not in sku.upper():\n            continue\n        candidates=[]'''
if needle not in s: raise SystemExit('HB extension patch point missing')
s=s.replace(needle,replace,1)
p.write_text(s,encoding='utf-8',newline='\n')

# app.js: reliable independent wallboard refresh/reset + new tolerance control default 1300.
p=OUT/'app/static/app.js'; s=p.read_text(encoding='utf-8')
s=s.replace("r.value??1000","r.value??1300")
addon=r'''

/* v10.1.4 — ET-only guard UI + reliable wallboard controls + 1300 TL runtime tolerance */
(function(){
  const q=s=>document.querySelector(s);
  const esc=v=>String(v??'').replace(/[&<>\"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','\"':'&quot;'}[c]));
  const money14=v=>new Intl.NumberFormat('tr-TR',{maximumFractionDigits:2}).format(Number(v||0))+' TL';
  async function api14(url,opt){const r=await fetch(url,opt);let j={};try{j=await r.json()}catch(_){ }if(!r.ok)throw new Error(j.detail||j.message||'İşlem başarısız');return j}
  window.refreshWallboardV1010=async function(){
    const [ops,dash,health]=await Promise.all([api14('/api/operations/overview'),api14('/api/dashboard'),api14('/api/health')]);
    const actions=(ops.actions||[]).filter(x=>['LOSS','CRITICAL','WARNING'].includes(x.status));
    const critical=actions.filter(x=>x.status==='LOSS'||x.status==='CRITICAL').length;
    const warning=actions.filter(x=>x.status==='WARNING').length;
    if(q('#wallCritical'))q('#wallCritical').textContent=critical;
    if(q('#wallWarning'))q('#wallWarning').textContent=warning;
    if(q('#wallProducts'))q('#wallProducts').textContent=ops.stats?.products??dash.stats?.products??0;
    if(q('#wallExcluded'))q('#wallExcluded').textContent=ops.stats?.excluded??0;
    if(q('#wallUpdated'))q('#wallUpdated').textContent=new Date().toLocaleTimeString('tr-TR',{hour:'2-digit',minute:'2-digit'});
    if(q('#tolChip'))q('#tolChip').textContent=money14(health.alert_tolerance_tl??1300);
    const status=q('#wallStatus'); const title=q('#wallTitle'); const msg=q('#wallMessage');
    if(status){status.classList.remove('wall-ok','wall-warning','wall-critical','wall-error');status.classList.add(critical?'wall-critical':warning?'wall-warning':'wall-ok')}
    if(title)title.textContent=critical?critical+' KRİTİK FİYAT HATASI':warning?warning+' UYARI':'Sistem Normal';
    if(msg)msg.textContent=critical?'Acil kontrol gereken fiyat kayıtları var.':warning?'Kontrol edilmesi gereken fiyat sapmaları var.':'Aktif kritik fiyat hatası bulunmuyor.';
    if(q('#wallListTitle'))q('#wallListTitle').textContent=actions.length?actions.length+' aktif fiyat kaydı':'Sorunlu fiyat yok';
    const list=q('#wallAlertList');
    if(list) list.innerHTML=actions.slice(0,40).map(x=>`<article class="wall-alert-card ${x.status==='WARNING'?'warning':'critical'}"><div class="wall-alert-status">${x.status==='WARNING'?'UYARI':'KRİTİK'}</div><div class="wall-alert-main"><b>${esc(x.name||'Ürün')}</b><span>${esc(x.marketplace||'')} · ${esc(x.barcode||x.product_code||'')}</span></div><div class="wall-alert-prices"><span>Mevcut <b>${money14(x.price)}</b></span><span>Beklenen <b>${money14(x.expected_price)}</b></span><strong>${money14(x.difference)}</strong></div></article>`).join('')||'<div class="wall-empty-premium"><b>Fiyatlar güvenli</b><span>Aktif kritik veya uyarı kaydı yok.</span></div>';
    const marketBox=q('#wallMarketHealth');
    if(marketBox){const ms=['Trendyol','Hepsiburada','N11','Idefix','Pazarama'];marketBox.innerHTML=ms.map(m=>{const n=actions.filter(x=>x.marketplace===m).length;return `<span class="wall-market-pill ${n?'risk':'ok'}">${m}<b>${n||'✓'}</b></span>`}).join('')}
    return {ops,dash,health};
  };
  function installControls14(){
    q('#wallTools1013')?.remove();q('#wallRefresh1012')?.remove();q('#wallReset1012')?.remove();q('#wallRefresh1011')?.remove();q('#wallReset1011')?.remove();
    const anchor=q('#wallCheckBtn');if(anchor&&!q('#wallTools1014')){const w=document.createElement('div');w.id='wallTools1014';w.className='wall-tools-1013 wall-tools-1014';w.innerHTML='<button id="wallRefresh1014" type="button">↻ Yenile</button><button id="wallReset1014" class="danger" type="button">Kritikleri Sıfırla</button>';anchor.insertAdjacentElement('afterend',w);q('#wallRefresh1014').onclick=async()=>{const b=q('#wallRefresh1014');b.disabled=true;b.textContent='Yenileniyor…';try{await window.refreshWallboardV1010();if(typeof toast==='function')toast('Kritik ekran güncellendi.')}catch(e){if(typeof toast==='function')toast('Yenileme başarısız: '+e.message)}finally{b.disabled=false;b.textContent='↻ Yenile'}};q('#wallReset1014').onclick=async()=>{const b=q('#wallReset1014');b.disabled=true;b.textContent='Sıfırlanıyor…';try{const r=await api14('/api/price-protection/critical/reset',{method:'POST'});await window.refreshWallboardV1010();if(typeof toast==='function')toast((r.cleared_rows||0)+' kritik/uyarı temizlendi.')}catch(e){if(typeof toast==='function')toast('Sıfırlama başarısız: '+e.message)}finally{b.disabled=false;b.textContent='Kritikleri Sıfırla'}}}
    q('#toleranceControl1013')?.remove(); const host=q('#protectionPicker')||q('#tolChip')?.parentElement;
    if(host&&!q('#toleranceControl1014')){const box=document.createElement('div');box.id='toleranceControl1014';box.className='tolerance-control-1013 tolerance-control-1014';box.innerHTML='<div class="tol-copy"><span>ALARM TOLERANSI</span><b>Fiyat farkı eşiği</b></div><div class="tol-input-wrap"><input id="toleranceInput1014" type="number" min="0" max="100000" step="50" value="1300"><span>TL</span></div><button id="toleranceSave1014" type="button">Kaydet</button>';host.appendChild(box);api14('/api/settings/alert-tolerance').then(r=>{q('#toleranceInput1014').value=r.value??1300});q('#toleranceSave1014').onclick=async()=>{const b=q('#toleranceSave1014'),v=Number(q('#toleranceInput1014').value);if(!Number.isFinite(v)||v<0)return typeof toast==='function'&&toast('Geçerli tolerans girin.');b.disabled=true;try{const r=await api14('/api/settings/alert-tolerance',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({value:v})});q('#tolChip').textContent=money14(r.value);await window.refreshWallboardV1010();if(typeof toast==='function')toast('Alarm toleransı '+money14(r.value)+' olarak kaydedildi.')}catch(e){if(typeof toast==='function')toast('Kaydetme başarısız: '+e.message)}finally{b.disabled=false}}
    }
  }
  function boot14(){installControls14();window.refreshWallboardV1010().catch(()=>{});setTimeout(installControls14,1200)}
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',boot14);else boot14();
})();
'''
s += addon
p.write_text(s,encoding='utf-8',newline='\n')

# style additions
p=OUT/'app/static/style.css'; s=p.read_text(encoding='utf-8')
s += '''\n/* v10.1.4 */\n.wall-tools-1014{display:flex;gap:8px;align-items:center;margin-left:8px}.wall-tools-1014 button{cursor:pointer}.wall-alert-card{display:grid;grid-template-columns:90px minmax(220px,1fr) minmax(320px,.8fr);gap:18px;align-items:center;padding:16px 18px;margin:9px 0;border:1px solid rgba(255,255,255,.07);border-radius:16px;background:rgba(10,16,24,.72)}.wall-alert-card.critical{box-shadow:inset 3px 0 #ff4d5a}.wall-alert-card.warning{box-shadow:inset 3px 0 #e8b84f}.wall-alert-status{font-size:11px;font-weight:900;letter-spacing:.12em}.wall-alert-card.critical .wall-alert-status{color:#ff737d}.wall-alert-card.warning .wall-alert-status{color:#e8b84f}.wall-alert-main{display:flex;flex-direction:column;gap:5px}.wall-alert-main b{font-size:14px}.wall-alert-main span{opacity:.62;font-size:11px}.wall-alert-prices{display:flex;justify-content:flex-end;align-items:center;gap:18px}.wall-alert-prices span{display:flex;flex-direction:column;font-size:9px;opacity:.7}.wall-alert-prices span b{font-size:12px;opacity:1}.wall-alert-prices>strong{font-size:14px}.wall-empty-premium{padding:36px;text-align:center;border:1px dashed rgba(255,255,255,.08);border-radius:18px}.wall-empty-premium b,.wall-empty-premium span{display:block}.wall-empty-premium span{margin-top:5px;opacity:.55}.wall-market-pill{display:inline-flex;gap:7px;align-items:center}.wall-market-pill.ok b{color:#55d99b}.wall-market-pill.risk b{color:#ff6d78}.tolerance-control-1014{border-color:rgba(201,163,83,.28)!important;background:linear-gradient(135deg,rgba(201,163,83,.09),rgba(255,255,255,.02))!important}@media(max-width:900px){.wall-alert-card{grid-template-columns:1fr}.wall-alert-prices{justify-content:flex-start;flex-wrap:wrap}}\n'''
p.write_text(s,encoding='utf-8',newline='\n')

# syntax validation
subprocess.run([sys.executable,'-m','py_compile',str(OUT/'app/db.py'),str(OUT/'app/service.py'),str(OUT/'app/main.py')],check=True)
subprocess.run(['node','--check',str(OUT/'app/static/app.js')],check=True)

files=[]
for rel in SOURCES:
    f=OUT/rel; files.append({'path':rel,'url':BASE+'direct/10.1.4/'+rel,'sha256':hashlib.sha256(f.read_bytes()).hexdigest()})
channel={'version':'10.1.4','published_at':'2026-08-14','notes':'Alarm toleransı 1300 TL; panelden tolerans kaydı düzeltildi; kritik Yenile/Sıfırla düzeltildi; barkod veya stok kodunda ET olmayan ürünler tamamen reddedilir ve eski kayıtlar temizlenir.','files':files}
(ROOT/'channel.json').write_text(json.dumps(channel,ensure_ascii=False,indent=2),encoding='utf-8',newline='\n')
