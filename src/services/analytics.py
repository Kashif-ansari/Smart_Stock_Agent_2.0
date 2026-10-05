from sqlalchemy import select
from src.core.auth import require,audit
from src.core.db import session
from src.core.models import Forecast,Expense,Employee,Dataset,now
from src.services.data import sales
from src.analytics.forecasting import daily_series,run_forecast

def forecast_product(ctx,dataset_id,sku,horizon=14,method='Auto benchmark'):
    require(ctx,'forecast.run')
    from src.services.lifecycle import purge_revision,ensure_current
    revision=purge_revision(ctx)
    with session() as s:
        ds=s.scalar(select(Dataset).where(Dataset.tenant_id==ctx.tenant_id,Dataset.id==dataset_id))
        if not ds:raise ValueError('Dataset unavailable.')
    df=sales(ctx,dataset_id)
    result=run_forecast(daily_series(df,sku,ds.zero_days),int(horizon),method)
    result['dataset_id']=dataset_id;result['sku']=sku
    if df[df.sku==sku].stockout.any():result['warnings'].append('This product has recorded stockouts; the model forecasts observed sales, not unconstrained demand.')
    ensure_current(ctx,revision)
    with session() as s:
        f=Forecast(tenant_id=ctx.tenant_id,dataset_id=dataset_id,sku=sku,model=result['model'],horizon=horizon,payload=result)
        s.add(f);s.flush();audit(s,ctx,'forecast.completed',{'forecast_id':f.id,'sku':sku});result['forecast_id']=f.id
    return result

def forecasts(ctx):
    require(ctx,'sales.read')
    with session() as s:return s.scalars(select(Forecast).where(Forecast.tenant_id==ctx.tenant_id).order_by(Forecast.created_at.desc())).all()

def finance(ctx):
    require(ctx,'finance.read')
    df=sales(ctx)
    with session() as s:expenses=s.scalars(select(Expense).where(Expense.tenant_id==ctx.tenant_id).order_by(Expense.date.desc())).all()
    if df.empty:return {'sales':0,'known_cost':0,'gross_profit':None,'missing_cost_rows':0,'expenses':expenses,'operating_result':None}
    complete=df.unit_cost.notna().all() and df.price.notna().all()
    revenue=float(df.revenue.sum());cost=float(df.cost.sum())
    return {'sales':revenue,'known_cost':cost,'gross_profit':revenue-cost if complete else None,'missing_cost_rows':int(df.unit_cost.isna().sum()),'expenses':expenses,'operating_result':revenue-cost-sum(e.amount for e in expenses) if complete else None,'period_start':str(df.date.min().date()),'period_end':str(df.date.max().date()),'note':'Accrual-style estimate from uploaded sales and recorded expenses; not a cash ledger or statutory statement.'}

def add_expense(ctx,date,category,amount,note):
    require(ctx,'finance.write')
    if not 0<amount<1e10:raise ValueError('Enter a positive expense amount.')
    with session() as s:s.add(Expense(tenant_id=ctx.tenant_id,date=date,category=category[:100],amount=amount,note=note[:300]));audit(s,ctx,'expense.created',{'amount':amount,'category':category})

def employees(ctx):
    require(ctx,'hr.read')
    with session() as s:return s.scalars(select(Employee).where(Employee.tenant_id==ctx.tenant_id)).all()

def add_employee(ctx,name,position,hours,availability):
    require(ctx,'hr.write')
    if not name.strip() or not 1<=hours<=80:raise ValueError('Name and weekly hours between 1 and 80 are required.')
    with session() as s:s.add(Employee(tenant_id=ctx.tenant_id,name=name[:120],position=position[:120],weekly_hours=hours,availability=availability[:200]));audit(s,ctx,'employee.created',{'position':position[:120]})
