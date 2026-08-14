from pathlib import Path
import hashlib,json,urllib.request,subprocess,sys,shutil

ROOT=Path.cwd(); BASE='https://raw.githubusercontent.com/topaloglusarraf-afk/topaloglu-updates/main/'
WORK=ROOT/'_1013'; shutil.rmtree(WORK,ignore_errors=True); WORK.mkdir()
rels=['app/main.py','app/static/app.js','app/static/style.css']
for rel in rels:
    dst=WORK/rel; dst.parent.mkdir(parents=True,exist_ok=True)
    urllib.request.urlretrieve(BASE+'direct/10.1.2/'+rel,dst)

# main.py — persistent runtime tolerance + API
p=WORK/'app/main.py'; s=p.read_text(encoding='utf-8')
old='''async def startup():\n    db.init_db()\n    if not scheduler.running:'''
new='''async def startup():\n    db.init_db()\n    try:\n        saved=db.runtime_all().get("alert_tolerance_tl")\n        if saved not in (None,""):\n            settings.alert_tolerance_tl=float(saved)\n    except Exception:\n        pass\n    if not scheduler.running:'''
if old not in s: raise SystemExit('startup patch point missing')
s=s.replace(old,new,1)
anchor='@app.get("/api/update/check")'
api='''@app.get("/api/settings/alert-tolerance")\ndef alert_tolerance_get():\n    return {"ok":True,"value":float(settings.alert_tolerance_tl)}\n\n@app.post("/api/settings/alert-tolerance")\ndef alert_tolerance_save(payload:dict):\n    try:\n        value=float(payload.get("value"))\n    except Exception:\n        raise HTTPException(400,"Geçerli bir TL tutarı girin.")\n    if value < 0 or value > 100000:\n        raise HTTPException(400,"Alarm toleransı 0 ile 100.000 TL arasında olmalı.")\n    value=round(value,2)\n    settings.alert_tolerance_tl=value\n    db.runtime_set("alert_tolerance_tl",str(value))\n    db.log("INFO",f"Alarm toleransı panelden {value:.2f} TL olarak değiştirildi.","Sistem")\n    return {"ok":True,"value":value}\n\n'''
if anchor not in s: raise SystemExit('update anchor missing')
s=s.replace(anchor,api+anchor,1)
p.write_text(s,encoding='utf-8',newline='\n')

# app.js — hard-working refresh/reset + premium tolerance control
p=WORK/'app/static/app.js'; s=p.read_text(encoding='utf-8')
module=r'''

/* v10.1.3 — runtime tolerance + reliable wall controls */
(function(){
  function money1013(v){return new Intl.NumberFormat('tr-TR',{maximumFractionDigits:2}).format(Number(v||0))+' TL'}
  async function api1013(url,opt){
    const r=await fetch(url,opt);let j={};try{j=await r.json()}catch(_){ }
    if(!r.ok)throw new Error(j.detail||j.message||'İşlem başarısız');return j;
  }
  function ensureTolerance1013(){
    if(document.querySelector('#toleranceControl1013'))return;
    const host=document.querySelector('#protectionPicker')||document.querySelector('.protection-picker')||document.querySelector('#tolChip')?.parentElement;
    if(!host)return;
    const box=document.createElement('div');box.id='toleranceControl1013';box.className='tolerance-control-1013';
    box.innerHTML='<div class="tol-copy"><span>ALARM TOLERANSI</span><b>Fiyat farkı eşiği</b></div><div class="tol-input-wrap"><input id="toleranceInput1013" type="number" min="0" max="100000" step="50" inputmode="decimal"><span>TL</span></div><button id="toleranceSave1013" type="button">Kaydet</button>';
    host.appendChild(box);
    api1013('/api/settings/alert-tolerance').then(r=>{const i=document.querySelector('#toleranceInput1013');if(i)i.value=r.value??1000}).catch(()=>{});
  }
  function ensureWallButtons1013(){
    const anchor=document.querySelector('#wallCheckBtn');if(!anchor)return;
    document.querySelector('#wallTools1013')?.remove();
    document.querySelector('#wallRefresh1011')?.remove();document.querySelector('#wallReset1011')?.remove();
    const w=document.createElement('div');w.id='wallTools1013';w.className='wall-tools-1013';
    w.innerHTML='<button id="wallRefresh1013" type="button">↻ Yenile</button><button id="wallReset1013" class="danger" type="button">Kritikleri Sıfırla</button>';
    anchor.insertAdjacentElement('afterend',w);
  }
  async function saveTolerance1013(btn){
    const i=document.querySelector('#toleranceInput1013');const value=Number(i?.value);
    if(!Number.isFinite(value)||value<0){if(typeof toast==='function')toast('Geçerli bir tolerans girin.');return}
    const old=btn.textContent;btn.disabled=true;btn.textContent='Kaydediliyor…';
    try{const r=await api1013('/api/settings/alert-tolerance',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({value})});
      if(i)i.value=r.value;const chip=document.querySelector('#tolChip');if(chip)chip.textContent=money1013(r.value);
      if(typeof toast==='function')toast('Alarm toleransı '+money1013(r.value)+' olarak kaydedildi.');
    }catch(e){if(typeof toast==='function')toast(e.message)}finally{btn.disabled=false;btn.textContent=old}
  }
  document.addEventListener('click',async function(e){
    const save=e.target.closest('#toleranceSave1013');if(save){e.preventDefault();e.stopImmediatePropagation();await saveTolerance1013(save);return}
    const refresh=e.target.closest('#wallRefresh1013,#wallRefresh1011');if(refresh){
      e.preventDefault();e.stopImmediatePropagation();const old=refresh.textContent;refresh.disabled=true;refresh.textContent='Yenileniyor…';
      try{await Promise.all([api1013('/api/operations/overview'),api1013('/api/dashboard')]);window.location.reload()}
      catch(err){refresh.disabled=false;refresh.textContent=old;if(typeof toast==='function')toast('Yenileme başarısız: '+err.message)}return;
    }
    const reset=e.target.closest('#wallReset1013,#wallReset1011');if(reset){
      e.preventDefault();e.stopImmediatePropagation();const old=reset.textContent;reset.disabled=true;reset.textContent='Sıfırlanıyor…';
      try{const r=await api1013('/api/price-protection/critical/reset',{method:'POST'});if(typeof toast==='function')toast((r.cleared_rows||0)+' kritik/uyarı kaydı temizlendi.');setTimeout(()=>window.location.reload(),250)}
      catch(err){reset.disabled=false;reset.textContent=old;if(typeof toast==='function')toast('Sıfırlama başarısız: '+err.message)}return;
    }
  },true);
  function boot1013(){ensureTolerance1013();ensureWallButtons1013();setTimeout(()=>{ensureTolerance1013();ensureWallButtons1013()},1000)}
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',boot1013);else boot1013();
})();
'''
s += module
p.write_text(s,encoding='utf-8',newline='\n')

