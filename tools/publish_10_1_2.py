from pathlib import Path
import hashlib,json,shutil,urllib.request,zipfile,subprocess,sys,re

ROOT=Path.cwd(); SRC=ROOT/'_1010.zip'; WORK=ROOT/'_1012'; BASE='https://raw.githubusercontent.com/topaloglusarraf-afk/topaloglu-updates/main/'
urllib.request.urlretrieve(BASE+'update-10.1.0.zip',SRC)
shutil.rmtree(WORK,ignore_errors=True); WORK.mkdir()
with zipfile.ZipFile(SRC,'r') as z:z.extractall(WORK)
app=WORK/'Topaloglu-Pazaryeri-Merkezi'

# db.py
p=app/'app/db.py';s=p.read_text(encoding='utf-8')
s=s.replace("CREATE TABLE IF NOT EXISTS runtime(key TEXT PRIMARY KEY, value TEXT NOT NULL);",'''CREATE TABLE IF NOT EXISTS runtime(key TEXT PRIMARY KEY, value TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS price_exclusions(
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          match_type TEXT NOT NULL, match_value TEXT NOT NULL,
          mode TEXT NOT NULL DEFAULT 'EXCLUDE', marketplace TEXT NOT NULL DEFAULT '*',
          note TEXT DEFAULT '', enabled INTEGER NOT NULL DEFAULT 1,
          created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS idx_price_exclusions_enabled ON price_exclusions(enabled, mode, marketplace);''')
extra='''

def list_exclusions():
    with conn() as c:return [dict(r) for r in c.execute("SELECT * FROM price_exclusions ORDER BY enabled DESC,id DESC").fetchall()]
def add_exclusion(match_type,match_value,mode="EXCLUDE",marketplace="*",note=""):
    mt=str(match_type or "name").strip().lower(); mt=mt if mt in {"product","name","category"} else "name"
    mv=str(match_value or "").strip()
    if not mv: raise ValueError("Hariç bırakma değeri boş olamaz.")
    md=str(mode or "EXCLUDE").strip().upper(); md=md if md in {"EXCLUDE","SILENT"} else "EXCLUDE"
    mp=str(marketplace or "*").strip() or "*"
    with conn() as c:return c.execute("INSERT INTO price_exclusions(match_type,match_value,mode,marketplace,note,enabled) VALUES(?,?,?,?,?,1)",(mt,mv,md,mp,str(note or "").strip())).lastrowid
def delete_exclusion(rule_id):
    with conn() as c:c.execute("DELETE FROM price_exclusions WHERE id=?",(int(rule_id),))
def toggle_exclusion(rule_id,enabled):
    with conn() as c:c.execute("UPDATE price_exclusions SET enabled=? WHERE id=?",(1 if enabled else 0,int(rule_id)))
def clear_product_market(product_code,marketplace):
    with conn() as c:c.execute("DELETE FROM market_prices WHERE product_code=? AND marketplace=?",(product_code,marketplace))
def _norm_exclusion(v):
    import unicodedata,re
    x=str(v or "").strip().lower().replace("ı","i");x=unicodedata.normalize("NFKD",x);x="".join(ch for ch in x if not unicodedata.combining(ch));return re.sub(r"\\s+"," ",x)
def exclusion_mode(product,marketplace="*"):
    pcode=_norm_exclusion(product.get("product_code"));barcode=_norm_exclusion(product.get("barcode"));supplier=_norm_exclusion(product.get("supplier_product_code"));name=_norm_exclusion(product.get("name"));category=_norm_exclusion(product.get("category"));winner=None
    for r in list_exclusions():
        if not int(r.get("enabled") or 0):continue
        mp=str(r.get("marketplace") or "*")
        if mp not in {"*",marketplace}:continue
        value=_norm_exclusion(r.get("match_value"));mt=r.get("match_type");matched=False
        if mt=="product":matched=value in {pcode,barcode,supplier}
        elif mt=="category":matched=value in category
        else:matched=value in name
        if matched:
            score=(2 if mp==marketplace else 1,2 if r.get("mode")=="EXCLUDE" else 1,int(r.get("id") or 0))
            if winner is None or score>winner[0]:winner=(score,r)
    return winner[1].get("mode") if winner else None
def exclusion_product_counts(products=None):
    products=products if products is not None else list_products();return {"global_excluded":sum(1 for p in products if exclusion_mode(p,"*")=="EXCLUDE"),"rules":len([r for r in list_exclusions() if int(r.get('enabled') or 0)])}
'''
i=s.find('\ndef runtime_set(');s=s[:i]+extra+s[i:];p.write_text(s,encoding='utf-8')

