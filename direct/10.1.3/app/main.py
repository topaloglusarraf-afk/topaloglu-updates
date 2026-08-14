from pathlib import Path
from fastapi import FastAPI,HTTPException,Query,Body
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from .config import settings
from .notifier import send_price_risk_notification
from . import db
from . import updater
from . import service
from .service import sync_tsoft,run_cycle,run_marketplace_only, run_single_product
from .commissions import COMMISSION_RATES,GROUPS
from .connectors.idefix import fetch_debug_sample as idefix_debug_sample
from .connectors.pazarama import fetch_debug_sample as pazarama_debug_sample
from .connectors import connectprof as connectprof_api
from .connectors import hepsiburada as hepsiburada_api
from .connectors import hepsiburada_web as hepsiburada_web_api

class MappingPayload(BaseModel):
    marketplace:str
    product_code:str
    match_key:str
    match_value:str
    marketplace_title:str=""

app=FastAPI(title=settings.app_name)
BASE=Path(__file__).parent
app.mount("/static",StaticFiles(directory=BASE/"static"),name="static")
scheduler=AsyncIOScheduler()

@app.on_event("startup")
async def startup():
    db.init_db()
    try:
        saved=db.runtime_all().get("alert_tolerance_tl")
        if saved not in (None,""):
            settings.alert_tolerance_tl=float(saved)
    except Exception:
        pass
    if not scheduler.running:
        scheduler.add_job(run_cycle,"interval",minutes=settings.interval_minutes,id="cycle",
                          replace_existing=True,max_instances=1,coalesce=True)
        scheduler.start()

@app.get("/")
def home():
    return FileResponse(BASE/"static"/"index.html",headers={"Cache-Control":"no-store, no-cache, must-revalidate, max-age=0"})

@app.get("/api/health")
def health():
    return {"ok":True,"interval":settings.interval_minutes,"alert_tolerance_tl":settings.alert_tolerance_tl,
            "connections":{"T-Soft":bool(settings.tsoft_base_url and settings.tsoft_token),
            "Trendyol":settings.trendyol_enabled,"Hepsiburada":settings.hepsiburada_enabled,
            "N11":settings.n11_enabled,"Idefix":settings.idefix_enabled,"Pazarama":settings.pazarama_enabled}}


@app.post("/api/notifications/test")
async def test_desktop_notification():
    try:
        checks=db.list_checks()
        result=send_price_risk_notification(checks,force=True)
        if result.get("count",0)==0:
            # Risk yokken de test bildirimi göster.
            from .notifier import _send_windows
            ok=_send_windows("Topaloğlu Fiyat Koruma","Masaüstü bildirimleri aktif. 5 dakikalık kontrollerde yeni fiyat riski oluşursa bildirim alacaksınız.")
            return {"ok":ok,"message":"Test bildirimi gönderildi." if ok else "Windows bildirimi gönderilemedi."}
        return {"ok":bool(result.get("sent")),"message":f"{result.get('count',0)} risk için test bildirimi gönderildi."}
    except Exception as e:
        raise HTTPException(500,str(e))





@app.get("/api/hepsiburada/extension/status")
async def hepsiburada_extension_status():
    return {"ok":True,"version":"10.0.2","message":"Chrome eklentisi bağlantısı hazır."}

