from datetime import timedelta
import hashlib, secrets
import numpy as np
import pandas as pd
from sqlalchemy import select
from src.core.db import session
from src.core.models import User,Tenant,Membership,Product,Expense,Employee,KnowledgeDoc,now
from src.core.auth import issue,Context
from src.core.config import flag
from src.services.data import normalize,suggest_mapping,import_sales

CATALOG=[
 ('RICE-5','Basmati rice 5kg','Pantry',1850,1430,11,24),
 ('MILK-1','Whole milk 1L','Dairy',290,231,18,36),
 ('EGGS-12','Eggs dozen','Dairy',380,295,12,24),
 ('BREAD-1','Sandwich bread','Bakery',220,164,16,18),
 ('TEA-190','Black tea 190g','Beverages',540,426,9,74),
 ('SUGAR-1','Sugar 1kg','Pantry',175,138,14,22),
 ('OIL-1','Cooking oil 1L','Pantry',565,469,10,32),
 ('SOAP-100','Bath soap 100g','Personal care',140,93,8,120),
 ('SHAMP-180','Shampoo 180ml','Personal care',420,310,6,88),
 ('CHIPS-50','Potato chips 50g','Snacks',100,71,20,170),
 ('BISCUIT-1','Tea biscuits','Snacks',80,54,17,18),
 ('DETERG-1','Detergent 1kg','Household',490,369,7,63),
]

def sample_sales(days=180):
    rng=np.random.default_rng(42)
    end=pd.Timestamp.now().normalize()-pd.Timedelta(days=1)
    rows=[]
    for di,day in enumerate(pd.date_range(end-pd.Timedelta(days=days-1),end)):
        seen=set()
        for b in range(12):
            customer=int(rng.integers(0,180 if di<days-30 else 125))
            choices=list(rng.choice(len(CATALOG),size=3,replace=False))
            if b%3==0:choices=[1,2,3]  # repeatable breakfast basket signal
            for ix in choices:
                sku,name,cat,price,cost,base,stock=CATALOG[ix]
                q=int(rng.integers(1,5))+(1 if day.dayofweek>=5 else 0)
                if ix==9:q+=int(di>days-45)
                rows.append({'date':day.date().isoformat(),'sku':sku,'quantity':q,'product':name,'price':price,'unit_cost':cost,'category':cat,'customer_id':f'C{customer:03}','transaction_id':f'T{di:03}-{b:02}','stockout':False})
                seen.add(ix)
        for ix in set(range(len(CATALOG)))-seen:
            sku,name,cat,price,cost,_,_=CATALOG[ix]
            rows.append({'date':day.date().isoformat(),'sku':sku,'quantity':0,'product':name,'price':price,'unit_cost':cost,'category':cat,'customer_id':'','transaction_id':'','stockout':False})
    return pd.DataFrame(rows)

def create_demo():
    if not flag('ALLOW_DEMO',True):raise ValueError('Demo access is disabled.')
    with session() as s:
        t=Tenant(name='Evergreen General Store',demo=True)
        u=User(name='Demo owner',email=f'{secrets.token_hex(12)}@demo.invalid')
        s.add_all([t,u]);s.flush()
        s.add(Membership(tenant_id=t.id,user_id=u.id,role='owner'))
        token=issue(s,u.id,t.id)
        ctx=Context(u.id,t.id,'owner',u.name)
    raw=sample_sales().to_csv(index=False).encode()
    frame=pd.read_csv(__import__('io').BytesIO(raw))
    clean,_,quality=normalize(frame,suggest_mapping(frame))
    import_sales(ctx,'demo_sales.csv',raw,clean,quality,True)
    with session() as s:
        for ix,item in enumerate(CATALOG):
            sku,name,cat,price,cost,_,stock=item
            p=s.scalar(select(Product).where(Product.tenant_id==ctx.tenant_id,Product.sku==sku))
            p.on_hand=stock;p.lead_days=3 if cat in {'Dairy','Bakery'} else 5
            p.shelf_days=7 if cat in {'Dairy','Bakery'} else 180
            p.supplier='Fresh Fields Supply' if cat in {'Dairy','Bakery'} else 'Metro Wholesale'
            p.pack_size=6;p.moq=6;p.lead_std=1
            if cat in {'Dairy','Bakery'}:p.expiry_date=(now()+timedelta(days=3)).date().isoformat()
        s.add_all([Expense(tenant_id=ctx.tenant_id,date=now()-timedelta(days=7),category='Rent',amount=45000,note='Synthetic monthly rent'),Expense(tenant_id=ctx.tenant_id,date=now()-timedelta(days=5),category='Utilities',amount=12500,note='Synthetic utilities')])
        for name,role in [('Alex','Store associate'),('Sam','Inventory assistant'),('Taylor','Cashier')]:s.add(Employee(tenant_id=ctx.tenant_id,name=name,position=role,weekly_hours=40))
        content='Store replenishment policy\nReview milk, eggs and bread daily. Require owner approval before creating a supplier commitment. Review pantry items every Monday. Keep discounts above the approved margin floor. These are synthetic demo policies.'
        s.add(KnowledgeDoc(tenant_id=ctx.tenant_id,title='Demo store policy',scope='general',content_hash=hashlib.sha256(content.encode()).hexdigest(),payload=[{'text':content,'location':'Section 1'}]))
    return token

