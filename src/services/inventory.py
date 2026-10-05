from datetime import timedelta
from statistics import NormalDist
import math, json, hashlib
import numpy as np
import pandas as pd
from sqlalchemy import select,update
from src.core.db import session
from src.core.models import Product,Movement,Approval,Forecast,now
from src.core.auth import require,audit
from src.services.data import sales,datasets

def products(ctx):
    require(ctx,'inventory.read')
    with session() as s:return s.scalars(select(Product).where(Product.tenant_id==ctx.tenant_id).order_by(Product.name)).all()

def product_dict(p):
    return {c.name:getattr(p,c.name) for c in Product.__table__.columns if c.name!='tenant_id'}

def update_product(ctx,sku,values):
    require(ctx,'inventory.write')
    fields={'on_hand','reserved','backorders','lead_days','lead_std','pack_size','moq','ordering_cost','holding_rate','shelf_days','supplier','unit_cost','expiry_date'}
    if not set(values)<=fields:raise ValueError('Unsupported product update; prices require approval.')
    for k,v in values.items():
        if k not in {'supplier','expiry_date'} and (not np.isfinite(v) or v<0):raise ValueError('Product values must be finite and nonnegative.')
    if values.get('pack_size',1)<1 or values.get('lead_days',1)<1 or values.get('shelf_days',1)<1:raise ValueError('Pack size, lead time and shelf life must be positive.')
    with session() as s:
        p=s.scalar(select(Product).where(Product.tenant_id==ctx.tenant_id,Product.sku==sku).with_for_update())
        if not p:raise ValueError('Product unavailable.')
        if 'on_hand' in values:s.add(Movement(tenant_id=ctx.tenant_id,sku=sku,delta=float(values['on_hand'])-p.on_hand,reason='Confirmed stock count'))
        for k,v in values.items():setattr(p,k,v)
        audit(s,ctx,'product.updated',{'sku':sku,'fields':sorted(values)})

