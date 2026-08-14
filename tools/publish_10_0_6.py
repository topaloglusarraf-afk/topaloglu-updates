from pathlib import Path
import hashlib, json, shutil, urllib.request, zipfile

ROOT = Path.cwd()
SOURCE_URL = "https://raw.githubusercontent.com/topaloglusarraf-afk/topaloglu-updates/main/update-10.0.5.zip"
SOURCE = ROOT / "_source-10.0.5.zip"
WORK = ROOT / "_build-10.0.6"
OUT = ROOT / "update-10.0.6.zip"

urllib.request.urlretrieve(SOURCE_URL, SOURCE)
if WORK.exists():
    shutil.rmtree(WORK)
WORK.mkdir()
with zipfile.ZipFile(SOURCE, "r") as z:
    z.extractall(WORK)

app = WORK / "Topaloglu-Pazaryeri-Merkezi"
if not app.exists():
    raise SystemExit("Update package root not found")

wallboard_js = r'''(() => {
  const $ = s => document.querySelector(s);
  const esc = s => String(s ?? '').replace(/[&<>\"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','\"':'&quot;',"'":'&#39;'}[c]));
  const money = n => n == null ? '—' : new Intl.NumberFormat('tr-TR',{minimumFractionDigits:2,maximumFractionDigits:2}).format(Number(n))+' TL';
  const label = s => ({LOSS:'Zarar',CRITICAL:'Kritik',WARNING:'Uyarı',OK:'Normal',UNRESOLVED:'Eşleşmedi',REVIEW:'İncelenecek','STOK YOK':'Stok Yok','SATIŞA KAPALI':'Satışa Kapalı'}[s]||s||'—');

  function setText(sel, value){ const el=$(sel); if(el) el.textContent=value; }
  function setState(kind, title, message){
    const box=$('#wallStatus'); if(!box) return;
    box.classList.remove('wall-ok','wall-warning','wall-critical');
    box.classList.add(kind==='critical'?'wall-critical':kind==='warning'?'wall-warning':'wall-ok');
    setText('#wallEyebrow', kind==='critical'?'KRİTİK FİYAT HATASI':kind==='warning'?'FİYAT UYARISI':'SİSTEM NORMAL');
    setText('#wallTitle',title); setText('#wallMessage',message);
    document.body.classList.toggle('has-critical-price',kind==='critical');
  }
  function renderAlerts(rows){
    const list=$('#wallAlertList'); if(!list) return;
    const title=$('#wallListTitle');
    if(!rows.length){
      if(title) title.textContent='Sorunlu fiyat bulunamadı';
      list.innerHTML='<div class="wall-empty"><div class="wall-checkmark">✓</div><b>Her şey normal</b><span>Kritik veya uyarı seviyesinde aktif fiyat kaydı yok.</span></div>';
      return;
    }
    if(title) title.textContent=rows.length+' fiyat kaydı dikkat istiyor';
    list.innerHTML=rows.slice(0,12).map(x=>`<div class="wall-alert-row ${['LOSS','CRITICAL'].includes(x.status)?'critical':'warning'}"><div class="wall-alert-dot"></div><div class="wall-alert-product"><b>${esc(x.name||'—')}</b><span>${esc(x.barcode||x.product_code||'—')} · ${esc(x.marketplace||'—')}</span></div><div class="wall-alert-status"><strong>${label(x.status)}</strong><span>${x.net_margin!=null?money(x.net_margin):'Fiyatı kontrol et'}</span></div></div>`).join('');
  }
  function dashboardRows(d){
    return (d.checks||[]).filter(x=>['LOSS','CRITICAL','WARNING'].includes(x.status));
  }
  async function fetchJson(url, opts){
    const r=await fetch(url,opts); const text=await r.text();
    let j={}; try{j=JSON.parse(text)}catch(_){throw new Error('Sunucudan geçersiz cevap alındı')}
    if(!r.ok) throw new Error(j.detail||j.message||('HTTP '+r.status)); return j;
  }
  async function refresh(){
    try{
      let products=0, rows=[];
      try{
        const ops=await fetchJson('/api/operations/overview');
        products=Number(ops?.stats?.products||0);
        rows=(ops?.actions||[]).filter(x=>['LOSS','CRITICAL','WARNING'].includes(x.status));
      }catch(_){
        const d=await fetchJson('/api/dashboard');
        products=Number(d?.stats?.products||0);
        rows=dashboardRows(d);
      }
      const critical=rows.filter(x=>['LOSS','CRITICAL'].includes(x.status));
      const warnings=rows.filter(x=>x.status==='WARNING');
      setText('#wallCritical',String(critical.length));
      setText('#wallWarning',String(warnings.length));
      setText('#wallProducts',String(products));
      setText('#wallUpdated',new Date().toLocaleTimeString('tr-TR',{hour:'2-digit',minute:'2-digit'}));
      if(critical.length) setState('critical',critical.length+' kritik kayıt var','Fiyat farkı 1.000 TL alarm toleransının üzerinde. Hemen kontrol edin.');
      else if(warnings.length) setState('warning',warnings.length+' kayıt kontrol bekliyor','Kritik zarar görünmüyor; uyarı seviyesinde kayıtlar var.');
      else setState('ok','Kritik fiyat hatası yok','Aktif fiyat kayıtları 1.000 TL alarm toleransı içinde.');
      renderAlerts([...critical,...warnings]);
    }catch(e){
      setText('#wallCritical','!'); setText('#wallWarning','!'); setText('#wallProducts','—');
      setState('critical','VERİ BAĞLANTISI YOK','Kontrol verileri okunamadı: '+(e?.message||String(e)));
      const t=$('#wallListTitle'); if(t) t.textContent='Veri alınamadı';
      const l=$('#wallAlertList'); if(l) l.innerHTML='<div class="wall-empty"><b>Kontrol verisi alınamadı</b><span>Bu ekran artık bağlantı hatasını 0 ürün gibi göstermiyor.</span></div>';
    }
  }
  async function runNow(){
    const btn=$('#wallCheckBtn'); if(btn){btn.disabled=true;btn.textContent='Kontrol ediliyor…'}
    try{ await fetchJson('/api/check',{method:'POST'}); await refresh(); }
    catch(e){ setState('critical','KONTROL BAŞARISIZ',e?.message||String(e)); }
    finally{ if(btn){btn.disabled=false;btn.textContent='Şimdi Kontrol Et'} }
  }
  function bind(){
    const btn=$('#wallCheckBtn'); if(btn && !btn.dataset.wallBound){btn.dataset.wallBound='1';btn.addEventListener('click',runNow)}
    refresh(); setInterval(refresh,20000);
  }
  if(document.readyState==='loading') document.addEventListener('DOMContentLoaded',bind,{once:true}); else bind();
})();
'''
(app / 'app/static/wallboard.js').write_text(wallboard_js, encoding='utf-8')