# service.py
p=app/'app/service.py';s=p.read_text(encoding='utf-8')
s=s.replace('''    for p in products:\n        m,method=match_product(p,idx,name,rows)''','''    for p in products:\n        exclusion=db.exclusion_mode(p,name)\n        if exclusion=="EXCLUDE": continue\n        m,method=match_product(p,idx,name,rows)''',1)
s=s.replace('''        row=evaluate(p,m,method,name)\n        db.upsert_market(row)''','''        row=evaluate(p,m,method,name)\n        if exclusion=="SILENT" and row.get("status") in {"LOSS","CRITICAL","WARNING"}:\n            row["status"]="IGNORED";row["error"]="Sessiz izleme kuralı: alarm üretilmedi."\n        db.upsert_market(row)''',1)
s=s.replace('products=[p for p in db.list_products() if float(p.get("stock") or 0)>0]','products=[p for p in db.list_products() if float(p.get("stock") or 0)>0 and db.exclusion_mode(p,"Hepsiburada")!="EXCLUDE"]',1)
s=s.replace('''            trusted+=1\n            row=evaluate(p,m,"WEB_TOPALOGLU","Hepsiburada")\n            db.upsert_market(row)''','''            trusted+=1\n            row=evaluate(p,m,"WEB_TOPALOGLU","Hepsiburada")\n            if db.exclusion_mode(p,"Hepsiburada")=="SILENT" and row.get("status") in {"LOSS","CRITICAL","WARNING"}:row["status"]="IGNORED";row["error"]="Sessiz izleme kuralı: alarm üretilmedi."\n            db.upsert_market(row)''',1)
s=s.replace('''    for name,fetcher,enabled in MARKETS:\n        if not enabled() or name not in selected_markets:\n            continue\n        try:''','''    for name,fetcher,enabled in MARKETS:\n        if not enabled() or name not in selected_markets: continue\n        exclusion=db.exclusion_mode(target,name)\n        if exclusion=="EXCLUDE":\n            result["markets"][name]={"status":"IGNORED","marketplace":name,"error":"Ürün fiyat kontrolünden hariç bırakılmış."};db.clear_product_market(target["product_code"],name);continue\n        try:''',1)
s=s.replace('''                row=base_row(target,None,None,name,"UNRESOLVED","Güvenli eşleşme bulunamadı.") if not market_row else evaluate(target,market_row,method,name)\n                db.upsert_market(row)''','''                row=base_row(target,None,None,name,"UNRESOLVED","Güvenli eşleşme bulunamadı.") if not market_row else evaluate(target,market_row,method,name)\n                if exclusion=="SILENT" and row.get("status") in {"LOSS","CRITICAL","WARNING"}:row["status"]="IGNORED";row["error"]="Sessiz izleme kuralı: alarm üretilmedi."\n                db.upsert_market(row)''',1)
p.write_text(s,encoding='utf-8')