@app.post("/api/hepsiburada/extension/import")
async def hepsiburada_extension_import(payload:dict=Body(...)):
    rows=payload.get("rows") or []
    if not isinstance(rows,list): raise HTTPException(400,"rows listesi geçersiz")
    rows=rows[:500]; products=db.list_products(); matched=review=unresolved=saved=0
    import re as _re, unicodedata as _ud
    def n(v):
        s=str(v or "").strip().lower().replace("ı","i"); s=_ud.normalize("NFKD",s); s="".join(c for c in s if not _ud.combining(c)); return _re.sub(r"[^a-z0-9]+","",s)
    by_code={}; by_barcode={}
    for p in products:
        for key in (p.get("product_code"),p.get("supplier_product_code")):
            if key: by_code.setdefault(n(key),[]).append(p)
        if p.get("barcode"): by_barcode.setdefault(n(p.get("barcode")),[]).append(p)
    result=[]
    for r in rows:
        barcode=str(r.get("barcode") or "").strip(); sku=str(r.get("stock_code") or "").strip(); title=str(r.get("title") or "").strip(); price=r.get("price"); stock=r.get("stock")
        candidates=[]
        for key in (barcode,sku):
            nk=n(key)
            if nk: candidates += by_barcode.get(nk,[])+by_code.get(nk,[])
        uniq=[]; seen=set()
        for p in candidates:
            pc=str(p.get("product_code") or "")
            if pc not in seen: seen.add(pc); uniq.append(p)
        target=None
        if len(uniq)==1: target=uniq[0]
        elif len(uniq)>1 and title:
            exact=[p for p in uniq if n(p.get("name"))==n(title)]
            if len(exact)==1: target=exact[0]
        if not target and title:
            exact=[p for p in products if n(p.get("name"))==n(title)]
            if len(exact)==1: target=exact[0]
        item={"barcode":barcode,"stock_code":sku,"title":title,"price":price,"stock":stock}
        if not target:
            unresolved+=1; item["match_status"]="UNRESOLVED"; result.append(item); continue
        market={"barcode":barcode or target.get("barcode"),"stock_code":sku,"product_main_id":"HB_EXTENSION","title":title or target.get("name"),"price":float(price or 0),"stock":float(stock or 0) if stock is not None else 1,"commission":0,"active":None if stock is None else float(stock or 0)>0}
        try:
            if float(price or 0)<=0:
                row=service.base_row(target,market,"CHROME_EXTENSION","Hepsiburada","REVIEW","Chrome eklentisi ürünü eşleştirdi ancak fiyat okunamadı."); review+=1
            else:
                row=service.evaluate(target,market,"CHROME_EXTENSION","Hepsiburada"); matched+=1
            db.upsert_market(row); saved+=1; item["match_status"]=row.get("status"); item["product_code"]=target.get("product_code")
        except Exception as e:
            review+=1; item["match_status"]="REVIEW"; item["error"]=str(e)
        result.append(item)
    db.runtime_set("Hepsiburada_extension_last_import_count",len(rows)); db.runtime_set("Hepsiburada_extension_last_saved",saved)
    db.log("INFO",f"Hepsiburada Chrome eklentisi: {len(rows)} satır, {matched} eşleşti, {review} incelenecek, {unresolved} eşleşmedi.","Hepsiburada")
    return {"ok":True,"imported":len(rows),"saved":saved,"matched":matched,"review":review,"unresolved":unresolved,"rows":result[:100]}

@app.get("/api/hepsiburada/web/diagnostics")
async def hepsiburada_web_diagnostics():
    return await hepsiburada_web_api.diagnostics()

@app.get("/api/hepsiburada/web/product/{query}")
async def hepsiburada_web_product(query: str):
    products=db.list_products()
    nq=query.strip().lower()
    candidates=[]
    for p in products:
        values=[
            str(p.get("product_code") or ""),
            str(p.get("barcode") or ""),
            str(p.get("supplier_product_code") or ""),
        ]
        if any(v.lower()==nq for v in values if v):
            candidates.append(p)
    if not candidates:
        # exact-ish name fallback
        candidates=[p for p in products if nq and nq in str(p.get("name") or "").lower()]
    if not candidates:
        raise HTTPException(status_code=404,detail="T-Soft ürünü bulunamadı.")
    if len(candidates)>1:
        # duplicate ET is possible; refuse arbitrary selection unless exact product code uniquely resolves.
        exact_code=[p for p in candidates if str(p.get("product_code") or "").lower()==nq]
        if len(exact_code)==1:
            candidates=exact_code
        else:
            return {"ok":False,"ambiguous":True,"message":"Bu barkod birden fazla T-Soft ürününde kullanılıyor. Daha özel ürün koduyla arayın.",
                    "candidates":[{"product_code":p.get("product_code"),"barcode":p.get("barcode"),"name":p.get("name")} for p in candidates[:20]]}
    return await hepsiburada_web_api.find_product(candidates[0])

@app.get("/api/hepsiburada/web/batch")
async def hepsiburada_web_batch(limit: int = 10):
    limit=max(1,min(limit,getattr(settings,"hepsiburada_web_batch_size",10),25))
    products=[p for p in db.list_products() if float(p.get("stock") or 0)>0][:limit]
    results=[]
    for p in products:
        try:
            results.append(await hepsiburada_web_api.find_product(p))
        except Exception as e:
            results.append({"ok":False,"product_code":p.get("product_code"),"barcode":p.get("barcode"),"error":str(e)})
    return {"count":len(results),"results":results}

