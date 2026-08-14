from datetime import datetime
import re, unicodedata
from collections import defaultdict
from . import db
from .config import settings
from .classifier import auto_group
from .commissions import fallback_commission, expected_price
from .connectors.tsoft import fetch_products
from .connectors.trendyol import fetch_all_approved_products
from .connectors.hepsiburada import fetch_all_listings
from .connectors import hepsiburada_web as hb_web
from .connectors.n11 import fetch_all_products as fetch_n11
from .connectors.idefix import fetch_inventory as fetch_idefix
from .connectors.pazarama import fetch_all_products as fetch_pazarama

from .notifier import send_price_risk_notification
def now(): return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def norm(s):
    s=str(s or "").strip().lower()
    s=unicodedata.normalize("NFKD",s)
    s="".join(ch for ch in s if not unicodedata.combining(ch))
    s=s.replace("ı","i")
    return re.sub(r"[^a-z0-9]+","",s)

async def sync_tsoft():
    incoming=await fetch_products()
    items=[p for p in incoming if db.product_has_et(p)]
    purged=db.purge_non_et_products()
    for p in items: db.upsert_product(p,auto_group(p["name"],p["category"]))
    db.runtime_set("last_tsoft_success",now())
    db.runtime_set("tsoft_product_count",len(items))
    db.runtime_set("tsoft_non_et_filtered",max(0,len(incoming)-len(items)))
    db.log("INFO",f"T-Soft senkronu: {len(items)} ET ürün alındı; {len(incoming)-len(items)} ET dışı ürün reddedildi; {purged} eski kayıt temizlendi.")
    return len(items)

def make_indexes(rows):
    idx={k:defaultdict(list) for k in ("barcode","sku","pmid","title")}
    for r in rows:
        for k,field in [("barcode","barcode"),("sku","stock_code"),("pmid","product_main_id"),("title","title")]:
            key=norm(r.get(field))
            if key: idx[k][key].append(r)
    return idx

def unique(index,key):
    arr=index.get(norm(key),[])
    return arr[0] if len(arr)==1 else None

def unique_contains(index,key):
    q=norm(key)
    if not q: return None
    found=[]
    for k,arr in index.items():
        if q in k or k in q: found.extend(arr)
    uniq=[]; seen=set()
    for item in found:
        ident=(item.get('barcode'),item.get('stock_code'),item.get('product_main_id'),item.get('title'))
        if ident not in seen: uniq.append(item); seen.add(ident)
    return uniq[0] if len(uniq)==1 else None

def idefix_base_sku(value):
    """
    Idefix varyant stok kodlarını ana SKU'ya indirger.
    Örnek:
      TP1218-17  -> TP1218
      TP1218-15  -> TP1218
      TP1218-STD -> TP1218

    Yalnız son parça ölçü/STD görünümündeyse kırpar.
    Böylece normal tireli SKU'ları gereksiz yere bozmaz.
    """
    s=str(value or "").strip()
    m=re.match(r"^(.+?)-(STD|\d{1,3})$", s, flags=re.IGNORECASE)
    return m.group(1) if m else s

def match_idefix_base(p, rows):
    base_candidates={norm(p.get("supplier_product_code")), norm(p.get("product_code"))}
    base_candidates.discard("")
    if not base_candidates:
        return None

    matches=[]
    for r in rows:
        raw=r.get("stock_code") or r.get("product_main_id") or ""
        base=norm(idefix_base_sku(raw))
        if base in base_candidates:
            matches.append(r)

    if not matches:
        return None

    # Güvenlik için fiyatı sıfırdan büyük olan en düşük varyantı kontrol et.
    priced=[r for r in matches if float(r.get("price") or 0) > 0]
    chosen=min(priced, key=lambda r: float(r.get("price") or 0)) if priced else matches[0]
    chosen=dict(chosen)
    chosen["title"]=(chosen.get("title") or "") + (f" · {len(matches)} Idefix varyantı" if len(matches)>1 else "")
    return chosen


def base_market_code(value):
    """
    Pazaryeri varyant kodunu ana ürün koduna indirger.
    Eski TP ve yeni ET kod yapılarında ölçü/varyant sonlarını temizler.
    Örn: TP1218-17 -> TP1218, ET356574-18,5 -> ET356574
    """
    s=str(value or "").strip()
    return re.sub(r"-(STD|\d{1,3}(?:[.,]\d{1,2})?)$", "", s, flags=re.IGNORECASE)

