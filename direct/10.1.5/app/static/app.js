let D={stats:{},checks:[],products:[],events:[],runtime:{},by_market:{},mappings:[]},H={connections:{}};
let activeMarket='', unresolvedItems=[], selectedUnresolved=null;
const markets=["Trendyol","Hepsiburada","N11","Idefix","Pazarama"];
const $=s=>document.querySelector(s);
const money=n=>n==null?"—":new Intl.NumberFormat("tr-TR",{minimumFractionDigits:2,maximumFractionDigits:2}).format(Number(n))+" TL";


const displayCode=x=>{
  const et=(x?.tsoft_barcode||x?.barcode||'').trim();
  if(et) return et;
  return x?.product_code||'—';
};
const secondaryProductCode=x=>{
  const et=(x?.tsoft_barcode||x?.barcode||'').trim();
  const pc=(x?.product_code||'').trim();
  return et && pc && et!==pc ? pc : '';
};

const statusLabel=s=>({
  'LOSS':'Zarar',
  'CRITICAL':'Kritik',
  'WARNING':'Fiyatlar tutuyor',
  'OK':'Normal',
  'UNRESOLVED':'Eşleşmedi',
  'IGNORED':'Dikkate Alınmadı',
  'REVIEW':'İncelenecek',
  'STOK YOK':'Stok Yok',
  'SATIŞA KAPALI':'Satışa Kapalı'
}[s]||s||'—');

function animateNumber(el, target, duration=500){
  if(!el)return;
  const end=Number(target)||0;
  const start=Number(el.dataset.prev||0);
  const t0=performance.now();
  const step=t=>{
    const p=Math.min(1,(t-t0)/duration);
    const eased=1-Math.pow(1-p,3);
    el.textContent=Math.round(start+(end-start)*eased);
    if(p<1) requestAnimationFrame(step);
    else el.dataset.prev=end;
  };
  requestAnimationFrame(step);
}

function animateView(view){
  if(!view)return;
  view.classList.remove('view-enter');
  void view.offsetWidth;
  view.classList.add('view-enter');
}

const toast=m=>{let x=$("#toast");x.textContent=m;x.classList.add("show");setTimeout(()=>x.classList.remove("show"),2600)};
async function req(u,o){let r=await fetch(u,o),j=await r.json();if(!r.ok)throw new Error(j.detail||"İstek başarısız");return j}


let OPS={stats:{},actions:[],products:[],runtime:{}};

async function loadOperations(){
  try{
    OPS=await req('/api/operations/overview');
    animateNumber($('#ops-products'),OPS.stats.products||0);
    animateNumber($('#ops-normal'),OPS.stats.normal||0);
    animateNumber($('#ops-risk'),OPS.stats.risks||0);
    animateNumber($('#ops-stock'),OPS.stats.stock_zero||0);
    animateNumber($('#ops-closed'),OPS.stats.closed||0);
    $('#ops-loss').textContent=money(OPS.stats.potential_loss||0);
    renderOpsActions(); renderOpsProducts(); await loadConnectProfHealth();
  }catch(e){toast('Operasyon merkezi: '+e.message)}
}

function renderOpsActions(){
  const market=$('#opsActionMarket')?.value||'', q=($('#opsActionSearch')?.value||'').toLowerCase();
  const rows=(OPS.actions||[]).filter(x=>(!market||x.marketplace===market)&&(!q||JSON.stringify(x).toLowerCase().includes(q)));
  $('#opsActionList').innerHTML=rows.map(x=>`<div class="ops-action ${x.priority==='Çok Yüksek'?'urgent':x.priority==='Yüksek'?'high':''}">
    <div class="ops-priority"><span>${x.priority}</span><small>${x.type}</small></div>
    <div class="ops-action-main"><b>${x.name||'—'}</b><span><code>${x.barcode||x.product_code}</code>${x.barcode&&x.product_code&&x.barcode!==x.product_code?` <em class="legacy-inline">${x.product_code}</em>`:""} · ${x.marketplace} · ${statusLabel(x.status)}</span></div>
    <div class="ops-action-value">${x.net_margin!=null?`<b class="negative">${money(x.net_margin)}</b>`:`<b>${money(x.price)}</b>`}<span>${x.suggestion}</span></div>
  </div>`).join('')||`<div class="ops-empty"><b>Aksiyon gerektiren kayıt yok</b><span>Şu anda problem görünmüyor.</span></div>`;
}

function marketCell(x){
  if(!x)return `<div class="matrix-market missing"><span>—</span><small>Kayıt yok</small></div>`;
  const cls=['LOSS','CRITICAL'].includes(x.status)?'risk':['OK','WARNING'].includes(x.status)?'ok':'muted';
  return `<div class="matrix-market ${cls}"><b>${money(x.price)}</b><span>${statusLabel(x.status)}</span><small>Stok ${x.stock??'—'}</small></div>`;
}

function renderOpsProducts(){
  const q=($('#opsProductSearch')?.value||'').toLowerCase();
  const rows=(OPS.products||[]).filter(x=>!q||JSON.stringify(x).toLowerCase().includes(q)).slice(0,250);
  $('#opsProductMatrix').innerHTML=rows.map(x=>`<article class="matrix-row">
    <div class="matrix-product"><code class="primary-code">${x.barcode||x.product_code}</code>${x.barcode&&x.product_code&&x.barcode!==x.product_code?`<small class="legacy-code">Eski kod: ${x.product_code}</small>`:""}<b>${x.name||'—'}</b><span>T-Soft ${money(x.tsoft_price)} · Stok ${x.tsoft_stock??'—'}</span></div>
    ${markets.map(m=>`<div class="matrix-channel"><label>${m}</label>${marketCell((x.markets||{})[m])}</div>`).join('')}
  </article>`).join('')||`<div class="ops-empty"><b>Ürün bulunamadı</b><span>Arama kriterini değiştir.</span></div>`;
}

async function loadConnectProfHealth(){
  try{
    const h=await req('/api/connectprof/health'), box=$('#cpState');
    box.textContent=h.state||'Bilinmiyor'; box.className='cp-state '+(h.ok?'ok':h.configured?'error':'idle');
    $('#cpMessage').textContent=h.message||'';
    $('#cpProductsState').textContent=h.configured?'Hazır':'Bekliyor';
    $('#cpExportsState').textContent=h.configured?'Path bekliyor':'Bekliyor';
    $('#cpOrdersState').textContent=h.configured?'Path bekliyor':'Bekliyor';
  }catch(e){$('#cpState').textContent='Hata';$('#cpState').className='cp-state error';$('#cpMessage').textContent=e.message}
}