def replenishment(ctx,service_level=.95,budget=100000):
    require(ctx,'inventory.read')
    if not .5<service_level<1 or budget<0:raise ValueError('Invalid service level or budget.')
    frame=sales(ctx)
    if frame.empty:return pd.DataFrame()
    with session() as s:
        orders=s.scalars(select(Approval).where(Approval.tenant_id==ctx.tenant_id,Approval.kind=='purchase',Approval.state=='approved')).all()
        forecast_rows=s.scalars(select(Forecast).where(Forecast.tenant_id==ctx.tenant_id).order_by(Forecast.created_at.desc())).all()
    incoming={}
    for o in orders:incoming[o.payload['sku']]=incoming.get(o.payload['sku'],0)+o.payload['quantity']
    recent={}
    for f in forecast_rows:recent.setdefault(f.sku,f)
    rows=[]
    zero_confirmed={d.id:d.zero_days for d in datasets(ctx)}
    for p in products(ctx):
        item_sales=frame[frame.sku==p.sku]
        series=item_sales.groupby('date').quantity.sum().clip(lower=0).sort_index()
        complete=True
        if len(series):
            calendar=pd.date_range(max(series.index.min(),frame.date.max()-pd.Timedelta(days=55)),frame.date.max())
            series=series.reindex(calendar)
            if series.isna().any():
                complete=all(zero_confirmed.get(did,False) for did in item_sales.dataset_id.unique())
                series=series.fillna(0) if complete else series.dropna()
        mu=float(series.mean()) if len(series) else 0
        sigma=float(series.std()) if len(series)>1 else 0
        source='Recent daily sales' if complete else 'Missing dates unconfirmed; quantity withheld'
        f=recent.get(p.sku)
        if f and f.payload['train_end']>=frame.date.max().date().isoformat():
            vals=[x['prediction'] for x in f.payload['forecasts']]
            mu=float(np.mean(vals[:p.lead_days]));sigma=f.payload.get('residual_std',sigma);source='Forecast '+f.model
        ss=NormalDist().inv_cdf(service_level)*math.sqrt(p.lead_days*sigma**2+mu**2*p.lead_std**2)
        rop=mu*p.lead_days+ss
        position=p.on_hand+incoming.get(p.sku,0)-p.reserved-p.backorders
        holding=p.unit_cost*p.holding_rate
        eoq=math.sqrt(2*(mu*365)*p.ordering_cost/holding) if holding>0 else 0
        desired=max(0,mu*(p.lead_days+7)+ss-position)
        if position>rop:desired=0
        # Forecast order-up-to policy bounds EOQ for perishable products.
        quantity=max(desired,min(eoq,mu*p.shelf_days)) if desired else 0
        quantity=math.ceil(max(quantity,p.moq)/p.pack_size)*p.pack_size if quantity else 0
        max_shelf=math.floor(max(0,mu*p.shelf_days-max(0,position))/p.pack_size)*p.pack_size
        quantity=min(quantity,max_shelf)
        cap=math.floor(budget/max(p.unit_cost,1)/p.pack_size)*p.pack_size
        quantity=min(quantity,cap)
        if quantity<p.moq or p.unit_cost<=0 or not complete:quantity=0
        rows.append({'sku':p.sku,'product':p.name,'on_hand':p.on_hand,'on_order':incoming.get(p.sku,0),'inventory_position':position,'daily_demand':round(mu,2),'safety_stock':math.ceil(ss),'reorder_point':math.ceil(rop),'days_cover':round(max(0,position)/mu,1) if mu else None,'eoq_reference':math.ceil(eoq),'suggested_quantity':int(quantity),'unit_cost':p.unit_cost,'estimated_cost':round(quantity*p.unit_cost,2),'needs_review':bool(position<=rop),'source':source,'supplier':p.supplier})
    # Allocate a shared budget to the most urgent positions, not a full budget per SKU.
    rows.sort(key=lambda r:(not r['needs_review'],r['days_cover'] if r['days_cover'] is not None else 1e9))
    remaining=budget
    bysku={p.sku:p for p in products(ctx)}
    for r in rows:
        p=bysku[r['sku']]
        cap=math.floor(remaining/max(p.unit_cost,1)/p.pack_size)*p.pack_size
        r['suggested_quantity']=max(0,min(r['suggested_quantity'],cap))
        if r['suggested_quantity']<p.moq:r['suggested_quantity']=0
        r['estimated_cost']=round(r['suggested_quantity']*p.unit_cost,2)
        remaining-=r['estimated_cost']
    return pd.DataFrame(rows)

def fingerprint(payload):return hashlib.sha256(json.dumps(payload,sort_keys=True,separators=(',',':')).encode()).hexdigest()

def propose(ctx,kind,title,payload):
    require(ctx,'inventory.write' if kind in {'purchase','price'} else 'reports.write')
    if kind not in {'purchase','price','campaign','staffing'}:raise ValueError('Unsupported approval type.')
    if kind in {'purchase','price'}:
        with session() as s:
            p=s.scalar(select(Product).where(Product.tenant_id==ctx.tenant_id,Product.sku==payload.get('sku')))
            if not p:raise ValueError('Product unavailable.')
            if kind=='purchase':
                q=float(payload.get('quantity',0))
                if not np.isfinite(q) or q<=0 or q>1e7 or p.unit_cost<=0:raise ValueError('A valid quantity and unit cost are required.')
                if q<p.moq or q%p.pack_size:raise ValueError('Quantity must satisfy the minimum and pack size.')
                payload={'sku':p.sku,'quantity':q,'unit_cost':p.unit_cost,'cost':round(q*p.unit_cost,2),'supplier':p.supplier}
            else:
                price=float(payload.get('price',0));floor=float(payload.get('margin_floor',.2))
                if not .05<=floor<=.8 or not np.isfinite(price) or price<=0 or p.unit_cost<=0 or (price-p.unit_cost)/price<floor:raise ValueError('The proposed price breaches the margin floor or has missing cost.')
                payload={'sku':p.sku,'price':price,'old_price':p.price,'unit_cost':p.unit_cost,'margin_floor':floor}
    key=fingerprint(payload)
    with session() as s:
        dupe=s.scalar(select(Approval).where(Approval.tenant_id==ctx.tenant_id,Approval.fingerprint==key,Approval.state.in_(['pending','approved'])))
        if dupe:raise ValueError('An identical proposal is already pending or approved.')
        a=Approval(tenant_id=ctx.tenant_id,kind=kind,title=title[:200],payload=payload,fingerprint=key,created_by=ctx.user_id,expires_at=now()+timedelta(days=2))
        s.add(a);s.flush();audit(s,ctx,'approval.proposed',{'id':a.id,'kind':kind})
        return a.id