def exact_title_match(p, idx):
    name=norm(p.get("name"))
    if not name:
        return None
    arr=idx["title"].get(name, [])
    return arr[0] if len(arr)==1 else None

def choose_closest_expected_variant(p, rows, marketplace):
    """Belirsiz varyantlarda güvenli seçim.
    1) Pasif/stoksuz kayıtları dışla.
    2) T-Soft ürün/barkod kod ailesiyle eşleşen kayıtları önceliklendir.
    3) Hâlâ birden fazlaysa beklenen pazaryeri fiyatına en yakın aktif varyantı seç.
    """
    if not rows:
        return None

    sellable=[]
    for r in rows:
        try:
            price=float(r.get("price") or 0)
            stock=float(r.get("stock") or 0)
        except Exception:
            continue
        if price <= 0:
            continue
        # Pazarama'da stok 0 kayıt kesinlikle seçilmesin.
        if marketplace=="Pazarama" and stock <= 0:
            continue
        if r.get("active") is False:
            continue
        sellable.append(r)

    candidates=sellable
    if not candidates:
        return None

    # Önce T-Soft ET/TP kod ailesine uyan varyantları tut.
    p_bases={
        norm(base_market_code(p.get("barcode"))),
        norm(base_market_code(p.get("product_code"))),
        norm(base_market_code(p.get("supplier_product_code")))
    }
    p_bases.discard("")
    family=[]
    if p_bases:
        for r in candidates:
            r_values=[r.get("stock_code"),r.get("product_main_id"),r.get("barcode")]
            if any(norm(base_market_code(v)) in p_bases for v in r_values if v):
                family.append(r)
    if family:
        candidates=family

    if len(candidates)==1:
        return candidates[0]

    rate=fallback_commission(marketplace,p.get("price_group"))
    selling=float(p.get("selling_price") or 0)
    if rate is None or selling<=0:
        return None

    target=expected_price(selling,rate)
    return min(candidates,key=lambda r:abs(float(r.get("price") or 0)-target))

def normalize_market_barcode(value, marketplace=""):
    """Hepsiburada'daki 2026ET... gibi barkodları ET... biçimine indirger."""
    s=str(value or "").strip()
    if not s:
        return ""
    if marketplace=="Hepsiburada":
        m=re.search(r"(ET[0-9A-Z._-]+)$", s, flags=re.IGNORECASE)
        if m:
            return m.group(1).upper()
    return s

def _product_identifiers(p):
    """T-Soft tarafındaki tüm kullanılabilir kimlikleri döndürür.
    Yeni ET barkodları, eski TP ürün kodları ve supplier kodları birlikte desteklenir.
    """
    vals=[]
    for value in [p.get("barcode"), p.get("product_code"), p.get("supplier_product_code")]:
        v=str(value or "").strip()
        if v and norm(v) not in {norm(x) for x in vals}:
            vals.append(v)
    return vals

def _prefer_same_title(p, matches):
    """Aynı ET barkodu birden fazla üründe kullanılmışsa doğru ürünü isimle ayır."""
    if not matches:
        return None
    pname=norm(p.get("name"))
    if not pname:
        return None
    exact=[r for r in matches if norm(r.get("title"))==pname]
    return exact[0] if len(exact)==1 else None

