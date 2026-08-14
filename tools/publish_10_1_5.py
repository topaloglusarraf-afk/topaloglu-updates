from pathlib import Path
import urllib.request, hashlib, json, re

ROOT=Path.cwd()
BASE='https://raw.githubusercontent.com/topaloglusarraf-afk/topaloglu-updates/main/direct/10.1.4/'
OUT=ROOT/'direct/10.1.5'
(OUT/'app/static').mkdir(parents=True,exist_ok=True)

def get(path):
    return urllib.request.urlopen(BASE+path).read().decode('utf-8')

js=get('app/static/app.js')
css=get('app/static/style.css')

# Warning is informational/normal, not a price problem.
js=js.replace("'WARNING':'Uyarı'", "'WARNING':'Fiyatlar tutuyor'")
js=js.replace("const alerts=(D.stats.critical||0)+(D.stats.warning||0);", "const alerts=(D.stats.critical||0);")
js=js.replace("const risk=(s.loss||0)+(s.critical||0)+(s.warning||0);", "const risk=(s.loss||0)+(s.critical||0);")
js=js.replace("<small>Zarar / kritik / uyarı</small>", "<small>Yalnız kritik fiyat hatası</small>")
js=js.replace("const riskSet=new Set(['LOSS','CRITICAL','WARNING']);", "const riskSet=new Set(['LOSS','CRITICAL']);")
js=js.replace("const cls=['LOSS','CRITICAL','WARNING'].includes(x.status)?'risk':x.status==='OK'?'ok':'muted';", "const cls=['LOSS','CRITICAL'].includes(x.status)?'risk':['OK','WARNING'].includes(x.status)?'ok':'muted';")

# Final wallboard override: only LOSS/CRITICAL are visible as problems.
js += r'''

/* v10.1.5 — critical-only shared wallboard */
(function(){
  const q=s=>document.querySelector(s);
  const esc=v=>String(v??'').replace(/[&<>\"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','\"':'&quot;'}[c]));
  const money=v=>new Intl.NumberFormat('tr-TR',{minimumFractionDigits:2,maximumFractionDigits:2}).format(Number(v||0))+' TL';
  async function api(url,opt){const r=await fetch(url,opt);let j={};try{j=await r.json()}catch(_){ }if(!r.ok)throw new Error(j.detail||j.message||'İşlem başarısız');return j}

  function ensureDisclaimer(){
    if(q('#wallProjectDisclaimer'))return;
    const host=q('.wall-panel')||q('#view-operations');
    if(!host)return;
    const d=document.createElement('div');d.id='wallProjectDisclaimer';d.className='wall-project-disclaimer';
    d.innerHTML='<span>ⓘ</span><p>Fiyatların doğruluğu sorumluluk altında değildir. Bu bir projedir; lütfen fiyatları manuel kontrol ediniz.</p>';
    host.insertAdjacentElement('afterend',d);
  }

  window.refreshWallboardV1010=async function(){
    try{
      const [ops,dash,health]=await Promise.all([api('/api/operations/overview'),api('/api/dashboard'),api('/api/health')]);
      const critical=(ops.actions||[]).filter(x=>x.status==='LOSS'||x.status==='CRITICAL');
      const count=critical.length;
      if(q('#wallCritical'))q('#wallCritical').textContent=count;
      if(q('#wallWarning'))q('#wallWarning').textContent='0';
      if(q('#wallProducts'))q('#wallProducts').textContent=ops.stats?.products??dash.stats?.products??0;
      if(q('#wallExcluded'))q('#wallExcluded').textContent=ops.stats?.excluded??0;
      if(q('#wallUpdated'))q('#wallUpdated').textContent=new Date().toLocaleTimeString('tr-TR',{hour:'2-digit',minute:'2-digit'});
      const status=q('#wallStatus');
      if(status){status.classList.remove('wall-ok','wall-warning','wall-critical','wall-error');status.classList.add(count?'wall-critical':'wall-ok')}
      if(q('#wallTitle'))q('#wallTitle').textContent=count?'Fiyatlar tutmuyor':'Fiyatlar tutuyor';
      if(q('#wallMessage'))q('#wallMessage').textContent=count?`${count} kritik fiyat hatası tespit edildi. Manuel kontrol gerekli.`:'Kritik fiyat farkı tespit edilmedi.';
      if(q('#wallEyebrow'))q('#wallEyebrow').textContent=count?'KRİTİK FİYAT UYARISI':'PAZARYERİ FİYATLARI NORMAL';
      if(q('#wallListTitle'))q('#wallListTitle').textContent=count?`${count} kritik ürün manuel kontrol bekliyor`:'Kritik fiyat hatası yok';
      const list=q('#wallAlertList');
      if(list){
        list.innerHTML=count?critical.map(x=>`<article class="wall-alert-card critical-only"><div class="wall-alert-state"><span>KRİTİK</span><b>${esc(x.marketplace||'—')}</b></div><div class="wall-alert-product"><strong>${esc(x.name||'—')}</strong><small>${esc(x.barcode||x.product_code||'—')}</small></div><div class="wall-alert-prices"><div><span>Pazaryeri</span><b>${money(x.price)}</b></div><div><span>Beklenen</span><b>${money(x.expected_price)}</b></div><div class="negative"><span>Fark</span><b>${money(x.difference)}</b></div></div></article>`).join(''):'<div class="wall-clean-state"><div>✓</div><strong>Fiyatlar tutuyor</strong><span>Kritik fiyat hatası bulunmuyor.</span></div>';
      }
      const marketBox=q('#wallMarketHealth');
      if(marketBox){const ms=['Trendyol','Hepsiburada','N11','Idefix','Pazarama'];marketBox.innerHTML=ms.map(m=>{const n=critical.filter(x=>x.marketplace===m).length;return `<span class="wall-market-pill ${n?'risk':'ok'}">${m}<b>${n||'✓'}</b></span>`}).join('')}
      ensureDisclaimer();
      return {ops,dash,health};
    }catch(e){
      const status=q('#wallStatus');if(status){status.classList.remove('wall-ok','wall-warning','wall-critical');status.classList.add('wall-error')}
      if(q('#wallTitle'))q('#wallTitle').textContent='Veri bağlantısı yok';
      if(q('#wallMessage'))q('#wallMessage').textContent='Fiyat verileri alınamadı. Manuel kontrol ediniz.';
      ensureDisclaimer();throw e;
    }
  };

  function boot(){
    const warningCard=q('#wallWarning')?.closest('article');if(warningCard)warningCard.classList.add('wall-warning-hidden-1015');
    ensureDisclaimer();
    window.refreshWallboardV1010().catch(()=>{});
    setInterval(()=>window.refreshWallboardV1010().catch(()=>{}),20000);
  }
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',boot);else boot();
})();
'''

