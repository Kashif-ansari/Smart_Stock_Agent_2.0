from io import BytesIO
from pathlib import Path
import hashlib, json, os, zipfile
import numpy as np
import pandas as pd
from sqlalchemy import select, delete
from src.core.db import session
from src.core.auth import require, audit
from src.core.models import Dataset, Sale, Product, Forecast, Schedule, uid
from src.core.config import tenant_dir

ALIASES = {
 'date':['date','sales_date','order_date','timestamp','invoice_date'],
 'sku':['sku','product_id','item_id','product_code','item_code'],
 'quantity':['quantity','qty','units','quantity_sold','sales_quantity'],
 'product':['product','product_name','item','item_name'],
 'price':['price','unit_price','selling_price'],
 'unit_cost':['unit_cost','cost','cost_price'],
 'category':['category','department'],
 'customer_id':['customer_id','customer','customer_code'],
 'transaction_id':['transaction_id','order_id','invoice_id','invoice_no','basket_id'],
 'stockout':['stockout','out_of_stock'],
}

def read_file(name,raw,sheet=0):
    if len(raw)>int(os.getenv('MAX_UPLOAD_MB','10'))*1024**2:raise ValueError('File exceeds the configured upload limit.')
    ext=Path(name).suffix.lower()
    if ext in {'.xlsx','.xlsm'}:
        if ext=='.xlsm':raise ValueError('Macro-enabled workbooks are not accepted. Save as XLSX.')
        try:
            with zipfile.ZipFile(BytesIO(raw)) as z:
                if len(z.infolist())>5000 or sum(i.file_size for i in z.infolist())>100*1024**2:
                    raise ValueError('Workbook expands beyond safe limits.')
                if any('vbaproject' in i.filename.lower() for i in z.infolist()):raise ValueError('Macros are not accepted.')
        except zipfile.BadZipFile as exc:raise ValueError('Invalid XLSX file.') from exc
    if ext in {'.xlsx','.xls'}:
        book=pd.ExcelFile(BytesIO(raw),engine='openpyxl' if ext=='.xlsx' else 'xlrd')
        frame=pd.read_excel(book,sheet_name=sheet,dtype=object)
        sheets=book.sheet_names
    elif ext in {'.csv','.tsv'}:
        try:frame=pd.read_csv(BytesIO(raw),sep='\t' if ext=='.tsv' else ',',dtype=object,encoding='utf-8-sig')
        except UnicodeDecodeError:frame=pd.read_csv(BytesIO(raw),sep='\t' if ext=='.tsv' else ',',dtype=object,encoding='cp1252')
        sheets=[]
    else:raise ValueError('Supported sales formats are CSV, TSV, XLSX and XLS.')
    if len(frame)>100000 or len(frame.columns)>100:raise ValueError('Limit: 100,000 rows and 100 columns per import.')
    if frame.empty:raise ValueError('The file contains no rows.')
    frame.columns=[str(c).strip() for c in frame.columns]
    if len(set(frame.columns))!=len(frame.columns):raise ValueError('Column names must be unique.')
    return frame,sheets

def suggest_mapping(frame):
    lower={str(c).strip().lower().replace(' ','_'):c for c in frame.columns}
    return {key:next((lower[a] for a in aliases if a in lower),None) for key,aliases in ALIASES.items()}

def normalize(frame,mapping,dayfirst=False):
    for key in ['date','sku','quantity']:
        if not mapping.get(key):raise ValueError('Map date, product identifier and quantity before validating.')
    df=pd.DataFrame(index=frame.index)
    for key in ALIASES:
        col=mapping.get(key)
        df[key]=frame[col] if col else None
    df['date']=pd.to_datetime(df['date'],errors='coerce',dayfirst=dayfirst,format='mixed').dt.normalize()
    for c in ['quantity','price','unit_cost']:
        df[c]=pd.to_numeric(df[c],errors='coerce')
    for c in ['sku','product','category','customer_id','transaction_id']:
        df[c]=df[c].fillna('').astype(str).str.strip()
    df['product']=df['product'].where(df['product']!='',df['sku'])
    df['category']=df['category'].where(df['category']!='','General')
    df['stockout']=df['stockout'].fillna(False).astype(str).str.lower().isin(['1','true','yes'])
    reasons=[]
    for _,r in df.iterrows():
        bad=[]
        if pd.isna(r.date):bad.append('Invalid date')
        if not r.sku or len(r.sku)>120:bad.append('Invalid SKU')
        if not np.isfinite(r.quantity) or abs(r.quantity)>1e7:bad.append('Invalid quantity')
        for c in ['price','unit_cost']:
            if pd.notna(r[c]) and (not np.isfinite(r[c]) or r[c]<0):bad.append('Invalid '+c)
        reasons.append('; '.join(bad))
    df['error']=reasons
    rejected=frame[df.error!=''].copy();rejected['reason']=df.loc[df.error!='','error']
    clean=df[df.error==''].drop(columns='error').copy()
    quality={'input_rows':len(frame),'accepted_rows':len(clean),'rejected_rows':len(rejected),'return_rows':int((clean.quantity<0).sum()),'missing_price_rows':int(clean.price.isna().sum()),'missing_cost_rows':int(clean.unit_cost.isna().sum()),'duplicate_looking_rows':int(clean.duplicated().sum())}
    quality['score']=round(100*len(clean)/max(1,len(frame)),1)
    quality['notes']=['Negative quantities are returns. Repeated-looking rows are retained; identical files cannot be imported twice. Historical imports do not change current stock balances.']
    quality['mapping']=mapping
    quality['date_policy']='day-first' if dayfirst else 'month-first'
    return clean,rejected,quality