async function load(){
  [H,D]=await Promise.all([req('/api/health'),req('/api/dashboard')]);

  $('#tolChip').textContent=money(H.alert_tolerance_tl||1000);
  animateNumber($('#s-products'),D.stats.products||0);
  animateNumber($('#s-ok'),D.stats.ok||0);
  animateNumber($('#s-loss2'),D.stats.loss||0);

  const alerts=(D.stats.critical||0);
  animateNumber($('#s-alerts2'),alerts);
  animateNumber($('#s-unresolved'),D.stats.unresolved||0);
  animateNumber($('#s-stock-zero'),D.stats.stock_zero||0);
  animateNumber($('#s-closed'),D.stats.closed||0);

  const priceTotal=(D.stats.price_checked||0);
  const clean=Math.max(0,priceTotal-(D.stats.loss||0)-alerts);
  const score=priceTotal>0?Math.round((clean/priceTotal)*100):100;
  $('#healthScore').textContent=score+'%';

  renderMarkets();
  renderMarketTabs();
  renderChecks();
  renderAvailability();
  renderProducts();
  renderEvents();
}
function renderMarkets(){
  $('#marketStrip').innerHTML=markets.map(n=>{
    const on=!!H.connections[n], selected=PRICE_PROTECTION_SELECTED.has(n), s=D.by_market[n]||{}, r=D.runtime||{};
    const last=r['last_'+n+'_success']||'Henüz kontrol edilmedi';
    const risk=(s.loss||0)+(s.critical||0);
    const priceOk=s.ok||0;
    const stock=s.stock_zero||0, closed=s.closed||0;
    const health=(risk===0&&on)?'healthy':risk>0?'attention':'idle';

    return `<article class="market-card glass ${health} ${selected?'':'market-excluded'}">
      <div class="market-top">
        <div>
          <div class="market-title">${n}</div>
          <div class="market-connection"><i class="market-dot ${on?'on':''}"></i>${!selected?'Kontrol dışı':on?'Bağlı':'Bağlantı bekliyor'}</div>
        </div>
        <span class="market-health ${health}">${health==='healthy'?'Sağlıklı':health==='attention'?'Kontrol gerekli':'Bekliyor'}</span>
      </div>
      <div class="market-last">${last}</div>
      <div class="market-health-grid">
        <div class="market-health-item success"><span>Fiyatı Tutan</span><b>${priceOk}</b><small>Normal fiyat</small></div>
        <div class="market-health-item danger"><span>Fiyat Riski</span><b>${risk}</b><small>Yalnız kritik fiyat hatası</small></div>
        <div class="market-health-item warning"><span>Stok 0</span><b>${stock}</b><small>Fiyat alarmı dışında</small></div>
        <div class="market-health-item purple"><span>Kapalı</span><b>${closed}</b><small>Satışa kapalı</small></div>
      </div>
      <div class="market-footer">
        <span>Eşleşen ürün <b>${r[n+'_matched']||0}</b></span>
        <button class="market-check-btn" data-check-market="${n}" ${on?'':'disabled'}>${on?'Kontrolü Yenile':'Bağlantı Bekliyor'}</button>
      </div>
    </article>`
  }).join('');
  document.querySelectorAll('[data-check-market]').forEach(b=>b.onclick=()=>checkSingleMarket(b.dataset.checkMarket));
}
function renderMarketTabs(){
  const items=['',...markets];
  $('#marketTabs').innerHTML=items.map(n=>`<button class="market-tab ${activeMarket===n?'active':''}" data-market="${n}">${n||'Tümü'}${n&&D.by_market[n]?` <b>${D.by_market[n].total||0}</b>`:''}</button>`).join('');
  document.querySelectorAll('.market-tab').forEach(b=>b.onclick=()=>{activeMarket=b.dataset.market;renderMarketTabs();renderChecks();renderAvailability()});
}

