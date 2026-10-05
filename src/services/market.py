import ipaddress,socket,ssl,http.client,re,hashlib
from urllib.parse import urlparse,urljoin
from datetime import timedelta
from sqlalchemy import select
from src.core.auth import require,tenant,audit
from src.core.db import session
from src.core.models import Research,now
from src.core.config import flag

def safe_url(url):
    p=urlparse(url)
    if p.scheme not in {'http','https'} or not p.hostname or p.username or p.password or p.port not in {None,80,443}:raise ValueError('Only public HTTP(S) URLs are allowed.')
    infos=socket.getaddrinfo(p.hostname,p.port or (443 if p.scheme=='https' else 80),type=socket.SOCK_STREAM)
    addresses={x[4][0] for x in infos}
    if not addresses or any(not ipaddress.ip_address(ip).is_global for ip in addresses):raise ValueError('Non-public network destination blocked.')
    return p,sorted(addresses)[0]

def fetch_public_text(url):
    # Pin the connection to the validated address, retaining the original TLS hostname.
    for _ in range(3):
        p,ip=safe_url(url);port=p.port or (443 if p.scheme=='https' else 80)
        sock=socket.create_connection((ip,port),timeout=8)
        if p.scheme=='https':sock=ssl.create_default_context().wrap_socket(sock,server_hostname=p.hostname)
        conn=http.client.HTTPConnection(p.hostname,port,timeout=8);conn.sock=sock
        path=(p.path or '/')+('?' + p.query if p.query else '')
        try:
            conn.request('GET',path,headers={'Host':p.netloc,'User-Agent':'SmartStockAgent/1.0 evidence reader','Accept':'text/html,text/plain'})
            response=conn.getresponse()
            if response.status in {301,302,303,307,308}:
                url=urljoin(url,response.getheader('Location',''));continue
            if response.status!=200:raise ValueError(f'Source returned HTTP {response.status}.')
            if not any(t in (response.getheader('Content-Type') or '') for t in ['text/html','text/plain']):raise ValueError('Source is not a text page.')
            data=response.read(250001)
            if len(data)>250000:raise ValueError('Source exceeds page-size limit.')
            from bs4 import BeautifulSoup
            soup=BeautifulSoup(data,'html.parser')
            for x in soup(['script','style','nav','footer','noscript','iframe']):x.decompose()
            return soup.get_text(' ',strip=True)[:12000]
        finally:conn.close()
    raise ValueError('Too many source redirects.')

def research(ctx,query,region='pk-en'):
    require(ctx,'market.read')
    if not flag('ENABLE_WEB_SEARCH') or not tenant(ctx).web_search:raise ValueError('Web research is disabled. The workspace owner must enable it in Settings after the server is configured.')
    query=query.strip()
    if not query or len(query)>180 or '@' in query or re.search(r'\d{7,}',query):raise ValueError('Use public product/category terms only; exclude emails, phone numbers and private identifiers.')
    with session() as s:
        cached=s.scalar(select(Research).where(Research.tenant_id==ctx.tenant_id,Research.query==query,Research.created_at>now()-timedelta(hours=12)).order_by(Research.created_at.desc()))
        if cached:return {'id':cached.id,'results':cached.payload,'cached':True}
    from ddgs import DDGS
    hits=DDGS(timeout=10).text(query,region=region,max_results=5,backend='duckduckgo')
    rows=[]
    for hit in hits:
        url=hit.get('href') or hit.get('url','')
        if not url:continue
        text='';status='Search snippet only'
        try:text=fetch_public_text(url);status='Source page retrieved; sales claims still require review'
        except Exception:pass
        rows.append({'title':hit.get('title','Source'),'url':url,'snippet':hit.get('body','')[:1000],'source_text':text,'retrieved_at':now().isoformat()+'Z','publication_date':'Not verified','evidence_status':status,'sales_claim':'Not established by search rank or popularity'})
    if not rows:raise ValueError('Search returned no usable evidence. Try a narrower public query later.')
    with session() as s:
        r=Research(tenant_id=ctx.tenant_id,query=query,payload=rows);s.add(r);s.flush();audit(s,ctx,'research.completed',{'research_id':r.id,'source_count':len(rows)})
        return {'id':r.id,'results':rows,'cached':False}

def history(ctx):
    require(ctx,'market.read')
    with session() as s:return s.scalars(select(Research).where(Research.tenant_id==ctx.tenant_id).order_by(Research.created_at.desc())).all()

def set_status(ctx,rid,status):
    require(ctx,'market.read')
    if status not in {'new','saved','dismissed','snoozed'}:raise ValueError('Invalid status.')
    with session() as s:
        r=s.scalar(select(Research).where(Research.id==rid,Research.tenant_id==ctx.tenant_id))
        if not r:raise ValueError('Research unavailable.')
        r.state=status;audit(s,ctx,'research.status',{'id':rid,'status':status})

def assess_opportunity(ctx,name,unit_cost,price,quantity,budget,available,shelf_days,evidence_ids):
    """Review an explicitly named brand/variant/size; never infer sales from rank."""
    import math
    from src.services.inventory import products
    from src.services.reports import build_report
    require(ctx,'market.read')
    if not name.strip() or len(name)>200:raise ValueError('Enter the complete product name, variant and pack size.')
    if any(not math.isfinite(float(v)) for v in [unit_cost,price,quantity,budget,shelf_days]):raise ValueError('Use finite numeric values.')
    if unit_cost<=0 or price<=unit_cost or quantity<1 or int(quantity)!=quantity or budget<0 or shelf_days<1:raise ValueError('Confirm valid cost, selling price, whole units, budget and shelf life.')
    catalog=products(ctx)
    key=lambda x:re.sub(r'\W+',' ',x.casefold()).strip()
    exact=[p for p in catalog if key(p.name)==key(name) or key(p.sku)==key(name)]
    terms=set(key(name).split())
    similar=[p for p in catalog if len(terms & set(key(p.name).split()))/max(1,len(terms | set(key(p.name).split())))>=.25 and p not in exact]
    if exact:
        status='Already carried; currently out of stock' if exact[0].on_hand<=0 else 'Already carried; stock available'
    elif similar:status='Potential catalog match; verify brand, variant, size and unit before classifying as new'
    else:status='No catalog match found; candidate new assortment item (owner verification required)'
    verified=[r for r in history(ctx) if r.id in evidence_ids]
    margin=(price-unit_cost)/price
    eligible=not exact and not similar and available and margin>=.2 and quantity*unit_cost<=budget and bool(verified)
    decision='Small pilot can be proposed after owner verification' if eligible else 'Hold: resolve catalog, evidence, supplier, margin or budget checks before proposing a purchase'
    return build_report('Market pilot: '+name,decision,{'Pilot scenario':[{'product':name,'catalog_status':status,'assumed_units':int(quantity),'unit_cost':unit_cost,'price':price,'margin_pct':round(margin*100,1),'pilot_cost':round(quantity*unit_cost,2),'pilot_budget':budget,'shelf_days':shelf_days,'supplier_confirmed':available}], 'Potential catalog matches':[{'sku':p.sku,'product':p.name,'on_hand':p.on_hand} for p in exact+similar]},[h['url']+' (retrieved '+h['retrieved_at']+')' for r in verified for h in r.payload],['Quantity and price are user-supplied scenarios, not a new-product demand forecast.','Search popularity does not establish sales. Verify local market, source date, brand and pack size.','Track sell-through, realized margin and unsold stock over the pilot; stop or adjust after review. No supplier order is sent.'],'inventory')
