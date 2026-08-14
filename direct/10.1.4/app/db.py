import sqlite3, os
from contextlib import contextmanager
from .config import settings

def db_path():
    p=settings.db_path
    if not os.path.isabs(p): p=os.path.join(os.getcwd(),p)
    os.makedirs(os.path.dirname(p),exist_ok=True)
    return p

@contextmanager
def conn():
    c=sqlite3.connect(db_path(),check_same_thread=False)
    c.row_factory=sqlite3.Row
    try:
        yield c
        c.commit()
    finally:
        c.close()

def _has_et(value):
    return "ET" in str(value or "").upper()

def product_has_et(p):
    # T-Soft tarafında stok kodu farklı alanlarda gelebilir; barkod, ürün kodu veya tedarikçi stok kodundan en az birinde ET zorunlu.
    return any(_has_et(p.get(k)) for k in ("barcode","product_code","supplier_product_code"))

def market_row_has_et(r):
    # Pazaryeri kataloglarında kullanıcı kuralı gereği yalnız barkod veya stok kodunda ET bulunan satırlar tutulur.
    return _has_et(r.get("barcode")) or _has_et(r.get("stock_code"))

def purge_non_et_products():
    with conn() as c:
        rows=c.execute("""SELECT product_code FROM products WHERE
            UPPER(COALESCE(barcode,'')) NOT LIKE '%ET%' AND
            UPPER(COALESCE(product_code,'')) NOT LIKE '%ET%' AND
            UPPER(COALESCE(supplier_product_code,'')) NOT LIKE '%ET%'""").fetchall()
        codes=[r["product_code"] for r in rows]
        if codes:
            marks=','.join('?' for _ in codes)
            c.execute(f"DELETE FROM market_prices WHERE product_code IN ({marks})",codes)
            c.execute(f"DELETE FROM manual_mappings WHERE product_code IN ({marks})",codes)
            c.execute(f"DELETE FROM products WHERE product_code IN ({marks})",codes)
        return len(codes)