function renderChecks(){
  const q=$('#search').value.toLowerCase(), sf=$('#statusFilter').value, risk=$('#riskOnly').checked;
  const riskSet=new Set(['LOSS','CRITICAL']);
  const excluded=new Set(['STOK YOK','SATIŞA KAPALI']);

  const rows=D.checks.filter(x=>{
    if(excluded.has(x.status))return false;
    if(activeMarket&&x.marketplace!==activeMarket)return false;
    if(sf&&x.status!==sf)return false;
    if(risk&&!riskSet.has(x.status))return false;
    return !q||JSON.stringify(x).toLowerCase().includes(q)
  });

  $('#checksBody').innerHTML=rows.map(x=>{
    const nm=x.net_margin;
    return `<tr class="${x.status}">
      <td><span class="badge">${statusLabel(x.status)}</span></td>
      <td><span class="market-name">${x.marketplace}</span></td>
      <td><code class="primary-code">${displayCode(x)}</code>${secondaryProductCode(x)?`<small class="legacy-code">${secondaryProductCode(x)}</small>`:""}</td>
      <td class="name" title="${x.name||''}">${x.name||''}</td>
      <td><span class="price-main">${money(x.tsoft_price)}</span></td>
      <td>${x.commission_rate==null?'—':'%'+String(x.commission_rate).replace('.',',')}</td>
      <td><span class="price-market">${money(x.current_price)}</span></td>
      <td>${money(x.net_after_commission)}</td>
      <td class="${nm!=null?(nm<0?'negative':'positive'):''}">${money(nm)}</td>
      <td class="${Number(x.difference)<0?'negative-diff':'positive-diff'}">${money(x.difference)}</td>
    </tr>`
  }).join('') || `<tr><td colspan="10"><div class="table-empty"><b>Fiyat riski bulunamadı</b><span>Seçili filtrelerde aksiyon gerektiren ürün görünmüyor.</span></div></td></tr>`;
}
function renderAvailability(){
  const market=$('#availabilityMarket')?.value||'';
  const status=$('#availabilityStatus')?.value||'';
  const q=($('#availabilitySearch')?.value||'').toLowerCase();

  const all=D.checks.filter(x=>x.status==='STOK YOK'||x.status==='SATIŞA KAPALI');
  const rows=all.filter(x=>{
    if(market&&x.marketplace!==market)return false;
    if(status&&x.status!==status)return false;
    return !q||JSON.stringify(x).toLowerCase().includes(q);
  });

  $('#a-total').textContent=all.length;
  $('#a-stock').textContent=all.filter(x=>x.status==='STOK YOK').length;
  $('#a-closed').textContent=all.filter(x=>x.status==='SATIŞA KAPALI').length;

  $('#availabilityBody').innerHTML=rows.map(x=>`
    <tr class="${x.status==='STOK YOK'?'availability-stock':'availability-closed'}">
      <td><span class="availability-badge ${x.status==='STOK YOK'?'stock':'closed'}">${statusLabel(x.status)}</span></td>
      <td>${x.marketplace}</td>
      <td><code class="primary-code">${displayCode(x)}</code>${secondaryProductCode(x)?`<small class="legacy-code">${secondaryProductCode(x)}</small>`:""}</td>
      <td class="name">${x.name||'—'}</td>
      <td><code>${x.marketplace_sku||'—'}</code></td>
      <td>${x.match_method||'—'}</td>
      <td><b>${x.current_stock??0}</b></td>
      <td>${money(x.current_price)}</td>
      <td class="muted-cell">${x.error||'Fiyat alarmı dışında'}</td>
    </tr>
  `).join('') || `<tr><td colspan="9"><div class="table-empty"><b>Operasyon kaydı yok</b><span>Seçili filtrelerde stok 0 veya satışa kapalı ürün bulunmuyor.</span></div></td></tr>`;
}
function renderProducts(){
  const q=$('#productSearch').value.toLowerCase();
  $('#productsBody').innerHTML=D.products.filter(x=>!q||JSON.stringify(x).toLowerCase().includes(q)).slice(0,3000).map(p=>{
    const opts=D.groups.map(g=>`<option ${g===p.price_group?'selected':''}>${g}</option>`).join('');
    return `<tr><td><code class="primary-code">${p.barcode||p.product_code}</code>${p.barcode&&p.product_code&&p.barcode!==p.product_code?`<small class="legacy-code">${p.product_code}</small>`:""}</td><td class="name">${p.name}</td><td>${p.category||'—'}</td><td>${money(p.buying_price)}</td><td>${money(p.selling_price)}</td><td><select class="groupSelect" data-code="${p.product_code}">${opts}</select></td></tr>`
  }).join('');
  document.querySelectorAll('.groupSelect').forEach(s=>s.onchange=async()=>{await req(`/api/products/${encodeURIComponent(s.dataset.code)}/group/${encodeURIComponent(s.value)}`,{method:'POST'});toast('Ürün grubu kaydedildi')});
}

function renderEvents(){
  $('#eventsList').innerHTML=D.events.map(e=>`<div class="event-item"><div class="event-level ${e.level}">${e.level}</div><div class="event-market">${e.marketplace||'Sistem'}${e.product_code?' · '+e.product_code:''}</div><div class="event-message">${e.message}</div><div class="event-time">${e.created_at}</div></div>`).join('');
}


async function runSingleProductCheck(){
  const code=($('#singleProductCode')?.value||'').trim();
  if(!code){toast('Önce ET barkodu veya T-Soft ürün kodunu gir.');return;}
  const btn=$('#singleProductBtn'), old=btn.textContent;
  btn.disabled=true;btn.textContent='Kontrol ediliyor…';
  try{
    const r=await req('/api/check/product/'+encodeURIComponent(code),{method:'POST'});
    const cards=markets.map(m=>{
      const x=(r.markets||{})[m];
      if(!x)return `<article class="single-market-result glass idle"><div class="sm-head"><b>${m}</b><span>Kontrol edilmedi</span></div></article>`;
      const cls=(x.status||'').replaceAll(' ','-').toLowerCase();
      return `<article class="single-market-result glass ${cls}">
        <div class="sm-head"><b>${m}</b><span class="sm-status">${statusLabel(x.status)}</span></div>
        <div class="sm-price">${money(x.current_price)}</div>
        <div class="sm-grid"><div><span>Stok</span><b>${x.current_stock??'—'}</b></div><div><span>Eşleşme</span><b>${x.match_method||'—'}</b></div><div><span>Market SKU</span><b>${x.marketplace_sku||'—'}</b></div><div><span>Net Fark</span><b class="${Number(x.net_margin)<0?'negative':''}">${money(x.net_margin)}</b></div></div>
        <div class="sm-title">${escapeHtml(x.marketplace_title||'')}</div>${x.error?`<div class="sm-error">${escapeHtml(x.error)}</div>`:''}
      </article>`;
    }).join('');
    $('#singleProductResult').innerHTML=`<div class="single-result-head"><div><span>T-SOFT</span><h3>${escapeHtml(r.name||'')}</h3><code>${escapeHtml(r.product_code||code)}</code></div></div><div class="single-market-grid">${cards}</div>`;
    await load();
  }catch(e){
    $('#singleProductResult').innerHTML=`<div class="single-empty glass"><div class="empty-icon">!</div><h3>Kontrol başarısız</h3><p>${escapeHtml(e.message)}</p></div>`;
  }finally{btn.disabled=false;btn.textContent=old;}
}

async function saveDirectManualMapping(){
  if(!selectedUnresolved){toast('Önce soldan bir T-Soft ürünü seç.');return;}
  const match_value=($('#manualMatchValue')?.value||'').trim();
  if(!match_value){toast('Barkod veya SKU değerini gir.');return;}
  const btn=$('#manualSaveBtn'), old=btn.textContent;
  btn.disabled=true;btn.textContent='Kaydediliyor…';
  try{
    await req('/api/mappings/save',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({
      marketplace:$('#mappingMarket').value,
      product_code:selectedUnresolved.product_code,
      match_key:$('#manualMatchKey').value,
      match_value,
      marketplace_title:($('#manualMatchTitle')?.value||'').trim()
    })});
    $('#manualSaveState').innerHTML=`<span class="save-ok">✓ Kalıcı olarak kaydedildi: ${escapeHtml(match_value)}</span>`;
    toast('Manuel eşleştirme kalıcı olarak kaydedildi.');
    await loadUnresolved(); await load();
  }catch(e){
    $('#manualSaveState').innerHTML=`<span class="save-error">${escapeHtml(e.message)}</span>`;
    toast('Eşleştirme kaydedilemedi.');
  }finally{btn.disabled=false;btn.textContent=old;}
}