css += r'''

/* v10.1.5 critical-only wallboard */
.wall-warning-hidden-1015{display:none!important}
.wall-project-disclaimer{margin:16px 0 0;padding:14px 18px;border:1px solid rgba(214,178,94,.22);background:rgba(214,178,94,.06);border-radius:16px;display:flex;gap:12px;align-items:flex-start;color:#c8c1b3;font-size:13px;line-height:1.55}
.wall-project-disclaimer span{color:#d6b25e;font-size:18px;line-height:1.2}.wall-project-disclaimer p{margin:0}
.wall-alert-card.critical-only{border:1px solid rgba(255,75,75,.26);background:linear-gradient(135deg,rgba(110,20,24,.22),rgba(18,20,25,.72));box-shadow:0 18px 45px rgba(0,0,0,.18)}
.wall-alert-state span{display:inline-flex;padding:5px 9px;border-radius:999px;background:rgba(255,70,70,.13);color:#ff7777;font-size:11px;font-weight:800;letter-spacing:.08em}
.wall-clean-state{min-height:180px;display:flex;flex-direction:column;align-items:center;justify-content:center;text-align:center;gap:8px;color:#98a89d}.wall-clean-state div{width:48px;height:48px;border-radius:50%;display:grid;place-items:center;background:rgba(72,190,120,.1);border:1px solid rgba(72,190,120,.25);color:#76d59c;font-size:24px}.wall-clean-state strong{font-size:20px;color:#e8eee9}.wall-clean-state span{font-size:13px;color:#829087}
.wall-status.wall-ok #wallTitle{color:#eaf7ee}.wall-status.wall-critical #wallTitle{color:#fff0f0}
'''

(OUT/'app/static/app.js').write_text(js,encoding='utf-8',newline='\n')
(OUT/'app/static/style.css').write_text(css,encoding='utf-8',newline='\n')

files=[]
for rel in ['app/static/app.js','app/static/style.css']:
    p=OUT/rel
    files.append({'path':rel,'url':f'https://raw.githubusercontent.com/topaloglusarraf-afk/topaloglu-updates/main/direct/10.1.5/{rel}','sha256':hashlib.sha256(p.read_bytes()).hexdigest()})
channel={'version':'10.1.5','published_at':'2026-08-14','notes':'Sarı WARNING kayıtları normal kabul edilir; ortak ekran yalnız kritik fiyat hatalarını gösterir. Fiyatlar tutuyor/tutmuyor durumu ve manuel kontrol uyarısı eklendi.','files':files}
(ROOT/'channel.json').write_text(json.dumps(channel,ensure_ascii=False,indent=2),encoding='utf-8',newline='\n')
print('10.1.5 hazır')