@app.get("/api/hepsiburada/diagnostics")
async def hepsiburada_diagnostics():
    return await hepsiburada_api.diagnostics()

@app.get("/api/connectprof/health")
async def connectprof_health():
    return await connectprof_api.health()

@app.get("/api/connectprof/products")
async def connectprof_products():
    return await connectprof_api.products()

@app.get("/api/connectprof/exports")
async def connectprof_exports():
    return await connectprof_api.exports()

@app.get("/api/connectprof/orders")
async def connectprof_orders():
    return await connectprof_api.orders()

@app.get("/api/operations/overview")
async def operations_overview():
    products=db.list_products()
    checks=db.list_checks()
    all_markets=["Trendyol","Hepsiburada","N11","Idefix","Pazarama"]
    raw_selected=db.runtime_all().get("price_protection_selected_markets")
    if raw_selected is None:selected_markets=set(all_markets)
    elif not str(raw_selected).strip():selected_markets=set()
    else:selected_markets={x.strip() for x in str(raw_selected).split(",") if x.strip()}
    checks=[x for x in checks if x.get("marketplace") in selected_markets]
    products_by_code={p["product_code"]:p for p in products}
    for x in checks:
        p=products_by_code.get(x.get("product_code"))
        if p:
            x["tsoft_barcode"]=p.get("barcode")
    runtime=db.runtime_all()
    risk_status={"LOSS","CRITICAL","WARNING"}

    matrix={}
    for p in products:
        matrix[p["product_code"]]={
            "product_code":p["product_code"],"barcode":p.get("barcode"),"name":p.get("name"),
            "tsoft_price":p.get("selling_price"),"tsoft_stock":p.get("stock"),"markets":{}
        }

    actions=[]
    for x in checks:
        code=x.get("product_code")
        if code in matrix:
            matrix[code]["markets"][x.get("marketplace")]={
                "status":x.get("status"),"price":x.get("current_price"),"stock":x.get("current_stock"),
                "sku":x.get("marketplace_sku"),"difference":x.get("difference"),"net_margin":x.get("net_margin")
            }

        st=x.get("status")
        if st in risk_status:
            loss=float(x.get("net_margin") or 0)
            priority="Çok Yüksek" if loss < -5000 else "Yüksek" if loss < -1500 else "Normal"
            actions.append({"priority":priority,"type":"Fiyat Riski","marketplace":x.get("marketplace"),"product_code":code,
                            "barcode":matrix.get(code,{}).get("barcode"),"name":x.get("name"),"status":st,
                            "price":x.get("current_price"),"expected_price":x.get("expected_price"),
                            "difference":x.get("difference"),"net_margin":x.get("net_margin"),
                            "suggestion":"Pazaryeri fiyatını kontrol et"})
        elif st=="STOK YOK":
            actions.append({"priority":"Normal","type":"Stok","marketplace":x.get("marketplace"),"product_code":code,
                            "barcode":matrix.get(code,{}).get("barcode"),"name":x.get("name"),"status":st,
                            "price":x.get("current_price"),"net_margin":None,
                            "suggestion":"T-Soft ve pazaryeri stoklarını karşılaştır"})
        elif st=="SATIŞA KAPALI":
            actions.append({"priority":"Normal","type":"Yayın","marketplace":x.get("marketplace"),"product_code":code,
                            "barcode":matrix.get(code,{}).get("barcode"),"name":x.get("name"),"status":st,
                            "price":x.get("current_price"),"net_margin":None,
                            "suggestion":"Ürünün neden kapalı olduğunu kontrol et"})

    order={"Çok Yüksek":0,"Yüksek":1,"Normal":2}
    actions.sort(key=lambda x:order.get(x["priority"],9))
    stats={
        "products":sum(1 for p in products if db.exclusion_mode(p,"*")!="EXCLUDE"),
        "all_products":len(products),
        "excluded":sum(1 for p in products if db.exclusion_mode(p,"*")=="EXCLUDE"),
        "normal":sum(1 for x in checks if x.get("status")=="OK"),
        "risks":sum(1 for x in checks if x.get("status") in risk_status),
        "stock_zero":sum(1 for x in checks if x.get("status")=="STOK YOK"),
        "closed":sum(1 for x in checks if x.get("status")=="SATIŞA KAPALI"),
        "unresolved":sum(1 for x in checks if x.get("status")=="UNRESOLVED"),
        "potential_loss":round(sum(abs(float(x.get("net_margin") or 0)) for x in checks
                                   if x.get("status")=="LOSS" and float(x.get("net_margin") or 0)<0),2)
    }
    return {"stats":stats,"actions":actions[:100],"products":list(matrix.values()),"runtime":runtime}