# main.py
p=app/'app/main.py';s=p.read_text(encoding='utf-8')
s=s.replace('''    products=db.list_products()\n    checks=db.list_checks()\n    products_by_code={p["product_code"]:p for p in products}''','''    products=db.list_products()\n    checks=db.list_checks()\n    all_markets=["Trendyol","Hepsiburada","N11","Idefix","Pazarama"]\n    raw_selected=db.runtime_all().get("price_protection_selected_markets")\n    if raw_selected is None:selected_markets=set(all_markets)\n    elif not str(raw_selected).strip():selected_markets=set()\n    else:selected_markets={x.strip() for x in str(raw_selected).split(",") if x.strip()}\n    checks=[x for x in checks if x.get("marketplace") in selected_markets]\n    products_by_code={p["product_code"]:p for p in products}''',1)
s=s.replace('''        "products":len(products),''','''        "products":sum(1 for p in products if db.exclusion_mode(p,"*")!="EXCLUDE"),\n        "all_products":len(products),\n        "excluded":sum(1 for p in products if db.exclusion_mode(p,"*")=="EXCLUDE"),''',1)
start=s.find('@app.post("/api/price-protection/markets")');end=s.find('@app.get("/api/update/check")',start)
api='''@app.post("/api/price-protection/markets")
def price_protection_markets_save(payload: dict):
    all_markets=["Trendyol","Hepsiburada","N11","Idefix","Pazarama"];incoming=payload.get("selected")
    if not isinstance(incoming,list):raise HTTPException(400,"selected listesi gerekli.")
    selected=[x for x in all_markets if x in incoming];raw=db.runtime_all().get("price_protection_selected_markets");previous=set(all_markets) if raw is None else {x.strip() for x in str(raw).split(",") if x.strip()};removed=[x for x in all_markets if x in previous and x not in selected]
    for name in removed:db.clear_market(name)
    db.runtime_set("price_protection_selected_markets", ",".join(selected));return {"ok":True,"selected":selected,"cleared":removed}
@app.post("/api/price-protection/markets/reset")
def price_protection_markets_reset():
    for name in ["Trendyol","Hepsiburada","N11","Idefix","Pazarama"]:db.clear_market(name)
    db.runtime_set("price_protection_selected_markets", "");return {"ok":True,"selected":[]}
@app.post("/api/price-protection/critical/reset")
def price_protection_critical_reset():
    with db.conn() as c:cur=c.execute("DELETE FROM market_prices WHERE status IN ('LOSS','CRITICAL','WARNING')");cleared=cur.rowcount
    return {"ok":True,"cleared_rows":cleared}
@app.get("/api/price-protection/exclusions")
def exclusion_list():
    return {"ok":True,"rules":db.list_exclusions(),"counts":db.exclusion_product_counts(db.list_products())}
@app.post("/api/price-protection/exclusions")
def exclusion_add(payload: dict):
    try:rid=db.add_exclusion(payload.get("match_type"),payload.get("match_value"),payload.get("mode"),payload.get("marketplace"),payload.get("note"))
    except ValueError as e:raise HTTPException(400,str(e))
    if str(payload.get("mode") or "EXCLUDE").upper()=="EXCLUDE":
        rule_market=str(payload.get("marketplace") or "*")
        for product in db.list_products():
            targets=[rule_market] if rule_market!="*" else ["Trendyol","Hepsiburada","N11","Idefix","Pazarama"]
            for market in targets:
                if db.exclusion_mode(product,market)=="EXCLUDE":db.clear_product_market(product["product_code"],market)
    return {"ok":True,"id":rid,"rules":db.list_exclusions()}
@app.delete("/api/price-protection/exclusions/{rule_id}")
def exclusion_delete(rule_id:int):db.delete_exclusion(rule_id);return {"ok":True,"rules":db.list_exclusions()}
@app.post("/api/price-protection/exclusions/{rule_id}/toggle")
def exclusion_toggle(rule_id:int,payload:dict):db.toggle_exclusion(rule_id,bool(payload.get("enabled",True)));return {"ok":True,"rules":db.list_exclusions()}

'''
s=s[:start]+api+s[end:];p.write_text(s,encoding='utf-8')

