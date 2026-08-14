from pathlib import Path
import hashlib,json,shutil,urllib.request,zipfile,subprocess,sys
ROOT=Path.cwd();SRC=ROOT/'_1010.zip';WORK=ROOT/'_1011';BASE='https://raw.githubusercontent.com/topaloglusarraf-afk/topaloglu-updates/main/'
urllib.request.urlretrieve(BASE+'update-10.1.0.zip',SRC);shutil.rmtree(WORK,ignore_errors=True);WORK.mkdir()
with zipfile.ZipFile(SRC,'r') as z:z.extractall(WORK)
app=WORK/'Topaloglu-Pazaryeri-Merkezi'

p=app/'app/main.py';s=p.read_text(encoding='utf-8')
idx=s.find('@app.get("/api/operations/overview")');needle='    products=db.list_products()\n    checks=db.list_checks()\n';pos=s.find(needle,idx)
if idx<0 or pos<0:raise SystemExit('overview patch point missing')
insert='''    products=db.list_products()\n    checks=db.list_checks()\n    all_markets=["Trendyol","Hepsiburada","N11","Idefix","Pazarama"]\n    raw_selected=db.runtime_all().get("price_protection_selected_markets")\n    if raw_selected is None: selected_markets=set(all_markets)\n    elif not str(raw_selected).strip(): selected_markets=set()\n    else: selected_markets={x.strip() for x in str(raw_selected).split(",") if x.strip()}\n    checks=[x for x in checks if x.get("marketplace") in selected_markets]\n'''
s=s[:pos]+s[pos:].replace(needle,insert,1)
start=s.find('def price_protection_markets_save(');end=s.find('@app.get("/api/update/check")',start)
if start<0 or end<0:raise SystemExit('market API boundaries missing')
block='''def price_protection_markets_save(payload: dict):\n    all_markets=["Trendyol","Hepsiburada","N11","Idefix","Pazarama"]\n    incoming=payload.get("selected")\n    if not isinstance(incoming,list): raise HTTPException(400,"selected listesi gerekli.")\n    selected=[x for x in all_markets if x in incoming]\n    previous_raw=db.runtime_all().get("price_protection_selected_markets")\n    previous=set(all_markets) if previous_raw is None else {x.strip() for x in str(previous_raw).split(",") if x.strip()}\n    removed=[x for x in all_markets if x in previous and x not in selected]\n    for name in removed: db.clear_market(name)\n    db.runtime_set("price_protection_selected_markets", ",".join(selected))\n    return {"ok":True,"selected":selected,"cleared":removed}\n\n@app.post("/api/price-protection/markets/reset")\ndef price_protection_markets_reset():\n    for name in ["Trendyol","Hepsiburada","N11","Idefix","Pazarama"]: db.clear_market(name)\n    db.runtime_set("price_protection_selected_markets", "")\n    return {"ok":True,"selected":[]}\n\n@app.post("/api/price-protection/critical/reset")\ndef price_protection_critical_reset():\n    all_markets=["Trendyol","Hepsiburada","N11","Idefix","Pazarama"]\n    raw=db.runtime_all().get("price_protection_selected_markets")\n    selected=all_markets if raw is None else [x for x in all_markets if x in {v.strip() for v in str(raw).split(",") if v.strip()}]\n    if selected:\n        marks=",".join("?" for _ in selected)\n        with db.conn() as c:\n            cur=c.execute(f"DELETE FROM market_prices WHERE status IN ('LOSS','CRITICAL','WARNING') AND marketplace IN ({marks})",selected);cleared=cur.rowcount\n    else: cleared=0\n    db.runtime_set("critical_reset_at", datetime.now().isoformat(timespec="seconds"))\n    return {"ok":True,"cleared_rows":cleared}\n\n'''
s=s[:start]+block+s[end:];p.write_text(s,encoding='utf-8')

p=app/'app/static/app.js';s=p.read_text(encoding='utf-8')
addon=r'''
// 10.1.1 common-screen controls
(function(){
  async function refresh1011(){
    if(typeof refreshWallboardV1010==='function')return refreshWallboardV1010();
    if(typeof loadOperations==='function')return loadOperations();
    location.reload();
  }
  function mount1011(){
    if(document.getElementById('wallRefresh1011'))return;
    const anchor=document.getElementById('wallCheckBtn')?.parentElement||document.getElementById('wallStatus');
    if(!anchor)return;
    const wrap=document.createElement('div');wrap.style.cssText='display:flex;gap:7px;align-items:center;margin-left:8px';
    wrap.innerHTML='<button id="wallRefresh1011" style="border:1px solid rgba(255,255,255,.1);background:#182230;color:#d2d9e3;border-radius:9px;padding:8px 10px;font-size:8px;font-weight:800;cursor:pointer">Yenile</button><button id="wallReset1011" style="border:1px solid rgba(255,80,88,.22);background:rgba(255,72,82,.06);color:#ff858b;border-radius:9px;padding:8px 10px;font-size:8px;font-weight:800;cursor:pointer">Kritikleri Sıfırla</button>';
    anchor.appendChild(wrap);
    document.getElementById('wallRefresh1011').onclick=async()=>{try{await refresh1011();if(typeof toast==='function')toast('Ortak ekran yenilendi.')}catch(e){if(typeof toast==='function')toast(e.message||'Yenileme başarısız')}};
    document.getElementById('wallReset1011').onclick=async()=>{const b=document.getElementById('wallReset1011');try{b.disabled=true;b.textContent='Sıfırlanıyor…';const r=await req('/api/price-protection/critical/reset',{method:'POST'});await refresh1011();if(typeof toast==='function')toast(`${r.cleared_rows||0} kritik/uyarı kaydı temizlendi.`)}catch(e){if(typeof toast==='function')toast(e.message||'Kayıtlar temizlenemedi')}finally{b.disabled=false;b.textContent='Kritikleri Sıfırla'}};
  }
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',mount1011);else mount1011();
})();
'''
if 'wallRefresh1011' not in s:s+='\n'+addon
p.write_text(s,encoding='utf-8')
subprocess.run([sys.executable,'-m','py_compile',str(app/'app/main.py')],check=True);subprocess.run(['node','--check',str(app/'app/static/app.js')],check=True)
files=[]
for rel in ['app/main.py','app/static/app.js']:
    src=app/rel;target=ROOT/'direct'/'10.1.1'/rel;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,target);files.append({'path':rel,'url':BASE+'direct/10.1.1/'+rel,'sha256':hashlib.sha256(src.read_bytes()).hexdigest()})
(ROOT/'channel.json').write_text(json.dumps({'version':'10.1.1','published_at':'2026-08-14','notes':'Kritik kayıtları sıfırlama, ortak ekran yenileme ve kontrol dışı pazaryeri kayıtlarını temizleme.','files':files},ensure_ascii=False,indent=2),encoding='utf-8')
print('10.1.1 ready')