@app.get("/api/price-protection/markets")
def price_protection_markets_get():
    all_markets=["Trendyol","Hepsiburada","N11","Idefix","Pazarama"]
    runtime=db.runtime_all()
    raw=runtime.get("price_protection_selected_markets")
    if raw is None:
        selected=all_markets[:]
    elif str(raw).strip()=="":
        selected=[]
    else:
        selected=[x for x in all_markets if x in {v.strip() for v in str(raw).split(",") if v.strip()}]
    return {"ok":True,"markets":all_markets,"selected":selected}

@app.post("/api/price-protection/markets")
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

@app.get("/api/settings/alert-tolerance")
def alert_tolerance_get():
    return {"ok":True,"value":float(settings.alert_tolerance_tl)}

@app.post("/api/settings/alert-tolerance")
def alert_tolerance_save(payload:dict):
    try:
        value=float(payload.get("value"))
    except Exception:
        raise HTTPException(400,"Geçerli bir TL tutarı girin.")
    if value < 0 or value > 100000:
        raise HTTPException(400,"Alarm toleransı 0 ile 100.000 TL arasında olmalı.")
    value=round(value,2)
    settings.alert_tolerance_tl=value
    db.runtime_set("alert_tolerance_tl",str(value))
    db.log("INFO",f"Alarm toleransı panelden {value:.2f} TL olarak değiştirildi.","Sistem")
    return {"ok":True,"value":value}

@app.get("/api/update/check")
async def update_check():
    return await updater.check()

@app.post("/api/update/install")
async def update_install():
    result=await updater.prepare_update()
    if not result.get("ok"):
        raise HTTPException(500,result.get("message","Güncelleme hazırlanamadı."))
    if not result.get("available"):
        return result
    # Delayed process will replace files after uvicorn exits.
    import asyncio, os
    async def _stop_later():
        await asyncio.sleep(1.2)
        os._exit(0)
    asyncio.create_task(_stop_later())
    return result

@app.get("/api/dashboard")
def dashboard():
    products=db.list_products(); checks=db.list_checks()
    stats={"products":len(products),"ok":0,"warning":0,"critical":0,"loss":0,"ignored":0,"review":0,"unresolved":0,"stock_zero":0,"closed":0,"price_checked":0}
    by_market={}
    for x in checks:
        status=x.get("status") or ""
        k=status.lower()
        if k in stats:
            stats[k]+=1
        if status=="STOK YOK":
            stats["stock_zero"]+=1
        elif status=="SATIŞA KAPALI":
            stats["closed"]+=1
        elif status in {"OK","LOSS","CRITICAL","WARNING","REVIEW","IGNORED"}:
            stats["price_checked"]+=1

        m=x["marketplace"]
        if m not in by_market:
            by_market[m]={"total":0,"ok":0,"warning":0,"critical":0,"loss":0,"unresolved":0,"stock_zero":0,"closed":0}
        by_market[m]["total"]+=1
        if k in by_market[m]:
            by_market[m][k]+=1
        if status=="STOK YOK":
            by_market[m]["stock_zero"]+=1
        elif status=="SATIŞA KAPALI":
            by_market[m]["closed"]+=1
    return {"stats":stats,"by_market":by_market,"products":products,"checks":checks,
            "events":db.events(100),"runtime":db.runtime_all(),"groups":GROUPS,"commissions":COMMISSION_RATES,
            "mappings":db.manual_mappings()}