# index.html
p=app/'app/static/index.html';s=p.read_text(encoding='utf-8').replace('v10.1.0','v10.1.2').replace('style.css?v=10.1.0','style.css?v=10.1.2').replace('app.js?v=10.1.0','app.js?v=10.1.2').replace('<body>','<body class="premium-v2">')
s=s.replace('<article class="wall-kpi neutral"><span>İzlenen Ürün</span><strong id="wallProducts">0</strong><small>T-Soft portföyü</small></article>','<article class="wall-kpi neutral"><span>İzlenen Ürün</span><strong id="wallProducts">0</strong><small>Aktif fiyat koruması</small></article><article class="wall-kpi excluded"><span>Hariç Ürün</span><strong id="wallExcluded">0</strong><small>Alarm dışında</small></article>')
panel='''<section class="exclusion-studio glass" id="exclusionStudio"><div class="exclusion-head"><div><span>AKILLI FİYAT KORUMA</span><h2>Hariç Ürünler & Sessiz İzleme</h2><p>Kalze Set gibi özel ürünleri isim kuralıyla topluca veya tek ürün koduyla alarmdan çıkar.</p></div><div class="exclusion-count"><strong id="excludedRuleCount">0</strong><span>aktif kural</span></div></div><div class="exclusion-form"><select id="exclusionType"><option value="name">Ürün adında geçen</option><option value="product">ET / ürün kodu</option><option value="category">Kategori içerir</option></select><input id="exclusionValue" placeholder="Örn: Kalze Set"><select id="exclusionMode"><option value="EXCLUDE">Tam Hariç</option><option value="SILENT">Sessiz İzle</option></select><select id="exclusionMarket"><option value="*">Tüm pazaryerleri</option><option>Trendyol</option><option>Hepsiburada</option><option>N11</option><option>Idefix</option><option>Pazarama</option></select><button id="exclusionAddBtn" class="premium-action">Kural Ekle</button></div><div class="exclusion-presets"><button data-preset="Kalze Set">+ Kalze Setleri Hariç Tut</button><button data-preset="Hint Set">+ Hint Setleri Hariç Tut</button><span>Hazır kurallar tek tıkla eklenir.</span></div><div id="exclusionRules" class="exclusion-rules"></div></section>'''
s=s.replace('<section class="market-grid" id="marketStrip"></section>',panel+'<section class="market-grid" id="marketStrip"></section>',1);p.write_text(s,encoding='utf-8')