async function runHbDiagnostics(){
  const msg0=document.getElementById('hbDiagMessage');
  if(msg0){
    msg0.className='hb-diag-message';
    msg0.innerHTML='<b>Test başlatıldı…</b><span>Hepsiburada servislerine bağlanılıyor.</span>';
  }
  const btn=$('#hbDiagBtn'), old=btn?.textContent||'';
  if(btn){btn.disabled=true;btn.textContent='3 servis test ediliyor…';}
  try{
    const r=await req('/api/hepsiburada/diagnostics');

    const cfg=$('#hbDiagConfig');
    if(cfg) cfg.innerHTML=`
      <div><span>Ortam</span><b>${r.environment||'—'}</b></div>
      <div><span>Merchant ID</span><b>${r.merchant_id_present?'Hazır':'Eksik'}</b></div>
      <div><span>Username</span><b>${r.username_present?'Hazır':'Eksik'}</b></div>
      <div><span>Servis Anahtarı</span><b>${r.password_present?'Hazır':'Eksik'}</b></div>
      <div><span>User-Agent</span><b>${r.user_agent_present?'Hazır':'Eksik'}</b></div>
    `;

    const tests=r.tests||[];
    const icon=t=>{
      const s=t.http_status;
      if(s>=200&&s<300) return '●';
      if(s===401||s===403) return '●';
      return '●';
    };
    const cls=t=>{
      const s=t.http_status;
      if(s>=200&&s<300) return 'ok';
      if(s===401||s===403) return 'bad';
      return 'warn';
    };
    const shortName=t=>{
      if((t.service||'').startsWith('Listing')) return ['LISTING','Fiyat & Stok'];
      if((t.service||'').startsWith('Katalog')) return ['MPOP','Katalog'];
      return ['OMS','Sipariş'];
    };

    const box=$('#hbServiceTests');
    if(box) box.innerHTML=tests.map(t=>{
      const n=shortName(t);
      return `<article class="hb-service-card ${cls(t)}">
        <span>${n[0]}</span>
        <h4>${n[1]}</h4>
        <b>${icon(t)} ${t.state||'—'}</b>
        <em>HTTP ${t.http_status??'—'} · Auth: ${t.auth||'—'}</em>
        <small>${escapeHtml(t.message||'')}</small>
        <code>${escapeHtml(t.url||'')}</code>
      </article>`;
    }).join('');

    const msg=$('#hbDiagMessage');
    if(msg){
      const allOk=tests.length===3&&tests.every(t=>t.http_status>=200&&t.http_status<300);
      msg.className='hb-diag-message '+(allOk?'ok':tests.some(t=>t.http_status===401||t.http_status===403)?'error':'');
      msg.innerHTML=`<b>${r.summary||'—'}</b><span>${escapeHtml(r.message||'')}</span>${r.user_agent_warning?`<small>${escapeHtml(r.user_agent_warning)}</small>`:''}`;
    }
    toast(r.summary||'Hepsiburada teşhisi tamamlandı.');
  }catch(e){
    const msg=$('#hbDiagMessage');
    if(msg){msg.className='hb-diag-message error';msg.innerHTML=`<b>Teşhis Hatası</b><span>${escapeHtml(e.message)}</span>`;}
  }finally{
    if(btn){btn.disabled=false;btn.textContent=old;}
  }
}

async function loadUnresolved(){
  const market=$('#mappingMarket').value;
  const r=await req(`/api/mappings/unresolved?marketplace=${encodeURIComponent(market)}`); unresolvedItems=r.items||[]; renderUnresolved();
}
function renderUnresolved(){
  const q=$('#unresolvedSearch').value.toLowerCase();
  $('#unresolvedList').innerHTML=unresolvedItems.filter(x=>!q||JSON.stringify(x).toLowerCase().includes(q)).map(x=>`<div class="unresolved-item ${selectedUnresolved&&selectedUnresolved.product_code===x.product_code?'active':''}" data-code="${x.product_code}"><b>${x.name}</b><span>${x.product_code} · Barkod: ${x.barcode||'—'} · SKU: ${x.supplier_product_code||'—'}</span></div>`).join('')||'<div class="unresolved-item"><b>Çözülemeyen ürün yok</b><span>Bu pazaryerinde eşleşmeler temiz görünüyor.</span></div>';
  document.querySelectorAll('.unresolved-item[data-code]').forEach(el=>el.onclick=()=>selectUnresolved(el.dataset.code));
}
function selectUnresolved(code){
  selectedUnresolved=unresolvedItems.find(x=>x.product_code===code); if(!selectedUnresolved)return;
  renderUnresolved(); $('#mappingEmpty').classList.add('hidden'); $('#mappingEditor').classList.remove('hidden');
  if($('#manualMatchValue')) $('#manualMatchValue').value=''; if($('#manualMatchTitle')) $('#manualMatchTitle').value=''; if($('#manualSaveState')) $('#manualSaveState').innerHTML='';
  $('#mapProductName').textContent=selectedUnresolved.name; $('#mapProductCode').textContent=selectedUnresolved.product_code; $('#mapProductBarcode').textContent='Barkod: '+(selectedUnresolved.barcode||'—');
  $('#candidateSearch').value=selectedUnresolved.product_code; loadSuggestions(); loadCandidates();
}

async function loadSuggestions(){
  if(!selectedUnresolved)return;
  const market=$('#mappingMarket').value;
  try{
    const r=await req(`/api/mappings/suggestions?marketplace=${encodeURIComponent(market)}&product_code=${encodeURIComponent(selectedUnresolved.product_code)}&limit=5`);
    renderSuggestions(r.items||[]);
  }catch(e){
    $('#suggestionList').innerHTML=`<div class="candidate"><div><div class="title">Öneri alınamadı</div><div class="details">${e.message}</div></div></div>`;
  }
}