def safe_csv(frame):
    from src.services.reports import safe_cell
    out=frame.copy()
    out.columns=[safe_cell(str(c)) for c in out.columns]
    return out.map(safe_cell).to_csv(index=False).encode('utf-8-sig')

def import_sales(ctx,name,raw,clean,quality,zero_days=False):
    require(ctx,'sales.write')
    if clean.empty:raise ValueError('There are no accepted rows.')
    key=hashlib.sha256(raw).hexdigest()
    with session() as s:
        if s.scalar(select(Dataset).where(Dataset.tenant_id==ctx.tenant_id,Dataset.file_hash==key)):
            raise ValueError('This file was already imported. No rows were added.')
        did=uid();p=tenant_dir(ctx.tenant_id,'uploads')/(did+Path(name).suffix.lower())
        p.write_bytes(raw)
        d=Dataset(id=did,tenant_id=ctx.tenant_id,name=Path(name).name[:200],file_hash=key,file_path=str(p),rows=len(clean),quality=quality,zero_days=zero_days)
        s.add(d);s.flush()
        records=[]
        for r in clean.to_dict('records'):
            records.append(dict(tenant_id=ctx.tenant_id,dataset_id=did,date=r['date'].to_pydatetime(),sku=r['sku'],product=r['product'][:200],category=r['category'][:120],quantity=float(r['quantity']),price=None if pd.isna(r['price']) else float(r['price']),unit_cost=None if pd.isna(r['unit_cost']) else float(r['unit_cost']),customer_id=r['customer_id'][:150] or None,transaction_id=r['transaction_id'][:150] or None,stockout=bool(r['stockout'])))
        s.bulk_insert_mappings(Sale,records)
        existing=set(s.scalars(select(Product.sku).where(Product.tenant_id==ctx.tenant_id)).all())
        for sku,g in clean.groupby('sku'):
            if sku not in existing:
                r=g.iloc[-1]
                s.add(Product(tenant_id=ctx.tenant_id,sku=sku,name=r['product'][:200],category=r['category'][:120],price=float(r.price) if pd.notna(r.price) else 0,unit_cost=float(r.unit_cost) if pd.notna(r.unit_cost) else 0))
        audit(s,ctx,'sales.imported',{'dataset_id':did,'rows':len(clean),'quality_score':quality['score']})
    return did

def sales(ctx,dataset_id=None):
    require(ctx,'sales.read')
    with session() as s:
        q=select(Sale).where(Sale.tenant_id==ctx.tenant_id)
        if dataset_id:q=q.where(Sale.dataset_id==dataset_id)
        rows=s.scalars(q).all()
        cols=['id','dataset_id','date','sku','product','category','quantity','price','unit_cost','customer_id','transaction_id','stockout']
        df=pd.DataFrame([{c:getattr(r,c) for c in cols} for r in rows],columns=cols)
    if not df.empty:
        df['date']=pd.to_datetime(df.date)
        for c in ['quantity','price','unit_cost']:df[c]=pd.to_numeric(df[c],errors='coerce')
        df['revenue']=df.quantity*df.price
        df['cost']=df.quantity*df.unit_cost
    return df

def datasets(ctx):
    require(ctx,'sales.read')
    with session() as s:return s.scalars(select(Dataset).where(Dataset.tenant_id==ctx.tenant_id).order_by(Dataset.created_at.desc())).all()

def delete_dataset(ctx,dataset_id):
    require(ctx,'admin')
    with session() as s:
        d=s.scalar(select(Dataset).where(Dataset.id==dataset_id,Dataset.tenant_id==ctx.tenant_id))
        if not d:raise ValueError('Dataset unavailable.')
        s.execute(delete(Sale).where(Sale.tenant_id==ctx.tenant_id,Sale.dataset_id==d.id))
        s.execute(delete(Forecast).where(Forecast.tenant_id==ctx.tenant_id,Forecast.dataset_id==d.id))
        for item in s.scalars(select(Schedule).where(Schedule.tenant_id==ctx.tenant_id)).all():
            if item.payload.get('dataset_id')==dataset_id:s.delete(item)
        from src.services.lifecycle import clear_derived
        clear_derived(s,ctx)
        Path(d.file_path).unlink(missing_ok=True)
        s.delete(d);audit(s,ctx,'dataset.deleted',{'dataset_id':dataset_id})