@app.get("/api/debug/{marketplace}")
async def debug_marketplace(marketplace:str):
    try:
        key=marketplace.lower()
        if key=="idefix":
            rows=await idefix_debug_sample(5)
        elif key=="pazarama":
            rows=await pazarama_debug_sample(5)
        else:
            raise HTTPException(400,"API teşhisi şu an yalnız Idefix ve Pazarama için açık.")

        # Secret/token içerme ihtimali olan alanları maskele.
        sensitive={"token","accessToken","access_token","secret","password","authorization","apiKey","api_key"}
        def clean(v):
            if isinstance(v,dict):
                out={}
                for k,val in v.items():
                    if str(k) in sensitive or any(s in str(k).lower() for s in ["token","secret","password","authorization"]):
                        out[k]="***"
                    else:
                        out[k]=clean(val)
                return out
            if isinstance(v,list):
                return [clean(x) for x in v[:20]]
            return v
        cleaned=[clean(x) for x in rows]

        # Ham debug servisi boş dönerse, ana kontrolün daha önce başarıyla
        # kaydettiği marketplace_catalog kayıtlarını göster.
        source="raw_api"
        if not cleaned:
            cached=db.catalog_search("Idefix" if key=="idefix" else "Pazarama","",5)
            cleaned=[clean(x) for x in cached]
            source="cached_catalog"

        return {"marketplace":marketplace,"source":source,"items":cleaned}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500,str(e))


@app.post("/api/mappings/save")
async def save_mapping_explicit(payload:dict):
    marketplace=str(payload.get("marketplace") or "").strip()
    product_code=str(payload.get("product_code") or "").strip()
    match_key=str(payload.get("match_key") or "").strip()
    match_value=str(payload.get("match_value") or "").strip()
    marketplace_title=str(payload.get("marketplace_title") or "").strip()

    if not marketplace or not product_code or not match_key or not match_value:
        raise HTTPException(400,"Pazaryeri, T-Soft ürün kodu, eşleşme alanı ve değer zorunludur.")
    if match_key not in {"barcode","stock_code","product_main_id"}:
        raise HTTPException(400,"Geçersiz eşleşme alanı.")

    db.save_manual_mapping(marketplace,product_code,match_key,match_value,marketplace_title)
    db.log("INFO",f"Manuel eşleşme kaydedildi: {match_key}={match_value}",marketplace,product_code)
    return {"ok":True}

@app.get("/api/mappings/unresolved")
def unresolved(marketplace:str=Query(...)):
    return {"items":db.unresolved_for_market(marketplace)}


@app.get("/api/mappings/suggestions")
def suggestions(
    marketplace:str=Query(...),
    product_code:str=Query(...),
    limit:int=Query(5,ge=1,le=10)
):
    return {"items":db.smart_candidates(marketplace,product_code,limit)}

@app.get("/api/mappings/candidates")
def candidates(marketplace:str=Query(...),q:str=Query(""),limit:int=Query(80,ge=1,le=300)):
    return {"items":db.catalog_search(marketplace,q,limit)}

@app.post("/api/mappings")
def save_mapping(payload:MappingPayload):
    if payload.match_key not in {"barcode","sku","pmid","title"}: raise HTTPException(400,"Geçersiz eşleştirme alanı")
    db.save_manual_mapping(payload.marketplace,payload.product_code,payload.match_key,payload.match_value,payload.marketplace_title)
    db.log("INFO",f"Manuel eşleştirme kaydedildi: {payload.match_key}={payload.match_value}",payload.marketplace,payload.product_code)
    return {"ok":True}

@app.delete("/api/mappings/{marketplace}/{product_code}")
def delete_mapping(marketplace:str,product_code:str):
    db.delete_manual_mapping(marketplace,product_code); return {"ok":True}

@app.post("/api/sync/tsoft")
async def sync():
    try: return {"ok":True,"count":await sync_tsoft()}
    except Exception as e: raise HTTPException(500,str(e))


@app.post("/api/check/product/{product_code}")
async def check_single_product(product_code:str):
    try:
        return await run_single_product(product_code)
    except ValueError as e:
        raise HTTPException(400,str(e))
    except Exception as e:
        raise HTTPException(500,str(e))

@app.post("/api/check/{marketplace}")
async def check_one(marketplace:str):
    aliases={"idefix":"Idefix","trendyol":"Trendyol","hepsiburada":"Hepsiburada","n11":"N11","pazarama":"Pazarama"}
    name=aliases.get(marketplace.lower(),marketplace)
    try:
        return {"ok":True,"marketplace":name,"result":await run_marketplace_only(name)}
    except Exception as e:
        raise HTTPException(500,str(e))

@app.post("/api/check")
async def check():
    try: return {"ok":True,"result":await run_cycle()}
    except Exception as e: raise HTTPException(500,str(e))

@app.post("/api/products/{code}/group/{group}")
def group(code:str,group:str):
    if group not in GROUPS: raise HTTPException(400,"Geçersiz grup")
    db.set_group(code,group); return {"ok":True}