def match_code_anywhere(p, rows, marketplace):
    """
    Yeni eşleşme sırası:
    1) ET barkod / ProductCode / SupplierProductCode birebir.
    2) Aynı kimlik birden fazla üründe varsa birebir ürün adı ile ayrıştır.
    3) Varyant ana kodu.
    4) Hâlâ birden fazlaysa yalnız aktif/stoklu adaylar içinde güvenli fiyat seçimi.

    Not: ET barkodlarının bazı ürünlerde tekrar ettiği görüldüğü için barkod tek başına
    benzersiz kabul edilmez.
    """
    codes=_product_identifiers(p)

    # 1) Birebir kimlik eşleşmesi
    for code in codes:
        nc=norm(code)
        matches=[]
        for r in rows:
            raw_values=[r.get("barcode"),r.get("stock_code"),r.get("product_main_id")]
            values=[]
            for v in raw_values:
                if not v:
                    continue
                values.append(v)
                if marketplace=="Hepsiburada":
                    values.append(normalize_market_barcode(v,marketplace))
            target_values={nc,norm(normalize_market_barcode(code,marketplace))}
            if any(norm(v) in target_values for v in values if v):
                matches.append(r)

        if len(matches)==1:
            method="ET / BARKOD" if str(code).upper().startswith("ET") or norm(code)==norm(p.get("barcode")) else "ÜRÜN KODU"
            return matches[0],method

        if len(matches)>1:
            by_title=_prefer_same_title(p,matches)
            if by_title:
                return by_title,"ET / BARKOD + ÜRÜN ADI"

            chosen=choose_closest_expected_variant(p,matches,marketplace)
            if chosen:
                return chosen,"KİMLİK / VARYANT (FİYATA EN YAKIN)"

    # 2) Ana varyant kodu (TP veya ET)
    for code in codes:
        base=norm(base_market_code(code))
        if not base:
            continue
        matches=[]
        for r in rows:
            for v in [r.get("barcode"),r.get("stock_code"),r.get("product_main_id")]:
                if not v:
                    continue
                candidates=[v]
                if marketplace=="Hepsiburada":
                    candidates.append(normalize_market_barcode(v,marketplace))
                if any(norm(base_market_code(cv))==base for cv in candidates if cv):
                    matches.append(r)
                    break

        if matches:
            unique_rows=[]
            seen=set()
            for x in matches:
                ident=(x.get("barcode"),x.get("stock_code"),x.get("product_main_id"),x.get("title"))
                if ident not in seen:
                    seen.add(ident)
                    unique_rows.append(x)

            by_title=_prefer_same_title(p,unique_rows)
            if by_title:
                return by_title,"ANA KOD + ÜRÜN ADI"

            chosen=choose_closest_expected_variant(p,unique_rows,marketplace)
            if chosen:
                return chosen,"ANA ÜRÜN KODU / FİYATA EN YAKIN"

    return None,None

def find_manual_row(mapping, idx):
    if not mapping: return None
    key=mapping.get('match_key')
    value=mapping.get('match_value')
    target={'barcode':'barcode','sku':'sku','stock_code':'sku','pmid':'pmid','product_main_id':'pmid','title':'title'}.get(key)
    if not target: return None
    return unique(idx[target], value)

def match_product(p,idx,marketplace,rows):
    # Manuel eşleşme varsa her zaman onu kullan
    mapping=db.mapping_for(marketplace,p["product_code"])
    if mapping:
        m=find_manual_row(mapping,idx)
        if m:
            return m,"MANUEL"

    # 1) ET barkod / ürün kodu / eski TP kodu doğrudan eşleşme
    # Hepsiburada'da 2026ET... barkodları ET... formatına normalize edilir.
    m,method=match_code_anywhere(p,rows,marketplace)
    if m:
        return m,method

    # 2) ÜRÜN ADI BİREBİR
    # Noktalama, boşluk, Türkçe karakter farkları norm() ile kaldırılır.
    pname=norm(p.get("name"))
    if pname:
        title_matches=[r for r in rows if norm(r.get("title"))==pname]
        if len(title_matches)==1:
            return title_matches[0],"ÜRÜN ADI BİREBİR"
        if len(title_matches)>1:
            chosen=choose_closest_expected_variant(p,title_matches,marketplace)
            if chosen:
                return chosen,"ÜRÜN ADI / VARYANT (FİYATA EN YAKIN)"

    # 3) Barkod
    if p.get("barcode"):
        m=unique(idx["barcode"],p["barcode"])
        if m:
            return m,"BARKOD"

    # 4) Kalan güvenli SKU/Main ID kontrolleri
    for code in [p.get("supplier_product_code"),p.get("product_code")]:
        if code:
            m=unique(idx["sku"],code)
            if m:
                return m,"SKU"

    for code in [p.get("supplier_product_code"),p.get("product_code")]:
        if code:
            m=unique(idx["pmid"],code)
            if m:
                return m,"MAIN ID"

    # 5) Tekil benzer SKU
    for code in [p.get("supplier_product_code"),p.get("product_code")]:
        if code:
            m=unique_contains(idx["sku"],code)
            if m:
                return m,"SKU BENZER"

    return None,None