# app.js
p=app/'app/static/app.js';s=p.read_text(encoding='utf-8')
s=s.replace("if($('#wallProducts'))$('#wallProducts').textContent=ops.stats?.products??dash.stats?.products??0;","if($('#wallProducts'))$('#wallProducts').textContent=ops.stats?.products??dash.stats?.products??0;if($('#wallExcluded'))$('#wallExcluded').textContent=ops.stats?.excluded??0;")
s=s.replace("PRICE_PROTECTION_SELECTED=new Set(r.selected||[]);renderPriceProtectionMarkets();toast(PRICE_PROTECTION_SELECTED.size?`${PRICE_PROTECTION_SELECTED.size} pazaryeri aktif.`:'Tüm pazaryeri kontrolleri kapatıldı.')","PRICE_PROTECTION_SELECTED=new Set(r.selected||[]);renderPriceProtectionMarkets();toast(PRICE_PROTECTION_SELECTED.size?`${PRICE_PROTECTION_SELECTED.size} pazaryeri aktif.`:'Tüm pazaryeri kontrolleri kapatıldı.');await refreshWallboardV1010();")
s=s.replace("PRICE_PROTECTION_SELECTED=new Set(r.selected||[]);renderPriceProtectionMarkets();toast('Tüm pazaryeri kontrolleri sıfırlandı.')","PRICE_PROTECTION_SELECTED=new Set(r.selected||[]);renderPriceProtectionMarkets();toast('Tüm pazaryeri kontrolleri sıfırlandı.');await refreshWallboardV1010();")
s+='''

// v10.1.2 premium exclusion studio
let EXCLUSION_RULES=[];const exclusionLabels={product:'Tek ürün',name:'İsim kuralı',category:'Kategori'};
async function loadExclusions1012(){try{const r=await req('/api/price-protection/exclusions');EXCLUSION_RULES=r.rules||[];renderExclusions1012();if($('#excludedRuleCount'))$('#excludedRuleCount').textContent=EXCLUSION_RULES.filter(x=>Number(x.enabled)!==0).length}catch(e){console.error(e)}}
function renderExclusions1012(){const box=$('#exclusionRules');if(!box)return;if(!EXCLUSION_RULES.length){box.innerHTML='<div class="exclusion-empty"><b>Henüz hariç kuralı yok</b><span>Özel fiyatlı ürünleri alarm ekranından çıkarmak için yukarıdan kural ekle.</span></div>';return}box.innerHTML=EXCLUSION_RULES.map(r=>`<article class="exclusion-rule ${Number(r.enabled)?'':'disabled'}"><div class="exclusion-rule-icon">${r.mode==='EXCLUDE'?'×':'◌'}</div><div class="exclusion-rule-main"><div><span>${exclusionLabels[r.match_type]||r.match_type}</span><b>${escapeHtml(r.match_value)}</b></div><small>${r.marketplace==='*'?'Tüm pazaryerleri':escapeHtml(r.marketplace)} · ${r.mode==='EXCLUDE'?'Tam hariç':'Sessiz izle'}</small></div><button data-rule-toggle="${r.id}" data-enabled="${Number(r.enabled)?0:1}">${Number(r.enabled)?'Pasifleştir':'Aktifleştir'}</button><button class="rule-delete" data-rule-delete="${r.id}">Sil</button></article>`).join('');box.querySelectorAll('[data-rule-delete]').forEach(b=>b.onclick=async()=>{await req('/api/price-protection/exclusions/'+b.dataset.ruleDelete,{method:'DELETE'});await loadExclusions1012();await refreshWallboardV1010();toast('Hariç kuralı kaldırıldı.')});box.querySelectorAll('[data-rule-toggle]').forEach(b=>b.onclick=async()=>{await req('/api/price-protection/exclusions/'+b.dataset.ruleToggle+'/toggle',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({enabled:Number(b.dataset.enabled)===1})});await loadExclusions1012();await refreshWallboardV1010()})}
async function addExclusion1012(preset){const value=(preset||$('#exclusionValue')?.value||'').trim();if(!value){toast('Hariç bırakılacak ürün veya kuralı yaz.');return}const payload={match_type:preset?'name':$('#exclusionType').value,match_value:value,mode:preset?'EXCLUDE':$('#exclusionMode').value,marketplace:preset?'*':$('#exclusionMarket').value};const b=$('#exclusionAddBtn');try{if(b)b.disabled=true;await req('/api/price-protection/exclusions',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});if($('#exclusionValue'))$('#exclusionValue').value='';await loadExclusions1012();await refreshWallboardV1010();toast(`${value} kuralı eklendi.`)}catch(e){toast(e.message)}finally{if(b)b.disabled=false}}
function ensureWallTools1012(){const tools=document.querySelector('.wall-tools');if(!tools||$('#wallRefresh1012'))return;const refresh=document.createElement('button');refresh.id='wallRefresh1012';refresh.className='wall-btn subtle';refresh.textContent='Yenile';refresh.onclick=async()=>{await refreshWallboardV1010();toast('Ekran yenilendi.')};const reset=document.createElement('button');reset.id='wallReset1012';reset.className='wall-btn danger';reset.textContent='Kritikleri Sıfırla';reset.onclick=async()=>{reset.disabled=true;try{const r=await req('/api/price-protection/critical/reset',{method:'POST'});await refreshWallboardV1010();toast(`${r.cleared_rows||0} kritik/uyarı temizlendi.`)}catch(e){toast(e.message)}finally{reset.disabled=false}};tools.append(refresh,reset)}
function bindPremium1012(){$('#exclusionAddBtn')?.addEventListener('click',()=>addExclusion1012());$('#exclusionValue')?.addEventListener('keydown',e=>{if(e.key==='Enter')addExclusion1012()});document.querySelectorAll('[data-preset]').forEach(b=>b.onclick=()=>addExclusion1012(b.dataset.preset));ensureWallTools1012();loadExclusions1012()}
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',bindPremium1012);else bindPremium1012();
''';p.write_text(s,encoding='utf-8')