def approvals(ctx):
    require(ctx,'approvals.read')
    with session() as s:return s.scalars(select(Approval).where(Approval.tenant_id==ctx.tenant_id).order_by(Approval.created_at.desc())).all()

def decide(ctx,aid,approve,note=''):
    require(ctx,'approvals.decide')
    with session() as s:
        a=s.scalar(select(Approval).where(Approval.id==aid,Approval.tenant_id==ctx.tenant_id).with_for_update())
        if not a or a.state!='pending':raise ValueError('This proposal is not awaiting a decision.')
        if a.expires_at<now():raise ValueError('Proposal expired. Create a current proposal.')
        if a.fingerprint!=fingerprint(a.payload):raise ValueError('Proposal changed. A new review is required.')
        if approve and a.kind in {'purchase','price'}:
            p=s.scalar(select(Product).where(Product.tenant_id==ctx.tenant_id,Product.sku==a.payload['sku']))
            if not p or p.unit_cost!=a.payload['unit_cost'] or (a.kind=='price' and p.price!=a.payload['old_price']):raise ValueError('Product inputs changed. Submit a new proposal.')
        state='approved' if approve else 'rejected'
        changed=s.execute(update(Approval).where(Approval.id==aid,Approval.tenant_id==ctx.tenant_id,Approval.state=='pending').values(state=state,decided_by=ctx.user_id,decision_note=note[:500]))
        if not changed.rowcount:raise ValueError('Another reviewer already decided this proposal.')
        audit(s,ctx,'approval.decided',{'id':aid,'state':state})

def execute(ctx,aid):
    require(ctx,'inventory.write')
    with session() as s:
        a=s.scalar(select(Approval).where(Approval.id==aid,Approval.tenant_id==ctx.tenant_id).with_for_update())
        if not a or a.state!='approved':raise ValueError('An approved action is required.')
        if a.kind=='price' and a.expires_at<now():raise ValueError('Price approval expired. Submit a current proposal.')
        # Claim in the same transaction as the stock/price update. Works on SQLite too.
        changed=s.execute(update(Approval).where(Approval.id==aid,Approval.tenant_id==ctx.tenant_id,Approval.state=='approved').values(state='executing'))
        if not changed.rowcount:raise ValueError('This action was already claimed.')
        if fingerprint(a.payload)!=a.fingerprint:raise ValueError('Action changed.')
        p=s.scalar(select(Product).where(Product.tenant_id==ctx.tenant_id,Product.sku==a.payload.get('sku')).with_for_update())
        if not p or p.unit_cost!=a.payload.get('unit_cost'):raise ValueError('Product inputs changed.')
        if a.kind=='purchase':
            p.on_hand+=a.payload['quantity']
            s.add(Movement(tenant_id=ctx.tenant_id,sku=p.sku,delta=a.payload['quantity'],reason='Confirmed receipt '+a.id))
        elif a.kind=='price':
            if p.price!=a.payload['old_price']:raise ValueError('Price changed since approval.')
            p.price=a.payload['price']
        else:raise ValueError('This action requires a manual external handoff.')
        a.state='completed';audit(s,ctx,'approval.completed',{'id':aid,'kind':a.kind})