def availability_status(row):
    if not row:
        return "BİLİNMİYOR"
    if row and row.get("active") is False:
        return "SATIŞA KAPALI"
    try:
        stock=float(row.get("stock") or 0)
    except Exception:
        stock=0
    if stock <= 0:
        return "STOK YOK"
    return "AKTİF"

def evaluate(p,m,method,marketplace):
    """
    Fiyat riski yalnız SATILABİLİR kayıtlar için hesaplanır.
    Stok 0 / satışa kapalı ürünlerde komisyon, net marj ve fiyat alarmı üretilmez.
    """
    avail=availability_status(m)

    if avail=="SATIŞA KAPALI":
        return base_row(
            p,m,method,marketplace,
            "SATIŞA KAPALI",
            "Pazaryeri ürünü satışa kapalı/pasif. Fiyat risk hesabına dahil edilmedi."
        )

    if avail=="STOK YOK":
        return base_row(
            p,m,method,marketplace,
            "STOK YOK",
            "Pazaryeri stoğu 0. Fiyat risk hesabına dahil edilmedi."
        )

    try:
        tolerance=float(db.runtime_all().get("alert_tolerance_tl") or 1300)
    except Exception:
        tolerance=1300.0
    price=float(m.get("price") or 0)
    if price<=0:
        return base_row(p,m,method,marketplace,"IGNORED","Pazaryeri 0 TL fiyat döndürdü; alarm dışı.")

    api_commission=float(m.get("commission") or 0)
    rate=api_commission if api_commission>0 else fallback_commission(marketplace,p["price_group"])
    if rate is None:
        return base_row(p,m,method,marketplace,"REVIEW","Komisyon belirlenemedi.")

    buying=float(p.get("buying_price") or 0)
    net=round(price*(1-rate/100.0),2)
    margin=round(net-buying,2) if buying>0 else None
    margin_pct=round((margin/buying)*100,2) if buying>0 and margin is not None else None
    exp=expected_price(float(p.get("selling_price") or 0),rate)
    diff=round(price-exp,2)

    if buying>0 and net < buying-tolerance:
        status="LOSS"
    elif diff < -tolerance:
        status="CRITICAL"
    elif abs(diff)>tolerance:
        status="WARNING"
    else:
        status="OK"

    row=base_row(p,m,method,marketplace,status,None)
    row.update({
        "expected_price":exp,
        "commission_rate":rate,
        "difference":diff,
        "net_after_commission":net,
        "net_margin":margin,
        "margin_percent":margin_pct
    })
    return row

def base_row(p,m,method,marketplace,status,error):
    return {
        "product_code":p["product_code"],"marketplace":marketplace,"barcode":p.get("barcode"),
        "marketplace_sku":m.get("stock_code") if m else None,
        "marketplace_product_main_id":m.get("product_main_id") if m else None,
        "marketplace_title":m.get("title") if m else None,
        "match_method":method,"current_price":m.get("price") if m else None,
        "current_stock":m.get("stock") if m else None,
        "expected_price":None,"commission_rate":None,"difference":None,
        "net_after_commission":None,"net_margin":None,"margin_percent":None,
        "status":status,"error":error
    }