# style.css
p=WORK/'app/static/style.css'; s=p.read_text(encoding='utf-8')
s += r'''
/* v10.1.3 */
.tolerance-control-1013{display:flex;align-items:center;gap:10px;padding:9px 11px;border:1px solid rgba(216,178,92,.18);background:linear-gradient(135deg,rgba(216,178,92,.07),rgba(255,255,255,.025));border-radius:13px;box-shadow:inset 0 1px rgba(255,255,255,.03)}
.tolerance-control-1013 .tol-copy{display:flex;flex-direction:column;min-width:116px}.tolerance-control-1013 .tol-copy span{font-size:7px;letter-spacing:.12em;color:#a89262}.tolerance-control-1013 .tol-copy b{font-size:9px;color:#e8e0d0;margin-top:2px}
.tol-input-wrap{display:flex;align-items:center;background:#0d141d;border:1px solid rgba(255,255,255,.08);border-radius:9px;padding:0 9px;height:34px}.tol-input-wrap input{width:82px;background:transparent;border:0;outline:0;color:#f3ead8;font-weight:800;font-size:10px}.tol-input-wrap span{font-size:8px;color:#827765}
#toleranceSave1013,.wall-tools-1013 button{height:34px;border-radius:9px;border:1px solid rgba(216,178,92,.22);background:linear-gradient(180deg,rgba(216,178,92,.15),rgba(216,178,92,.06));color:#e9d7ad;padding:0 12px;font-size:8px;font-weight:800;cursor:pointer}
.wall-tools-1013{display:inline-flex;gap:7px;margin-left:7px;vertical-align:middle}.wall-tools-1013 .danger{border-color:rgba(255,76,88,.25);background:rgba(255,76,88,.08);color:#ff9098}.wall-tools-1013 button:disabled,#toleranceSave1013:disabled{opacity:.55;cursor:wait}
@media(max-width:900px){.tolerance-control-1013{width:100%;flex-wrap:wrap}.tolerance-control-1013 .tol-copy{flex:1}.wall-tools-1013{display:flex;margin:7px 0 0}}
'''
p.write_text(s,encoding='utf-8',newline='\n')

subprocess.run([sys.executable,'-m','py_compile',str(WORK/'app/main.py')],check=True)
subprocess.run(['node','--check',str(WORK/'app/static/app.js')],check=True)

files=[]
for rel in rels:
    src=WORK/rel; target=ROOT/'direct'/'10.1.3'/rel;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(src,target)
    files.append({'path':rel,'url':BASE+'direct/10.1.3/'+rel,'sha256':hashlib.sha256(src.read_bytes()).hexdigest()})
channel={'version':'10.1.3','published_at':'2026-08-14','notes':'Alarm toleransı panelden kalıcı değiştirilebilir; kritik ekran Yenile ve Kritikleri Sıfırla butonları güvenilir şekilde düzeltildi.','files':files}
(ROOT/'channel.json').write_text(json.dumps(channel,ensure_ascii=False,indent=2),encoding='utf-8',newline='\n')