p = app / 'app/static/index.html'
s = p.read_text(encoding='utf-8')
s = s.replace('Pazaryeri Merkezi v10.0.5','Pazaryeri Merkezi v10.0.6')
s = s.replace('/static/style.css?v=10.0.5','/static/style.css?v=10.0.6')
s = s.replace('/static/app.js?v=10.0.5','/static/app.js?v=10.0.6')
if '/static/wallboard.js?v=10.0.6' not in s:
    s = s.replace('</body>','  <script src="/static/wallboard.js?v=10.0.6"></script>\n</body>')
p.write_text(s, encoding='utf-8')

(app / 'VERSION').write_text('10.0.6', encoding='utf-8')

p = app / 'README.md'
s = p.read_text(encoding='utf-8').replace('10.0.5','10.0.6')
s += "\n\n## 10.0.6 — Ortak ekran veri düzeltmesi\n- Ortak ekran ana app.js dosyasından bağımsız veri motoruyla beslenir.\n- Önce /api/operations/overview, gerekirse /api/dashboard fallback kullanılır.\n- Veri alınamazsa 0 göstermek yerine kırmızı VERİ BAĞLANTISI YOK alarmı gösterir.\n- Şimdi Kontrol Et doğrudan /api/check çağırır ve sonucu ekrana yeniler.\n"
p.write_text(s, encoding='utf-8')

if OUT.exists(): OUT.unlink()
with zipfile.ZipFile(OUT,'w',zipfile.ZIP_DEFLATED) as z:
    for f in app.rglob('*'):
        if f.is_file() and '__pycache__' not in f.parts:
            z.write(f, Path('Topaloglu-Pazaryeri-Merkezi') / f.relative_to(app))
sha=hashlib.sha256(OUT.read_bytes()).hexdigest()
manifest={
  'version':'10.0.6',
  'published_at':'2026-08-14',
  'notes':'Ortak ekranın 0 değerlerde donmasına neden olan veri yükleme sorunu düzeltildi.',
  'package_url':'https://raw.githubusercontent.com/topaloglusarraf-afk/topaloglu-updates/main/update-10.0.6.zip',
  'sha256':sha,
}
(ROOT/'latest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
shutil.rmtree(WORK,ignore_errors=True); SOURCE.unlink(missing_ok=True)
print('Built',OUT,sha)