function renderSuggestions(items){
  const box=$('#suggestionList');
  if(!box)return;
  if(!items.length){
    box.innerHTML='<div class="candidate"><div><div class="title">Otomatik aday bulunamadı</div><div class="details">Aşağıdaki manuel aramayı kullanabilirsin.</div></div></div>';
    return;
  }

  box.innerHTML=items.map((x,i)=>`
    <div class="suggestion-card">
      <div class="suggestion-rank">${i+1}</div>
      <div class="suggestion-score">Benzerlik ${Math.round(Number(x.candidate_score||0))}</div>
      <div class="stitle">${x.title||x.stock_code||x.barcode||'Pazaryeri ürünü'}</div>
      <div class="smeta">SKU: ${x.stock_code||'—'}<br>Barkod: ${x.barcode||'—'}<br>${money(x.price)}</div>
      <div class="reason">${x.candidate_reason||'Benzer kayıt'}</div>
      <button
        data-sku="${encodeURIComponent(x.stock_code||'')}"
        data-barcode="${encodeURIComponent(x.barcode||'')}"
        data-pmid="${encodeURIComponent(x.product_main_id||'')}"
        data-title="${encodeURIComponent(x.title||'')}"
      >Bunu Eşleştir</button>
    </div>
  `).join('');

  box.querySelectorAll('button').forEach(b=>b.onclick=()=>saveCandidate(b));
}

async function loadCandidates(){
  if(!selectedUnresolved)return;
  const market=$('#mappingMarket').value, q=$('#candidateSearch').value;
  const r=await req(`/api/mappings/candidates?marketplace=${encodeURIComponent(market)}&q=${encodeURIComponent(q)}&limit=100`); renderCandidates(r.items||[]);
}
function renderCandidates(items){
  $('#candidateList').innerHTML=items.map(x=>`<div class="candidate"><div><div class="title">${x.title||x.stock_code||x.barcode||'Pazaryeri ürünü'}</div><div class="details">SKU: ${x.stock_code||'—'} · Barkod: ${x.barcode||'—'} · Fiyat: ${money(x.price)} · Stok: ${x.stock??'—'}</div></div><button data-id="${x.id}" data-sku="${encodeURIComponent(x.stock_code||'')}" data-barcode="${encodeURIComponent(x.barcode||'')}" data-pmid="${encodeURIComponent(x.product_main_id||'')}" data-title="${encodeURIComponent(x.title||'')}">Eşleştir</button></div>`).join('')||'<div class="candidate"><div><div class="title">Sonuç bulunamadı</div><div class="details">Farklı SKU, barkod veya ürün adıyla arayın.</div></div></div>';
  document.querySelectorAll('.candidate button').forEach(b=>b.onclick=()=>saveCandidate(b));
}
async function saveCandidate(b){
  if(!selectedUnresolved)return; const market=$('#mappingMarket').value;
  const vals={sku:decodeURIComponent(b.dataset.sku),barcode:decodeURIComponent(b.dataset.barcode),pmid:decodeURIComponent(b.dataset.pmid),title:decodeURIComponent(b.dataset.title)};
  let key='sku', value=vals.sku; if(!value&&vals.barcode){key='barcode';value=vals.barcode}else if(!value&&vals.pmid){key='pmid';value=vals.pmid}else if(!value&&vals.title){key='title';value=vals.title}
  await req('/api/mappings',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({marketplace:market,product_code:selectedUnresolved.product_code,match_key:key,match_value:value,marketplace_title:vals.title})});
  toast('Manuel eşleştirme kaydedildi. Kontrol yeniden çalıştırılıyor…'); await req('/api/check',{method:'POST'}); selectedUnresolved=null; $('#mappingEditor').classList.add('hidden'); $('#mappingEmpty').classList.remove('hidden'); await load(); await loadUnresolved();
}


async function loadDebug(){
  const market=$('#debugMarket').value;
  try{
    $('#debugContent').innerHTML='<div class="mapping-empty"><div class="empty-icon">⌁</div><h3>API okunuyor…</h3><p>'+market+' ilk kayıtları getiriliyor.</p></div>';
    const r=await req('/api/debug/'+encodeURIComponent(market.toLowerCase()));
    const items=r.items||[];
    const source=r.source==='cached_catalog'?'Kayıtlı katalog':'Ham API';
    $('#debugContent').innerHTML=items.map((x,i)=>`<div class="debug-card"><div class="debug-card-head">${market} · ${source} · Kayıt ${i+1}</div><pre>${escapeHtml(JSON.stringify(x,null,2))}</pre></div>`).join('') || '<div class="mapping-empty"><h3>Kayıt gelmedi</h3><p>Ana Pazarama kontrolünü bir kez çalıştırıp tekrar deneyin.</p></div>';
  }catch(e){
    $('#debugContent').innerHTML=`<div class="mapping-empty"><h3>Teşhis hatası</h3><p>${escapeHtml(e.message)}</p></div>`;
  }
}
function escapeHtml(v){
  return String(v??'').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));
}

async function checkSingleMarket(name){if(!name)return toast('Önce pazaryeri seç');try{toast(name+' kontrol ediliyor…');await req('/api/check/'+encodeURIComponent(name.toLowerCase()),{method:'POST'});toast(name+' kontrolü tamamlandı');await load();if($('#view-mapping').classList.contains('active'))await loadUnresolved()}catch(e){toast(e.message)}}

document.querySelectorAll('.nav').forEach(b=>b.onclick=async()=>{
async function loadDebug(){
  const market=$('#debugMarket').value;
  try{
    $('#debugContent').innerHTML='<div class="mapping-empty"><div class="empty-icon">⌁</div><h3>API okunuyor…</h3><p>'+market+' ilk kayıtları getiriliyor.</p></div>';
    const r=await req('/api/debug/'+encodeURIComponent(market.toLowerCase()));
    const items=r.items||[];
    const source=r.source==='cached_catalog'?'Kayıtlı katalog':'Ham API';
    $('#debugContent').innerHTML=items.map((x,i)=>`<div class="debug-card"><div class="debug-card-head">${market} · ${source} · Kayıt ${i+1}</div><pre>${escapeHtml(JSON.stringify(x,null,2))}</pre></div>`).join('') || '<div class="mapping-empty"><h3>Kayıt gelmedi</h3><p>Ana Pazarama kontrolünü bir kez çalıştırıp tekrar deneyin.</p></div>';
  }catch(e){
    $('#debugContent').innerHTML=`<div class="mapping-empty"><h3>Teşhis hatası</h3><p>${escapeHtml(e.message)}</p></div>`;
  }
}
function escapeHtml(v){
  return String(v??'').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));
}

