from pathlib import Path
import re

ROOT=Path('_desktop_src')
apps=[p for p in ROOT.iterdir() if p.is_dir() and (p/'app').is_dir()]
if not apps: raise SystemExit('desktop source root not found')
APP=apps[0]

# Desktop version
launcher=APP/'desktop_launcher.py'
s=launcher.read_text(encoding='utf-8').replace('VERSION = "10.2.10"','VERSION = "10.2.11"')
launcher.write_text(s,encoding='utf-8')
iss=APP/'desktop_installer.iss'
s=iss.read_text(encoding='utf-8').replace('#define MyAppVersion "10.2.10"','#define MyAppVersion "10.2.11"').replace('Topaloglu-Pazaryeri-Merkezi-Setup-10.2.10','Topaloglu-Pazaryeri-Merkezi-Setup-10.2.11')
iss.write_text(s,encoding='utf-8')
(APP/'DESKTOP_VERSION.txt').write_text('10.2.11\n',encoding='utf-8')

# Backend: use the application's real marketplace matcher for extension imports.
main=APP/'app/main.py'
s=main.read_text(encoding='utf-8')
s=s.replace('"version":"10.2.10","mode":"extension"','"version":"10.2.11","mode":"extension"')

start=s.find('@app.post("/api/hepsiburada/extension/import")')
end=s.find('@app.get("/api/hepsiburada/web/diagnostics")', start)
if start < 0 or end < 0:
    raise SystemExit('Hepsiburada extension import block not found')

new_import=r'''@app.post("/api/hepsiburada/extension/import")
async def hepsiburada_extension_import(payload:dict=Body(...)):
    incoming=payload.get("rows") or []
    if not isinstance(incoming,list):
        raise HTTPException(400,"rows listesi geçersiz")

    # Only ET stock/barcode rows are allowed into the project.
    rows=[]
    for raw in incoming[:500]:
        if not isinstance(raw,dict):
            continue
        barcode=str(raw.get("barcode") or "").strip()
        sku=str(raw.get("stock_code") or "").strip()
        if "ET" not in barcode.upper() and "ET" not in sku.upper():
            continue
        try: price=float(raw.get("price") or 0)
        except Exception: price=0.0
        try: stock=float(raw.get("stock") or 0) if raw.get("stock") is not None else 1.0
        except Exception: stock=1.0
        rows.append({
            "barcode":barcode,
            "stock_code":sku,
            "product_main_id":"HB_EXTENSION",
            "title":str(raw.get("title") or "").strip(),
            "price":price,
            "stock":stock,
            "commission":0,
            "active":stock>0,
        })

    products=db.list_products()
    idx=service.make_indexes(rows)
    saved=matched=review=loss=critical=warning=stock_zero=closed=0
    used=set()
    details=[]

    def sig(r):
        return (
            str(r.get("barcode") or ""),str(r.get("stock_code") or ""),
            str(r.get("title") or ""),float(r.get("price") or 0),float(r.get("stock") or 0)
        )

    for p in products:
        exclusion=db.exclusion_mode(p,"Hepsiburada")
        if exclusion=="EXCLUDE":
            continue

        market,method=service.match_product(p,idx,"Hepsiburada",rows)
        if not market:
            continue

        matched+=1
        used.add(sig(market))
        try:
            row=service.evaluate(p,market,method or "HB CHROME","Hepsiburada")
            if exclusion=="SILENT" and row.get("status") in {"LOSS","CRITICAL","WARNING"}:
                row["status"]="IGNORED"
                row["error"]="Sessiz izleme kuralı: alarm üretilmedi."
            db.upsert_market(row)
            saved+=1
            st=row.get("status")
            if st=="LOSS": loss+=1
            elif st=="CRITICAL": critical+=1
            elif st=="WARNING": warning+=1
            elif st=="REVIEW": review+=1
            elif st=="STOK YOK": stock_zero+=1
            elif st=="SATIŞA KAPALI": closed+=1
            details.append({
                "product_code":p.get("product_code"),
                "tsoft_barcode":p.get("barcode"),
                "marketplace_sku":market.get("stock_code"),
                "status":st,
                "price":row.get("current_price"),
                "match_method":method,
            })
        except Exception as e:
            review+=1
            details.append({
                "product_code":p.get("product_code"),
                "marketplace_sku":market.get("stock_code"),
                "status":"REVIEW","error":str(e)
            })

    unresolved=max(0,len(rows)-len(used))
    now_value=service.now()

    # Keep the operational/dashboard runtime in sync with direct marketplace connectors.
    db.runtime_set("Hepsiburada_extension_last_import_count",len(rows))
    db.runtime_set("Hepsiburada_extension_last_saved",saved)
    db.runtime_set("Hepsiburada_extension_last_matched",matched)
    db.runtime_set("Hepsiburada_extension_last_unresolved",unresolved)
    db.runtime_set("Hepsiburada_extension_last_import_at",now_value)
    db.runtime_set("Hepsiburada_product_count",len(rows))
    db.runtime_set("Hepsiburada_matched",matched)
    db.runtime_set("Hepsiburada_unresolved",unresolved)
    db.runtime_set("last_Hepsiburada_success",now_value)

    # Keep the currently scanned HB page available for diagnostics/manual mapping.
    db.replace_catalog("Hepsiburada",rows)

    db.log(
        "INFO",
        f"Hepsiburada Chrome: {len(rows)} alındı, {matched} T-Soft ürünü eşleşti, "
        f"{saved} fiyat kontrolüne kaydedildi, {unresolved} satır eşleşmedi, "
        f"{loss} zarar, {critical} kritik.",
        "Hepsiburada"
    )

    return {
        "ok":True,
        "imported":len(rows),"matched":matched,"saved":saved,"unresolved":unresolved,
        "review":review,"loss":loss,"critical":critical,"warning":warning,
        "stock_zero":stock_zero,"closed":closed,
        "rows":details[:100]
    }

'''
s=s[:start]+new_import+s[end:]