def init_db():
    with conn() as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS products(
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          product_id TEXT, product_code TEXT UNIQUE, supplier_product_code TEXT,
          barcode TEXT, name TEXT, category TEXT,
          buying_price REAL DEFAULT 0, selling_price REAL DEFAULT 0,
          stock REAL DEFAULT 0, is_active INTEGER DEFAULT 1,
          price_group TEXT DEFAULT 'İncelenecek', group_manual INTEGER DEFAULT 0,
          updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS market_prices(
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          product_code TEXT NOT NULL, marketplace TEXT NOT NULL, barcode TEXT,
          marketplace_sku TEXT, marketplace_product_main_id TEXT, marketplace_title TEXT,
          match_method TEXT, current_price REAL, current_stock REAL,
          expected_price REAL, commission_rate REAL, difference REAL,
          net_after_commission REAL, net_margin REAL, margin_percent REAL,
          status TEXT, error TEXT, checked_at TEXT DEFAULT CURRENT_TIMESTAMP,
          UNIQUE(product_code,marketplace)
        );

        CREATE TABLE IF NOT EXISTS marketplace_catalog(
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          marketplace TEXT NOT NULL,
          barcode TEXT, stock_code TEXT, product_main_id TEXT, title TEXT,
          price REAL, stock REAL, commission REAL,
          updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS idx_market_catalog_market ON marketplace_catalog(marketplace);
        CREATE INDEX IF NOT EXISTS idx_market_catalog_sku ON marketplace_catalog(marketplace, stock_code);
        CREATE INDEX IF NOT EXISTS idx_market_catalog_barcode ON marketplace_catalog(marketplace, barcode);

        CREATE TABLE IF NOT EXISTS manual_mappings(
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          marketplace TEXT NOT NULL,
          product_code TEXT NOT NULL,
          match_key TEXT NOT NULL,
          match_value TEXT NOT NULL,
          marketplace_title TEXT,
          created_at TEXT DEFAULT CURRENT_TIMESTAMP,
          updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
          UNIQUE(marketplace, product_code)
        );

        CREATE TABLE IF NOT EXISTS events(
          id INTEGER PRIMARY KEY AUTOINCREMENT, level TEXT NOT NULL,
          marketplace TEXT, product_code TEXT, message TEXT NOT NULL,
          created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS runtime(key TEXT PRIMARY KEY, value TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS price_exclusions(
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          match_type TEXT NOT NULL, match_value TEXT NOT NULL,
          mode TEXT NOT NULL DEFAULT 'EXCLUDE', marketplace TEXT NOT NULL DEFAULT '*',
          note TEXT DEFAULT '', enabled INTEGER NOT NULL DEFAULT 1,
          created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS idx_price_exclusions_enabled ON price_exclusions(enabled, mode, marketplace);
        """)

        pcols={r["name"] for r in c.execute("PRAGMA table_info(products)").fetchall()}
        for name, ddl in [("group_manual","INTEGER DEFAULT 0"),("buying_price","REAL DEFAULT 0")]:
            if name not in pcols: c.execute(f"ALTER TABLE products ADD COLUMN {name} {ddl}")

        mcols={r["name"] for r in c.execute("PRAGMA table_info(market_prices)").fetchall()}
        additions=[
            ("marketplace_sku","TEXT"),("marketplace_product_main_id","TEXT"),
            ("marketplace_title","TEXT"),("match_method","TEXT"),
            ("net_after_commission","REAL"),("net_margin","REAL"),("margin_percent","REAL")
        ]
        for name,ddl in additions:
            if name not in mcols: c.execute(f"ALTER TABLE market_prices ADD COLUMN {name} {ddl}")

def upsert_product(p, auto_group):
    if not product_has_et(p): return False
    with conn() as c:
        old=c.execute("SELECT price_group,group_manual FROM products WHERE product_code=?",(p["product_code"],)).fetchone()
        group=old["price_group"] if old and old["group_manual"] else auto_group
        manual=old["group_manual"] if old else 0
        c.execute("""
        INSERT INTO products(product_id,product_code,supplier_product_code,barcode,name,category,buying_price,selling_price,stock,is_active,price_group,group_manual,updated_at)
        VALUES(?,?,?,?,?,?,?,?,?,?,?,?,CURRENT_TIMESTAMP)
        ON CONFLICT(product_code) DO UPDATE SET
          product_id=excluded.product_id,supplier_product_code=excluded.supplier_product_code,
          barcode=excluded.barcode,name=excluded.name,category=excluded.category,
          buying_price=excluded.buying_price,selling_price=excluded.selling_price,
          stock=excluded.stock,is_active=excluded.is_active,price_group=excluded.price_group,
          group_manual=excluded.group_manual,updated_at=CURRENT_TIMESTAMP
        """,(p["product_id"],p["product_code"],p["supplier_product_code"],p["barcode"],p["name"],p["category"],
             p["buying_price"],p["selling_price"],p["stock"],1 if p["is_active"] else 0,group,manual))

def list_products(limit=20000):
    with conn() as c:
        return [dict(r) for r in c.execute("""SELECT * FROM products WHERE UPPER(COALESCE(barcode,'')) LIKE '%ET%' OR UPPER(COALESCE(product_code,'')) LIKE '%ET%' OR UPPER(COALESCE(supplier_product_code,'')) LIKE '%ET%' ORDER BY product_code LIMIT ?""",(limit,)).fetchall()]

def set_group(code,group):
    with conn() as c:
        c.execute("UPDATE products SET price_group=?,group_manual=1 WHERE product_code=?",(group,code))

def upsert_market(row):
    with conn() as c:
        c.execute("""
        INSERT INTO market_prices(
          product_code,marketplace,barcode,marketplace_sku,marketplace_product_main_id,
          marketplace_title,match_method,current_price,current_stock,expected_price,
          commission_rate,difference,net_after_commission,net_margin,margin_percent,
          status,error,checked_at
        ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,CURRENT_TIMESTAMP)
        ON CONFLICT(product_code,marketplace) DO UPDATE SET
          barcode=excluded.barcode,marketplace_sku=excluded.marketplace_sku,
          marketplace_product_main_id=excluded.marketplace_product_main_id,
          marketplace_title=excluded.marketplace_title,match_method=excluded.match_method,
          current_price=excluded.current_price,current_stock=excluded.current_stock,
          expected_price=excluded.expected_price,commission_rate=excluded.commission_rate,
          difference=excluded.difference,net_after_commission=excluded.net_after_commission,
          net_margin=excluded.net_margin,margin_percent=excluded.margin_percent,
          status=excluded.status,error=excluded.error,checked_at=CURRENT_TIMESTAMP
        """,(
          row["product_code"],row["marketplace"],row.get("barcode"),row.get("marketplace_sku"),
          row.get("marketplace_product_main_id"),row.get("marketplace_title"),row.get("match_method"),
          row.get("current_price"),row.get("current_stock"),row.get("expected_price"),
          row.get("commission_rate"),row.get("difference"),row.get("net_after_commission"),
          row.get("net_margin"),row.get("margin_percent"),row.get("status"),row.get("error")
        ))

def list_checks():
    with conn() as c:
        return [dict(r) for r in c.execute("""
        SELECT m.*,p.name,p.category,p.buying_price AS tsoft_buying_price,
               p.selling_price AS tsoft_price,p.price_group
        FROM market_prices m JOIN products p ON p.product_code=m.product_code
        ORDER BY CASE m.status
          WHEN 'LOSS' THEN 1 WHEN 'CRITICAL' THEN 2 WHEN 'WARNING' THEN 3
          WHEN 'REVIEW' THEN 4 WHEN 'UNRESOLVED' THEN 5 WHEN 'IGNORED' THEN 6
          WHEN 'STOK YOK' THEN 7 WHEN 'SATIŞA KAPALI' THEN 8
          WHEN 'OK' THEN 9 ELSE 10 END,
          COALESCE(m.net_margin, 999999999) ASC
        """).fetchall()]

def clear_market(marketplace):
    with conn() as c:
        c.execute("DELETE FROM market_prices WHERE marketplace=?",(marketplace,))

def replace_catalog(marketplace, rows):
    rows=[r for r in rows if market_row_has_et(r)]
    with conn() as c:
        c.execute("DELETE FROM marketplace_catalog WHERE marketplace=?",(marketplace,))
        c.executemany("""
        INSERT INTO marketplace_catalog(marketplace,barcode,stock_code,product_main_id,title,price,stock,commission,updated_at)
        VALUES(?,?,?,?,?,?,?,?,CURRENT_TIMESTAMP)
        """,[(marketplace,str(r.get('barcode') or ''),str(r.get('stock_code') or ''),str(r.get('product_main_id') or ''),
               str(r.get('title') or ''),float(r.get('price') or 0),float(r.get('stock') or 0),float(r.get('commission') or 0)) for r in rows])

def catalog_search(marketplace, query='', limit=80):
    q=(query or '').strip()
    with conn() as c:
        if q:
            like=f"%{q}%"
            rows=c.execute("""
              SELECT * FROM marketplace_catalog
              WHERE marketplace=? AND (barcode LIKE ? OR stock_code LIKE ? OR product_main_id LIKE ? OR title LIKE ?)
              ORDER BY CASE WHEN stock_code=? THEN 0 WHEN barcode=? THEN 1 ELSE 2 END, title
              LIMIT ?
            """,(marketplace,like,like,like,like,q,q,limit)).fetchall()
        else:
            rows=c.execute("SELECT * FROM marketplace_catalog WHERE marketplace=? ORDER BY title LIMIT ?",(marketplace,limit)).fetchall()
        return [dict(r) for r in rows]


def _norm_candidate_text(s):
    import re, unicodedata
    s=str(s or "").strip().lower()
    s=unicodedata.normalize("NFKD",s)
    s="".join(ch for ch in s if not unicodedata.combining(ch))
    s=s.replace("ı","i")
    return re.sub(r"[^a-z0-9]+"," ",s).strip()

def _candidate_score(product, row):
    import difflib, re

    pname=_norm_candidate_text(product.get("name"))
    pcode=_norm_candidate_text(product.get("product_code"))
    psupplier=_norm_candidate_text(product.get("supplier_product_code"))
    pbarcode=_norm_candidate_text(product.get("barcode"))

    title=_norm_candidate_text(row.get("title"))
    sku=_norm_candidate_text(row.get("stock_code"))
    barcode=_norm_candidate_text(row.get("barcode"))
    pmid=_norm_candidate_text(row.get("product_main_id"))

    score=0.0
    reasons=[]

    # Exact identifiers dominate the score
    if pbarcode and barcode and pbarcode==barcode:
        score += 100
        reasons.append("Barkod aynı")
    if pcode and sku and pcode==sku:
        score += 95
        reasons.append("SKU aynı")
    if psupplier and sku and psupplier==sku:
        score += 95
        reasons.append("Tedarikçi SKU aynı")

    # Variant-aware base SKU comparison (TP1218-17 -> TP1218)
    def base_code(v):
        raw=re.sub(r"\s+","",v or "")
        raw=re.sub(r"-(std|\d{1,3})$","",raw,flags=re.I)
        return raw

    if pcode and sku and base_code(pcode)==base_code(sku):
        score += 72
        reasons.append("Ana SKU aynı")
    elif psupplier and sku and base_code(psupplier)==base_code(sku):
        score += 72
        reasons.append("Ana SKU aynı")

    # Name similarity
    if pname and title:
        ratio=difflib.SequenceMatcher(None,pname,title).ratio()
        score += ratio*55
        if ratio >= .80:
            reasons.append("Ürün adı çok benzer")
        elif ratio >= .60:
            reasons.append("Ürün adı benzer")

        pwords=set(pname.split())
        twords=set(title.split())
        if pwords and twords:
            overlap=len(pwords&twords)/max(1,len(pwords|twords))
            score += overlap*30

    # Identifier containment can be useful across marketplace formatting
    for pc in [pcode, psupplier]:
        if pc:
            compact_pc=pc.replace(" ","")
            for rv in [sku, barcode, pmid]:
                compact_rv=(rv or "").replace(" ","")
                if compact_rv and (compact_pc in compact_rv or compact_rv in compact_pc):
                    score += 24
                    reasons.append("Kod benzer")
                    break

    return round(score,2), " · ".join(dict.fromkeys(reasons))

def smart_candidates(marketplace, product_code, limit=5):
    with conn() as c:
        product=c.execute("SELECT * FROM products WHERE product_code=?",(product_code,)).fetchone()
        if not product:
            return []
        product=dict(product)

        rows=[dict(r) for r in c.execute(
            "SELECT * FROM marketplace_catalog WHERE marketplace=?",
            (marketplace,)
        ).fetchall()]

    scored=[]
    for row in rows:
        score,reason=_candidate_score(product,row)
        if score>0:
            row["candidate_score"]=score
            row["candidate_reason"]=reason or "Benzer kayıt"
            scored.append(row)

    scored.sort(
        key=lambda r: (
            -float(r.get("candidate_score") or 0),
            0 if float(r.get("price") or 0)>0 else 1,
            str(r.get("title") or "")
        )
    )
    return scored[:limit]


def save_manual_mapping(marketplace, product_code, match_key, match_value, marketplace_title=''):
    with conn() as c:
        c.execute("""
          INSERT INTO manual_mappings(marketplace,product_code,match_key,match_value,marketplace_title,updated_at)
          VALUES(?,?,?,?,?,CURRENT_TIMESTAMP)
          ON CONFLICT(marketplace,product_code) DO UPDATE SET
            match_key=excluded.match_key,match_value=excluded.match_value,
            marketplace_title=excluded.marketplace_title,updated_at=CURRENT_TIMESTAMP
        """,(marketplace,product_code,match_key,match_value,marketplace_title))

def delete_manual_mapping(marketplace, product_code):
    with conn() as c:
        c.execute("DELETE FROM manual_mappings WHERE marketplace=? AND product_code=?",(marketplace,product_code))

def manual_mappings(marketplace=None):
    with conn() as c:
        if marketplace:
            rows=c.execute("SELECT * FROM manual_mappings WHERE marketplace=? ORDER BY product_code",(marketplace,)).fetchall()
        else:
            rows=c.execute("SELECT * FROM manual_mappings ORDER BY marketplace,product_code").fetchall()
        return [dict(r) for r in rows]

def mapping_for(marketplace, product_code):
    with conn() as c:
        r=c.execute("SELECT * FROM manual_mappings WHERE marketplace=? AND product_code=?",(marketplace,product_code)).fetchone()
        return dict(r) if r else None

def unresolved_for_market(marketplace):
    with conn() as c:
        return [dict(r) for r in c.execute("""
          SELECT m.product_code,m.marketplace,m.status,m.error,p.name,p.barcode,p.supplier_product_code,p.category
          FROM market_prices m JOIN products p ON p.product_code=m.product_code
          WHERE m.marketplace=? AND m.status='UNRESOLVED'
          ORDER BY p.name
        """,(marketplace,)).fetchall()]

def log(level,message,marketplace=None,product_code=None):
    with conn() as c:
        c.execute("INSERT INTO events(level,marketplace,product_code,message) VALUES(?,?,?,?)",
                  (level,marketplace,product_code,message))

def events(limit=100):
    with conn() as c:
        return [dict(r) for r in c.execute("SELECT * FROM events ORDER BY id DESC LIMIT ?",(limit,)).fetchall()]


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
    x=str(v or "").strip().lower().replace("ı","i");x=unicodedata.normalize("NFKD",x);x="".join(ch for ch in x if not unicodedata.combining(ch));return re.sub(r"\s+"," ",x)
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

def runtime_set(key,value):
    with conn() as c:
        c.execute("INSERT INTO runtime(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",(key,str(value)))

def runtime_all():
    with conn() as c:
        return {r["key"]:r["value"] for r in c.execute("SELECT * FROM runtime").fetchall()}


def checks():
    """Compatibility alias used by notification and single-product flows."""
    return list_checks()