async function checkSingleMarket(name){if(!name)return toast('Önce pazaryeri seç');try{toast(name+' kontrol ediliyor…');await req('/api/check/'+encodeURIComponent(name.toLowerCase()),{method:'POST'});toast(name+' kontrolü tamamlandı');await load();if($('#view-mapping').classList.contains('active'))await loadUnresolved()}catch(e){toast(e.message)}}

document.querySelectorAll('.nav').forEach(x=>x.classList.remove('active'));b.classList.add('active');document.querySelectorAll('.view').forEach(x=>x.classList.remove('active'));$('#view-'+b.dataset.view).classList.add('active');if(b.dataset.view==='mapping')await loadUnresolved()});
$('#search').oninput=renderChecks; $('#statusFilter').onchange=renderChecks; $('#riskOnly').onchange=renderChecks; $('#productSearch').oninput=renderProducts; $('#mappingMarket').onchange=()=>{selectedUnresolved=null;$('#mappingEditor').classList.add('hidden');$('#mappingEmpty').classList.remove('hidden');loadUnresolved()}; $('#unresolvedSearch').oninput=renderUnresolved; let timer; $('#candidateSearch').oninput=()=>{clearTimeout(timer);timer=setTimeout(loadCandidates,250)}; $('#refreshSuggestions').onclick=loadSuggestions;
$('#debugBtn').onclick=loadDebug;
$('#singleCheckBtn').onclick=()=>checkSingleMarket($('#singleMarket').value);
$('#syncBtn').onclick=async()=>{try{toast('T-Soft senkronu başladı');let r=await req('/api/sync/tsoft',{method:'POST'});toast(r.count+' ürün güncellendi');await load()}catch(e){toast(e.message)}};
$('#checkBtn').onclick=async()=>{try{toast('Tüm bağlı pazaryerleri kontrol ediliyor');await req('/api/check',{method:'POST'});toast('Kontrol tamamlandı');await load()}catch(e){toast(e.message)}};
load().catch(e=>toast(e.message)); setInterval(()=>load().catch(()=>{}),60000);

if($('#availabilityMarket')) $('#availabilityMarket').onchange=renderAvailability;
if($('#availabilityStatus')) $('#availabilityStatus').onchange=renderAvailability;
if($('#availabilitySearch')) $('#availabilitySearch').oninput=renderAvailability;

if($('#notifyTestBtn')) $('#notifyTestBtn').onclick=async()=>{
  try{
    const b=$('#notifyTestBtn');
    const old=b.textContent;b.disabled=true;b.textContent='Gönderiliyor…';
    const r=await req('/api/notifications/test',{method:'POST'});
    toast(r.message||'Test bildirimi gönderildi.');
    b.textContent=old;b.disabled=false;
  }catch(e){
    toast('Bildirim hatası: '+e.message);
    $('#notifyTestBtn').disabled=false;
    $('#notifyTestBtn').textContent='🔔 Bildirimi Test Et';
  }
};

document.querySelectorAll('.nav').forEach(btn=>{
  btn.addEventListener('click',()=>setTimeout(()=>animateView(document.querySelector('.view.active')),0));
});

if($('#opsRefreshBtn')) $('#opsRefreshBtn').onclick=loadOperations;
if($('#opsCheckAllBtn')) $('#opsCheckAllBtn').onclick=async()=>{document.querySelector('#checkBtn')?.click();setTimeout(loadOperations,1200)};
if($('#opsActionMarket')) $('#opsActionMarket').onchange=renderOpsActions;
if($('#opsActionSearch')) $('#opsActionSearch').oninput=renderOpsActions;
if($('#opsProductSearch')) $('#opsProductSearch').oninput=renderOpsProducts;
if($('#cpTestBtn')) $('#cpTestBtn').onclick=loadConnectProfHealth;
loadOperations();


function bindHepsiburadaDiagnostics(){
  const btn=document.getElementById('hbDiagBtn');
  if(!btn) return;
  // Avoid duplicate handlers when views are re-rendered.
  if(btn.dataset.bound==='1') return;
  btn.dataset.bound='1';
  btn.addEventListener('click', async (ev)=>{
    ev.preventDefault();
    ev.stopPropagation();
    try{
      await runHbDiagnostics();
    }catch(err){
      console.error('Hepsiburada teşhis hatası:',err);
      const msg=document.getElementById('hbDiagMessage');
      if(msg){
        msg.className='hb-diag-message error';
        msg.innerHTML=`<b>Teşhis Hatası</b><span>${escapeHtml(err?.message||String(err))}</span>`;
      }
      toast('Hepsiburada teşhis hatası: '+(err?.message||String(err)));
    }
  });
}

if(document.readyState==='loading'){
  document.addEventListener('DOMContentLoaded',bindHepsiburadaDiagnostics);
}else{
  bindHepsiburadaDiagnostics();
}



async function hbWebDiagnostics(){
  const msg=$('#hbWebState'),btn=$('#hbWebTestBtn');
  if(btn){btn.disabled=true;btn.textContent='Test ediliyor…'}
  if(msg) msg.innerHTML='<b>Web bağlantısı test ediliyor…</b><span>Hepsiburada herkese açık sayfasına bağlanılıyor.</span>';
  try{
    const r=await req('/api/hepsiburada/web/diagnostics');
    if(msg){
      msg.className='hb-diag-message '+(r.ok?'ok':'error');
      msg.innerHTML=`<b>${r.ok?'Web Okuma Hazır':'Web Okuma Başarısız'}</b><span>${escapeHtml(r.message||'')}</span><small>Bulunan ürün linki: ${r.candidate_links??0}</small>`;
    }
  }catch(e){
    if(msg){msg.className='hb-diag-message error';msg.innerHTML=`<b>Web Okuma Hatası</b><span>${escapeHtml(e.message)}</span>`}
  }finally{if(btn){btn.disabled=false;btn.textContent='Web Erişimini Test Et'}}
}