# style.css
p=app/'app/static/style.css';s=p.read_text(encoding='utf-8');s+='''

/* v10.1.2 premium redesign */
.premium-v2{--bg:#07090d;--panel:#0d1118;--panel2:#111720;--gold:#d5aa63;--gold2:#f0cf8d;--text:#f4f0e8;--muted:#858b96;--line:rgba(255,255,255,.07);background:radial-gradient(circle at 72% -10%,rgba(213,170,99,.12),transparent 30%),#07090d;color:var(--text)}
.premium-v2 .sidebar{background:linear-gradient(180deg,#0b0e13,#080a0e);border-right:1px solid rgba(213,170,99,.1);box-shadow:20px 0 50px rgba(0,0,0,.18)}.premium-v2 .brand-icon{background:linear-gradient(145deg,#e6c27e,#8f642d);color:#090806;box-shadow:0 8px 30px rgba(213,170,99,.18)}.premium-v2 .nav.active{background:linear-gradient(90deg,rgba(213,170,99,.14),rgba(213,170,99,.03));border-color:rgba(213,170,99,.16);color:#f3d99e}.premium-v2 .header{backdrop-filter:blur(22px);background:rgba(7,9,13,.72);border-bottom-color:rgba(255,255,255,.045)}
.premium-v2 .btn.primary,.premium-v2 .premium-action{background:linear-gradient(135deg,#e5bf79,#a77837);color:#0a0907;border:0;box-shadow:0 10px 26px rgba(213,170,99,.14);font-weight:900}.premium-v2 .glass,.premium-v2 .panel{background:linear-gradient(145deg,rgba(17,23,32,.94),rgba(10,14,20,.95));border:1px solid rgba(255,255,255,.06);box-shadow:0 22px 70px rgba(0,0,0,.22)}
.premium-v2 .wallboard-view{max-width:1780px;margin:0 auto}.premium-v2 .wall-status{min-height:188px;border-radius:26px;padding:28px 30px;background:radial-gradient(circle at 85% 20%,rgba(213,170,99,.09),transparent 32%),linear-gradient(135deg,#10151d,#090d13);border:1px solid rgba(213,170,99,.09);box-shadow:0 30px 90px rgba(0,0,0,.28)}.premium-v2 .wall-status h1{font-size:clamp(30px,3.2vw,58px);letter-spacing:-.055em}.premium-v2 .wall-status-copy>span{color:var(--gold2);letter-spacing:.18em}.premium-v2 .wall-status.wall-critical{background:radial-gradient(circle at 12% 50%,rgba(255,55,66,.24),transparent 24%),linear-gradient(135deg,#290d12,#0d1016 64%)!important;border-color:rgba(255,83,91,.34)!important}.premium-v2 .wall-status.wall-ok{border-color:rgba(77,211,158,.16)}
.premium-v2 .wall-kpis{grid-template-columns:repeat(4,1fr);gap:12px}.premium-v2 .wall-kpi{border-radius:20px;padding:20px 22px;min-height:130px;background:linear-gradient(145deg,#111720,#0b0f15);border:1px solid rgba(255,255,255,.055)}.premium-v2 .wall-kpi strong{font-size:40px}.premium-v2 .wall-kpi.excluded strong{color:var(--gold2)}.premium-v2 .wall-alert-panel{border-radius:24px;background:linear-gradient(150deg,#0f151e,#090d13);border:1px solid rgba(255,255,255,.055);overflow:hidden}.premium-v2 .wall-risk-card{border-radius:16px;background:linear-gradient(90deg,#121923,#0d131c);border-color:rgba(255,255,255,.055);box-shadow:0 10px 32px rgba(0,0,0,.14)}.premium-v2 .wall-risk-card.critical{background:linear-gradient(90deg,rgba(112,22,30,.32),#111720 30%);border-color:rgba(255,77,86,.23)}
.premium-v2 .protection-picker{border-radius:22px;padding:18px 20px}.premium-v2 .protection-market-pill{padding:10px 14px;background:#0c121a}.premium-v2 .protection-market-pill.active{border-color:rgba(213,170,99,.28);background:rgba(213,170,99,.08);color:#f2d698}.premium-v2 .protection-market-pill.active i{background:var(--gold);box-shadow:0 0 16px rgba(213,170,99,.55)}
.exclusion-studio{margin:12px 14px 16px;padding:22px;border-radius:24px;position:relative;overflow:hidden}.exclusion-studio:before{content:'';position:absolute;inset:0 auto auto 0;width:100%;height:1px;background:linear-gradient(90deg,transparent,rgba(213,170,99,.5),transparent)}.exclusion-head{display:flex;justify-content:space-between;gap:18px;align-items:flex-start}.exclusion-head>div:first-child>span{font-size:7px;letter-spacing:.18em;color:var(--gold2);font-weight:900}.exclusion-head h2{font-size:18px;margin:5px 0}.exclusion-head p{font-size:9px;color:var(--muted);margin:0}.exclusion-count{min-width:92px;text-align:center;padding:12px 16px;border-radius:16px;background:rgba(213,170,99,.055);border:1px solid rgba(213,170,99,.12)}.exclusion-count strong{display:block;font-size:24px;color:var(--gold2)}.exclusion-count span{font-size:7px;color:var(--muted)}
.exclusion-form{display:grid;grid-template-columns:180px minmax(240px,1fr) 150px 170px 130px;gap:8px;margin-top:18px}.exclusion-form input,.exclusion-form select{height:42px;border-radius:11px;border:1px solid rgba(255,255,255,.07);background:#0b1118;color:#e9edf2;padding:0 12px;font-size:9px;outline:none}.exclusion-form input:focus,.exclusion-form select:focus{border-color:rgba(213,170,99,.34);box-shadow:0 0 0 3px rgba(213,170,99,.06)}.premium-action{height:42px;border-radius:11px;cursor:pointer}.exclusion-presets{display:flex;gap:7px;align-items:center;margin-top:10px}.exclusion-presets button{border:1px solid rgba(213,170,99,.12);background:rgba(213,170,99,.045);color:#d9bd86;border-radius:999px;padding:7px 10px;font-size:7px;cursor:pointer}.exclusion-presets span{font-size:7px;color:#606a78;margin-left:5px}
.exclusion-rules{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px;margin-top:15px}.exclusion-rule{display:grid;grid-template-columns:34px minmax(0,1fr) auto auto;align-items:center;gap:10px;padding:11px 12px;border-radius:14px;background:#0b1118;border:1px solid rgba(255,255,255,.05)}.exclusion-rule.disabled{opacity:.42}.exclusion-rule-icon{width:32px;height:32px;border-radius:10px;display:grid;place-items:center;background:rgba(213,170,99,.07);color:var(--gold2);font-size:16px}.exclusion-rule-main>div{display:flex;gap:8px;align-items:center}.exclusion-rule-main span{font-size:6px;text-transform:uppercase;letter-spacing:.1em;color:#6f7a89}.exclusion-rule-main b{font-size:10px}.exclusion-rule-main small{display:block;margin-top:3px;font-size:7px;color:#6c7684}.exclusion-rule button{border:1px solid rgba(255,255,255,.07);background:#111923;color:#9aa5b4;border-radius:8px;padding:7px 8px;font-size:7px;cursor:pointer}.exclusion-rule .rule-delete{color:#ff858b;border-color:rgba(255,90,100,.14)}.exclusion-empty{grid-column:1/-1;text-align:center;padding:24px;border:1px dashed rgba(255,255,255,.07);border-radius:14px}.exclusion-empty b{display:block;font-size:10px}.exclusion-empty span{display:block;margin-top:4px;font-size:8px;color:var(--muted)}.premium-v2 .wall-btn.danger{border-color:rgba(255,81,91,.2);color:#ff8990;background:rgba(255,75,84,.055)}
@media(max-width:1200px){.premium-v2 .wall-kpis{grid-template-columns:repeat(2,1fr)}.exclusion-form{grid-template-columns:1fr 1fr}.exclusion-rules{grid-template-columns:1fr}}@media(max-width:700px){.exclusion-form{grid-template-columns:1fr}.exclusion-head{flex-direction:column}.premium-v2 .wall-kpis{grid-template-columns:1fr 1fr}}
''';p.write_text(s,encoding='utf-8')
(app/'VERSION').write_text('10.1.2',encoding='utf-8')

for py in [app/'app/db.py',app/'app/service.py',app/'app/main.py',app/'app/updater.py']:subprocess.run([sys.executable,'-m','py_compile',str(py)],check=True)
subprocess.run(['node','--check',str(app/'app/static/app.js')],check=True)

files=[]
for rel in ['app/db.py','app/service.py','app/main.py','app/static/index.html','app/static/app.js','app/static/style.css']:
    src=app/rel;target=ROOT/'direct'/'10.1.2'/rel;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,target);files.append({'path':rel,'url':BASE+'direct/10.1.2/'+rel,'sha256':hashlib.sha256(src.read_bytes()).hexdigest()})
channel={'version':'10.1.2','published_at':'2026-08-14','notes':'Ürün/isim/kategori bazlı fiyat kontrolü hariç tutma, sessiz izleme ve premium kontrol odası tasarımı.','files':files}
(ROOT/'channel.json').write_text(json.dumps(channel,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(channel,ensure_ascii=False,indent=2))