async def check_marketplace(name,fetcher):
    rows=await fetcher()
    db.replace_catalog(name,rows)
    db.clear_market(name)
    db.runtime_set(f"{name}_product_count",len(rows))
    db.runtime_set(f"{name}_title_count",sum(1 for r in rows if str(r.get("title") or "").strip()))
    db.runtime_set(f"{name}_sku_count",sum(1 for r in rows if str(r.get("stock_code") or "").strip()))
    db.runtime_set(f"{name}_stock_zero_count",sum(1 for r in rows if availability_status(r)=="STOK YOK"))
    db.runtime_set(f"{name}_closed_count",sum(1 for r in rows if availability_status(r)=="SATIŞA KAPALI"))
    idx=make_indexes(rows)
    products=db.list_products()
    matched=0; unresolved=0; loss=0; critical=0; manual=0; stock_zero=0; closed=0
    methods=defaultdict(int)

    for p in products:
        exclusion=db.exclusion_mode(p,name)
        if exclusion=="EXCLUDE": continue
        m,method=match_product(p,idx,name,rows)
        if not m:
            unresolved+=1
            db.upsert_market(base_row(p,None,None,name,"UNRESOLVED","Güvenli eşleşme bulunamadı."))
            continue
        matched+=1; methods[method]+=1
        if method=="MANUEL": manual+=1
        row=evaluate(p,m,method,name)
        if exclusion=="SILENT" and row.get("status") in {"LOSS","CRITICAL","WARNING"}:
            row["status"]="IGNORED";row["error"]="Sessiz izleme kuralı: alarm üretilmedi."
        db.upsert_market(row)
        if row["status"]=="LOSS":
            loss+=1
            db.log("LOSS",f"Net {row['net_after_commission']:.2f} TL < alış {p['buying_price']:.2f} TL.",name,p["product_code"])
        elif row["status"]=="CRITICAL":
            critical+=1
        elif row["status"]=="STOK YOK":
            stock_zero+=1
        elif row["status"]=="SATIŞA KAPALI":
            closed+=1

    db.runtime_set(f"last_{name}_success",now())
    db.runtime_set(f"{name}_matched",matched)
    db.runtime_set(f"{name}_unresolved",unresolved)
    db.runtime_set(f"{name}_manual",manual)
    db.runtime_set(f"{name}_stock_zero_matched",stock_zero)
    db.runtime_set(f"{name}_closed_matched",closed)
    db.log("INFO",f"{name}: {len(rows)} kayıt, {matched} eşleşti, {manual} manuel, {unresolved} çözülemedi, {loss} zarar riski, {stock_zero} stok 0, {closed} satışa kapalı.",name)
    return {"rows":len(rows),"matched":matched,"manual":manual,"unresolved":unresolved,"loss":loss,"critical":critical,"stock_zero":stock_zero,"closed":closed}


def _hb_web_market_row(p, info):
    """Public web result -> internal marketplace row. Never trust an unverified seller price."""
    if not info.get("ok") or not info.get("matched"):
        return None
    return {
        "barcode":info.get("barcode") or info.get("tsoft_barcode") or p.get("barcode"),
        "stock_code":"WEB",
        "product_main_id":info.get("url"),
        "title":info.get("title") or p.get("name"),
        "price":float(info.get("price") or 0),
        "stock":float(info.get("stock") or 0),
        "commission":0,
        "active":True if float(info.get("price") or 0)>0 else None,
        "_trusted_price":bool(info.get("trusted_price")),
        "_seller":info.get("seller"),
        "_url":info.get("url"),
        "_score":info.get("score"),
    }