async function hbWebReadProduct(){
  const q=($('#hbWebQuery')?.value||'').trim();
  if(!q){toast('ET barkod veya ürün kodu gir.');return}
  const btn=$('#hbWebReadBtn'),box=$('#hbWebResult');
  if(btn){btn.disabled=true;btn.textContent='Okunuyor…'}
  if(box) box.innerHTML='<div class="ops-empty"><b>Hepsiburada aranıyor…</b><span>Ürün sayfası ve satıcı fiyatı kontrol ediliyor.</span></div>';
  try{
    const r=await req('/api/hepsiburada/web/product/'+encodeURIComponent(q));
    if(r.ambiguous){
      box.innerHTML=`<div class="hb-web-warning"><b>Barkod tekil değil</b><span>${escapeHtml(r.message)}</span>${(r.candidates||[]).map(x=>`<code>${escapeHtml(x.product_code)} · ${escapeHtml(x.name||'')}</code>`).join('')}</div>`;
      return;
    }
    if(!r.ok||!r.matched){
      box.innerHTML=`<div class="hb-web-warning"><b>Güvenilir eşleşme bulunamadı</b><span>${escapeHtml(r.error||'Ürün sayfası doğrulanamadı.')}</span></div>`;
      return;
    }
    const trusted=r.trusted_price;
    box.innerHTML=`<article class="hb-web-product ${trusted?'trusted':'review'}">
      <div><span>ÜRÜN</span><h4>${escapeHtml(r.title||'—')}</h4><code>${escapeHtml(r.tsoft_barcode||r.product_code||'—')}</code></div>
      <div><span>WEB FİYATI</span><strong>${money(r.price||0)}</strong><small>${trusted?'Topaloğlu satıcısı doğrulandı':'Satıcı doğrulanamadı — alarma dahil edilmez'}</small></div>
      <div><span>SATICI</span><b>${escapeHtml(r.seller||'Doğrulanamadı')}</b><small>Eşleşme skoru ${r.score??0}</small></div>
      <div><a href="${escapeHtml(r.url||'#')}" target="_blank" rel="noreferrer">Ürün sayfasını aç ↗</a></div>
    </article>`;
  }catch(e){
    box.innerHTML=`<div class="hb-web-warning"><b>Web okuma hatası</b><span>${escapeHtml(e.message)}</span></div>`;
  }finally{if(btn){btn.disabled=false;btn.textContent="Web'den Ürünü Oku"}}
}

function bindHbWebReader(){
  $('#hbWebTestBtn')?.addEventListener('click',hbWebDiagnostics);
  $('#hbWebReadBtn')?.addEventListener('click',hbWebReadProduct);
  $('#hbWebQuery')?.addEventListener('keydown',e=>{if(e.key==='Enter')hbWebReadProduct()});
}
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',bindHbWebReader);else bindHbWebReader();



let UPDATE_STATE=null;
async function checkForUpdate(showToast=true){
  const btn=$('#updateCheckBtn');
  if(btn){btn.disabled=true;btn.textContent='Kontrol ediliyor…'}
  try{
    const r=await req('/api/update/check');
    UPDATE_STATE=r;
    $('#updateVersion').textContent='v'+(r.current||'10.0.0');
    const dot=$('#updateDot'), install=$('#updateInstallBtn');
    if(r.ok&&r.available){
      dot?.classList.add('available');
      if(install){install.classList.remove('hidden');install.textContent='v'+r.latest+' Güncelle'}
      if(btn)btn.textContent='Güncelleme Var';
      if(showToast)toast('Yeni sürüm hazır: v'+r.latest);
    }else{
      dot?.classList.remove('available');
      install?.classList.add('hidden');
      if(btn)btn.textContent=r.ok?'Güncel':'Güncelleme Kanalı Bekleniyor';
      if(showToast)toast(r.message||'Uygulama güncel.');
    }
  }catch(e){
    if(btn)btn.textContent='Tekrar Kontrol Et';
    if(showToast)toast('Güncelleme kontrolü: '+e.message);
  }finally{if(btn)btn.disabled=false}
}
async function installUpdate(){
  const btn=$('#updateInstallBtn');
  if(!UPDATE_STATE?.available){await checkForUpdate(true);if(!UPDATE_STATE?.available)return}
  if(btn){btn.disabled=true;btn.textContent='İndiriliyor…'}
  try{
    const r=await req('/api/update/install',{method:'POST'});
    toast(r.message||'Güncelleme hazırlanıyor…');
    if(btn)btn.textContent='Yeniden başlatılıyor…';
  }catch(e){
    toast('Güncelleme başarısız: '+e.message);
    if(btn){btn.disabled=false;btn.textContent='Tekrar Güncelle'}
  }
}
function bindUpdater(){
  $('#updateCheckBtn')?.addEventListener('click',()=>checkForUpdate(true));
  $('#updateInstallBtn')?.addEventListener('click',installUpdate);
  setTimeout(()=>checkForUpdate(false),2500);
}
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',bindUpdater);else bindUpdater();


async function hbExtensionStatus(){const box=$('#hbExtensionStatus'),btn=$('#hbExtensionStatusBtn');if(btn){btn.disabled=true;btn.textContent='Kontrol ediliyor…'}try{await req('/api/hepsiburada/extension/status');if(box){box.className='hb-diag-message ok';box.innerHTML='<b>Yerel bağlantı hazır</b><span>Chrome eklentisi bu uygulamaya veri gönderebilir.</span>'}}catch(e){if(box){box.className='hb-diag-message error';box.innerHTML=`<b>Bağlantı hazır değil</b><span>${escapeHtml(e.message)}</span>`}}finally{if(btn){btn.disabled=false;btn.textContent='Eklenti Bağlantısını Kontrol Et'}}}
function bindHbExtension(){ $('#hbExtensionStatusBtn')?.addEventListener('click',hbExtensionStatus); }
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',bindHbExtension);else bindHbExtension();