# Status endpoint: expose real result, not just 'received'.
old='''      "last_import_count":int(rt.get("Hepsiburada_extension_last_import_count") or 0),\n      "last_saved":int(rt.get("Hepsiburada_extension_last_saved") or 0)\n'''
new='''      "last_import_count":int(rt.get("Hepsiburada_extension_last_import_count") or 0),\n      "last_saved":int(rt.get("Hepsiburada_extension_last_saved") or 0),\n      "last_matched":int(rt.get("Hepsiburada_extension_last_matched") or 0),\n      "last_unresolved":int(rt.get("Hepsiburada_extension_last_unresolved") or 0)\n'''
if old in s:
    s=s.replace(old,new,1)
main.write_text(s,encoding='utf-8')

# Extension v1.3.0: popup waits for actual backend result and reports matched/saved/unresolved.
EXT=APP/'chrome-extension'
manifest=(EXT/'manifest.json').read_text(encoding='utf-8').replace('"version": "1.2.0"','"version": "1.3.0"').replace('v1.2.0','v1.3.0')
(EXT/'manifest.json').write_text(manifest,encoding='utf-8')

bg=(EXT/'background.js').read_text(encoding='utf-8').replace("const VERSION='1.2.0'","const VERSION='1.3.0'")
# Store the complete server result for the popup/status UI.
bg=bg.replace("message:`${j.saved||0} ürün aktarıldı`,saved:j.saved||0,matched:j.matched||0,at:new Date().toISOString(),port,version:VERSION",
              "message:`${j.imported||0} alındı · ${j.matched||0} eşleşti · ${j.saved||0} kaydedildi · ${j.unresolved||0} eşleşmedi`,saved:j.saved||0,matched:j.matched||0,imported:j.imported||0,unresolved:j.unresolved||0,critical:j.critical||0,loss:j.loss||0,at:new Date().toISOString(),port,version:VERSION")
(EXT/'background.js').write_text(bg,encoding='utf-8')

content=(EXT/'content.js').read_text(encoding='utf-8').replace('__TOPOLOGLU_HB_CONTENT_120__','__TOPOLOGLU_HB_CONTENT_130__').replace("version:'1.2.0'","version:'1.3.0'")
(EXT/'content.js').write_text(content,encoding='utf-8')

popup=(EXT/'popup.html').read_text(encoding='utf-8').replace('v1.2.0','v1.3.0')
(EXT/'popup.html').write_text(popup,encoding='utf-8')

pjs=(EXT/'popup.js').read_text(encoding='utf-8').replace('1.2.0','1.3.0')
oldscan="if(r.count>0)state(`✓ ${r.count} ET satırı bulundu ve gönderildi.`,'ok');else state('ET kodu ve fiyat içeren satır bulunamadı. Ürün/listing tablosunu açın.','err')"
newscan="if(r.count>0){state(`✓ ${r.count} ET satırı bulundu. Uygulama sonucu bekleniyor…`,'ok');await new Promise(x=>setTimeout(x,1300));const z=await chrome.storage.local.get('hbStatus');const d=z.hbStatus||{};if(d.ok)state(`✓ ${d.imported||r.count} alındı · ${d.matched||0} eşleşti · ${d.saved||0} kaydedildi · ${d.unresolved||0} eşleşmedi`,'ok');else state('✕ '+(d.message||'Uygulama sonucu alınamadı.'),'err')}else state('ET kodu ve fiyat içeren satır bulunamadı. Ürün/listing tablosunu açın.','err')"
if oldscan not in pjs:
    raise SystemExit('popup scan result marker missing')
pjs=pjs.replace(oldscan,newscan,1)
(EXT/'popup.js').write_text(pjs,encoding='utf-8')

# Desktop Hepsiburada settings card: show the actual import funnel.
bridge=APP/'app/static/hepsiburada_bridge.js'
b=bridge.read_text(encoding='utf-8')
b=b.replace("const last=d.last_import_at?`Son aktarım: ${d.last_import_at} · ${d.last_saved||0} kayıt`:'Henüz veri alınmadı';",
            "const last=d.last_import_at?`Son aktarım: ${d.last_import_at} · ${d.last_import_count||0} alındı · ${d.last_matched||0} eşleşti · ${d.last_saved||0} kaydedildi · ${d.last_unresolved||0} eşleşmedi`:'Henüz veri alınmadı';")
bridge.write_text(b,encoding='utf-8')

# UI cache/version bump
idx=APP/'app/static/index.html'
h=idx.read_text(encoding='utf-8').replace('v10.2.10','v10.2.11')
h=re.sub(r'/static/hepsiburada_bridge\\.js(?:\\?v=[^"\\\']*)?', '/static/hepsiburada_bridge.js?v=10.2.11', h)
idx.write_text(h,encoding='utf-8')

# Build-time assertions
m=main.read_text(encoding='utf-8')
assert 'service.match_product(p,idx,"Hepsiburada",rows)' in m
assert 'Hepsiburada_extension_last_matched' in m
assert 'last_Hepsiburada_success' in m
assert '1.3.0' in (EXT/'manifest.json').read_text(encoding='utf-8')
assert 'Uygulama sonucu bekleniyor' in (EXT/'popup.js').read_text(encoding='utf-8')
print(APP)