async def check_hepsiburada_web(limit=None):
    """
    Kontrollü web taraması:
    - tüm Hepsiburada kayıtlarını temizlemez;
    - her çalıştırmada bir sonraki aktif ürün grubunu tarar;
    - yalnız doğrulanmış Topaloğlu satıcı fiyatı risk hesabına girer;
    - doğrulanamayan fiyat REVIEW olarak kaydedilir.
    """
    products=[p for p in db.list_products() if float(p.get("stock") or 0)>0 and db.exclusion_mode(p,"Hepsiburada")!="EXCLUDE"]
    if not products:
        return {"mode":"web","checked":0,"trusted":0,"review":0,"unresolved":0,"next_cursor":0}

    batch=int(limit or getattr(settings,"hepsiburada_web_batch_size",10) or 10)
    batch=max(1,min(batch,25))

    runtime=db.runtime_all()
    try: cursor=int(runtime.get("Hepsiburada_web_cursor") or 0)
    except Exception: cursor=0
    if cursor>=len(products): cursor=0

    selected=products[cursor:cursor+batch]
    if len(selected)<batch and len(products)>len(selected):
        selected += products[:batch-len(selected)]

    trusted=review=unresolved=errors=0
    for p in selected:
        try:
            info=await hb_web.find_product(p)
            m=_hb_web_market_row(p,info)
            if not m:
                unresolved+=1
                db.upsert_market(base_row(
                    p,None,"WEB","Hepsiburada","UNRESOLVED",
                    info.get("error") or "Hepsiburada web sayfasında güvenli eşleşme bulunamadı."
                ))
                continue

            if not m.get("_trusted_price"):
                review+=1
                seller=m.get("_seller") or "doğrulanamadı"
                row=base_row(
                    p,m,"WEB_REVIEW","Hepsiburada","REVIEW",
                    f"Web fiyatı bulundu ancak Topaloğlu satıcısı doğrulanamadı ({seller}). Fiyat alarmına dahil edilmedi."
                )
                db.upsert_market(row)
                continue

            trusted+=1
            row=evaluate(p,m,"WEB_TOPALOGLU","Hepsiburada")
            if db.exclusion_mode(p,"Hepsiburada")=="SILENT" and row.get("status") in {"LOSS","CRITICAL","WARNING"}:row["status"]="IGNORED";row["error"]="Sessiz izleme kuralı: alarm üretilmedi."
            db.upsert_market(row)
        except Exception as e:
            errors+=1
            db.log("ERROR",f"Hepsiburada web ürün okuma hatası: {e}","Hepsiburada",p.get("product_code"))

    next_cursor=(cursor+len(selected))%len(products) if products else 0
    db.runtime_set("Hepsiburada_web_cursor",next_cursor)
    db.runtime_set("last_Hepsiburada_success",now())
    db.runtime_set("Hepsiburada_web_last_checked",len(selected))
    db.runtime_set("Hepsiburada_web_trusted",trusted)
    db.runtime_set("Hepsiburada_web_review",review)
    db.runtime_set("Hepsiburada_web_unresolved",unresolved)
    db.log("INFO",f"Hepsiburada WEB: {len(selected)} ürün tarandı, {trusted} doğrulanmış fiyat, {review} inceleme, {unresolved} eşleşmedi, {errors} hata.","Hepsiburada")
    return {
        "mode":"web","checked":len(selected),"trusted":trusted,"review":review,
        "unresolved":unresolved,"errors":errors,"next_cursor":next_cursor,
        "total_active_products":len(products)
    }

async def check_hepsiburada_web_single(target):
    info=await hb_web.find_product(target)
    m=_hb_web_market_row(target,info)
    if not m:
        row=base_row(
            target,None,"WEB","Hepsiburada","UNRESOLVED",
            info.get("error") or "Hepsiburada web sayfasında güvenli eşleşme bulunamadı."
        )
        db.upsert_market(row)
        return row

    if not m.get("_trusted_price"):
        seller=m.get("_seller") or "doğrulanamadı"
        row=base_row(
            target,m,"WEB_REVIEW","Hepsiburada","REVIEW",
            f"Web fiyatı bulundu ancak Topaloğlu satıcısı doğrulanamadı ({seller}). Alarm dışı."
        )
        db.upsert_market(row)
        return row

    row=evaluate(target,m,"WEB_TOPALOGLU","Hepsiburada")
    db.upsert_market(row)
    return row


MARKETS=[
    ("Trendyol",lambda:fetch_all_approved_products(),lambda:settings.trendyol_enabled),
    ("Hepsiburada",lambda:fetch_all_listings(),lambda:settings.hepsiburada_enabled),
    ("N11",lambda:fetch_n11(),lambda:settings.n11_enabled),
    ("Idefix",lambda:fetch_idefix(),lambda:settings.idefix_enabled),
    ("Pazarama",lambda:fetch_pazarama(),lambda:settings.pazarama_enabled),
]




def price_protection_selected_markets():
    """Pazaryeri fiyat kontrolüne dahil edilen kanallar. Boş kayıt = hiçbiri."""
    all_names=[name for name,_,_ in MARKETS]
    raw=db.runtime_all().get("price_protection_selected_markets")
    if raw is None:
        return set(all_names)
    raw=str(raw).strip()
    if raw=="":
        return set()
    selected={x.strip() for x in raw.split(",") if x.strip()}
    return {x for x in selected if x in all_names}