let PRICE_PROTECTION_SELECTED=new Set(markets);
async function loadPriceProtectionMarkets(){
  try{
    const r=await req('/api/price-protection/markets');
    PRICE_PROTECTION_SELECTED=new Set(r.selected||[]);
    renderPriceProtectionMarkets();
  }catch(e){console.error('Fiyat koruma kapsamı alınamadı',e)}
}
function renderPriceProtectionMarkets(){
  const box=$('#protectionMarketPills');if(!box)return;
  box.innerHTML=markets.map(m=>`<button class="protection-market-pill ${PRICE_PROTECTION_SELECTED.has(m)?'active':''}" data-protection-market="${m}"><i></i>${m}</button>`).join('');
  box.querySelectorAll('[data-protection-market]').forEach(btn=>btn.onclick=async()=>{
    const m=btn.dataset.protectionMarket;
    if(PRICE_PROTECTION_SELECTED.has(m))PRICE_PROTECTION_SELECTED.delete(m);else PRICE_PROTECTION_SELECTED.add(m);
    await savePriceProtectionMarkets();
  });
}
async function savePriceProtectionMarkets(){
  const r=await req('/api/price-protection/markets',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({selected:[...PRICE_PROTECTION_SELECTED]})});
  PRICE_PROTECTION_SELECTED=new Set(r.selected||[]);renderPriceProtectionMarkets();
  toast(PRICE_PROTECTION_SELECTED.size?`${PRICE_PROTECTION_SELECTED.size} pazaryeri kontrol edilecek.`:'Tüm pazaryeri kontrolleri durduruldu.');
}
function bindProtectionPicker(){
  $('#protectionAllBtn')?.addEventListener('click',async()=>{PRICE_PROTECTION_SELECTED=new Set(markets);await savePriceProtectionMarkets()});
  $('#protectionResetBtn')?.addEventListener('click',async()=>{
    const r=await req('/api/price-protection/markets/reset',{method:'POST'});
    PRICE_PROTECTION_SELECTED=new Set(r.selected||[]);renderPriceProtectionMarkets();toast('Pazaryeri kontrol seçimi sıfırlandı.');
  });
  loadPriceProtectionMarkets();
}
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',bindProtectionPicker);else bindProtectionPicker();


// v10.1.2 premium exclusion studio
let EXCLUSION_RULES=[];const exclusionLabels={product:'Tek ürün',name:'İsim kuralı',category:'Kategori'};
async function loadExclusions1012(){try{const r=await req('/api/price-protection/exclusions');EXCLUSION_RULES=r.rules||[];renderExclusions1012();if($('#excludedRuleCount'))$('#excludedRuleCount').textContent=EXCLUSION_RULES.filter(x=>Number(x.enabled)!==0).length}catch(e){console.error(e)}}
function renderExclusions1012(){const box=$('#exclusionRules');if(!box)return;if(!EXCLUSION_RULES.length){box.innerHTML='<div class="exclusion-empty"><b>Henüz hariç kuralı yok</b><span>Özel fiyatlı ürünleri alarm ekranından çıkarmak için yukarıdan kural ekle.</span></div>';return}box.innerHTML=EXCLUSION_RULES.map(r=>`<article class="exclusion-rule ${Number(r.enabled)?'':'disabled'}"><div class="exclusion-rule-icon">${r.mode==='EXCLUDE'?'×':'◌'}</div><div class="exclusion-rule-main"><div><span>${exclusionLabels[r.match_type]||r.match_type}</span><b>${escapeHtml(r.match_value)}</b></div><small>${r.marketplace==='*'?'Tüm pazaryerleri':escapeHtml(r.marketplace)} · ${r.mode==='EXCLUDE'?'Tam hariç':'Sessiz izle'}</small></div><button data-rule-toggle="${r.id}" data-enabled="${Number(r.enabled)?0:1}">${Number(r.enabled)?'Pasifleştir':'Aktifleştir'}</button><button class="rule-delete" data-rule-delete="${r.id}">Sil</button></article>`).join('');box.querySelectorAll('[data-rule-delete]').forEach(b=>b.onclick=async()=>{await req('/api/price-protection/exclusions/'+b.dataset.ruleDelete,{method:'DELETE'});await loadExclusions1012();await refreshWallboardV1010();toast('Hariç kuralı kaldırıldı.')});box.querySelectorAll('[data-rule-toggle]').forEach(b=>b.onclick=async()=>{await req('/api/price-protection/exclusions/'+b.dataset.ruleToggle+'/toggle',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({enabled:Number(b.dataset.enabled)===1})});await loadExclusions1012();await refreshWallboardV1010()})}
async function addExclusion1012(preset){const value=(preset||$('#exclusionValue')?.value||'').trim();if(!value){toast('Hariç bırakılacak ürün veya kuralı yaz.');return}const payload={match_type:preset?'name':$('#exclusionType').value,match_value:value,mode:preset?'EXCLUDE':$('#exclusionMode').value,marketplace:preset?'*':$('#exclusionMarket').value};const b=$('#exclusionAddBtn');try{if(b)b.disabled=true;await req('/api/price-protection/exclusions',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});if($('#exclusionValue'))$('#exclusionValue').value='';await loadExclusions1012();await refreshWallboardV1010();toast(`${value} kuralı eklendi.`)}catch(e){toast(e.message)}finally{if(b)b.disabled=false}}
function ensureWallTools1012(){const tools=document.querySelector('.wall-tools');if(!tools||$('#wallRefresh1012'))return;const refresh=document.createElement('button');refresh.id='wallRefresh1012';refresh.className='wall-btn subtle';refresh.textContent='Yenile';refresh.onclick=async()=>{await refreshWallboardV1010();toast('Ekran yenilendi.')};const reset=document.createElement('button');reset.id='wallReset1012';reset.className='wall-btn danger';reset.textContent='Kritikleri Sıfırla';reset.onclick=async()=>{reset.disabled=true;try{const r=await req('/api/price-protection/critical/reset',{method:'POST'});await refreshWallboardV1010();toast(`${r.cleared_rows||0} kritik/uyarı temizlendi.`)}catch(e){toast(e.message)}finally{reset.disabled=false}};tools.append(refresh,reset)}
function bindPremium1012(){$('#exclusionAddBtn')?.addEventListener('click',()=>addExclusion1012());$('#exclusionValue')?.addEventListener('keydown',e=>{if(e.key==='Enter')addExclusion1012()});document.querySelectorAll('[data-preset]').forEach(b=>b.onclick=()=>addExclusion1012(b.dataset.preset));ensureWallTools1012();loadExclusions1012()}
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',bindPremium1012);else bindPremium1012();


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
    api1013('/api/settings/alert-tolerance').then(r=>{const i=document.querySelector('#toleranceInput1013');if(i)i.value=r.value??1300}).catch(()=>{});
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