async def run_single_product(product_code):
    code=str(product_code or "").strip()
    if not code:
        raise ValueError("Ürün kodu boş olamaz.")

    def find_target(items):
        ncode=norm(code)
        matches=[
            p for p in items
            if any(norm(p.get(k))==ncode for k in ("barcode","product_code","supplier_product_code") if p.get(k))
        ]
        if len(matches)==1:
            return matches[0]
        # Aynı ET barkod birden fazla T-Soft ürününde varsa tek ürün kontrolünde
        # yanlış ürün seçmemek için otomatik seçim yapma.
        if len(matches)>1:
            raise ValueError(f"{code} birden fazla T-Soft ürününde kullanılıyor. Ürün kodu ile arama yapın.")
        return None

    products=db.list_products()
    target=find_target(products)
    if not target:
        await sync_tsoft()
        products=db.list_products()
        target=find_target(products)
    if not target:
        raise ValueError(f"T-Soft'ta {code} kimliğiyle ürün bulunamadı.")

    result={"product_code":target["product_code"],"name":target.get("name"),"markets":{},"errors":[]}

    selected_markets=price_protection_selected_markets()
    for name,fetcher,enabled in MARKETS:
        if not enabled() or name not in selected_markets: continue
        exclusion=db.exclusion_mode(target,name)
        if exclusion=="EXCLUDE":
            result["markets"][name]={"status":"IGNORED","marketplace":name,"error":"Ürün fiyat kontrolünden hariç bırakılmış."};db.clear_product_market(target["product_code"],name);continue
        try:
            if name=="Hepsiburada" and (getattr(settings,"hepsiburada_mode","web") or "web").lower()=="web":
                row=await check_hepsiburada_web_single(target)
            else:
                rows=await fetcher()
                db.replace_catalog(name,rows)
                idx=make_indexes(rows)
                market_row,method=match_product(target,idx,name,rows)
                row=base_row(target,None,None,name,"UNRESOLVED","Güvenli eşleşme bulunamadı.") if not market_row else evaluate(target,market_row,method,name)
                if exclusion=="SILENT" and row.get("status") in {"LOSS","CRITICAL","WARNING"}:row["status"]="IGNORED";row["error"]="Sessiz izleme kuralı: alarm üretilmedi."
                db.upsert_market(row)
            result["markets"][name]={
                "status":row.get("status"),
                "marketplace":name,
                "current_price":row.get("current_price"),
                "current_stock":row.get("current_stock"),
                "match_method":row.get("match_method"),
                "marketplace_sku":row.get("marketplace_sku"),
                "marketplace_title":row.get("marketplace_title"),
                "net_margin":row.get("net_margin"),
                "difference":row.get("difference"),
                "error":row.get("error"),
            }
        except Exception as e:
            result["errors"].append(f"{name}: {e}")
            db.log("ERROR",f"{name} tek ürün kontrol hatası: {e}",name,target["product_code"])

    try:
        send_price_risk_notification(db.list_checks())
    except Exception as e:
        db.log("ERROR",f"Tek ürün bildirim kontrolü başarısız: {e}")
    return result

async def run_marketplace_only(name):
    lookup={market:(fetcher,enabled) for market,fetcher,enabled in MARKETS}
    if name not in lookup:
        raise ValueError("Geçersiz pazaryeri")
    fetcher,enabled=lookup[name]
    if not enabled():
        raise RuntimeError(f"{name} bağlantısı .env içinde aktif değil.")
    if name=="Hepsiburada" and (getattr(settings,"hepsiburada_mode","web") or "web").lower()=="web":
        return await check_hepsiburada_web()
    return await check_marketplace(name,fetcher)

async def run_cycle():
    result={"tsoft":None,"markets":{},"errors":[]}
    try: result["tsoft"]=await sync_tsoft()
    except Exception as e:
        result["errors"].append(f"T-Soft: {e}"); db.log("ERROR",f"T-Soft senkron hatası: {e}")
    selected_markets=price_protection_selected_markets()
    for name,fetcher,enabled in MARKETS:
        if not enabled() or name not in selected_markets: continue
        try:
            if name=="Hepsiburada" and (getattr(settings,"hepsiburada_mode","web") or "web").lower()=="web":
                result["markets"][name]=await check_hepsiburada_web()
            else:
                result["markets"][name]=await check_marketplace(name,fetcher)
        except Exception as e:
            result["errors"].append(f"{name}: {e}"); db.log("ERROR",f"{name} kontrol hatası: {e}",name)

    # Her 5 dakikalık otomatik tur sonunda Windows masaüstü bildirimi.
    # Yalnız aktif fiyat riskleri (LOSS / CRITICAL / WARNING) dikkate alınır.
    try:
        send_price_risk_notification(db.list_checks())
    except Exception as e:
        db.log("ERROR",f"Masaüstü bildirim kontrolü başarısız: {e}")
    return result
