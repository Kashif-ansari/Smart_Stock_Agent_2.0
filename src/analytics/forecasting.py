import math, warnings
import numpy as np
import pandas as pd

METHODS=['Seasonal naive','Moving average','Exponential smoothing','ARIMA','Croston SBA','Prophet','Chronos-2']

def predict(y,horizon,method):
    y=np.asarray(y,dtype=float)
    if len(y)<7:raise ValueError('At least 7 daily observations are required.')
    with warnings.catch_warnings():
        warnings.simplefilter('ignore')
        if method=='Seasonal naive':out=np.resize(y[-7:],horizon)
        elif method=='Moving average':out=np.repeat(y[-min(28,len(y)):].mean(),horizon)
        elif method=='Exponential smoothing':
            from statsmodels.tsa.holtwinters import ExponentialSmoothing
            model=ExponentialSmoothing(y,trend='add' if len(y)>=28 else None,seasonal='add' if len(y)>=28 else None,seasonal_periods=7 if len(y)>=28 else None,initialization_method='estimated')
            out=model.fit(optimized=True).forecast(horizon)
        elif method=='ARIMA':
            if len(y)<35:raise ValueError('ARIMA needs at least 35 daily observations here.')
            from statsmodels.tsa.arima.model import ARIMA
            out=ARIMA(y,order=(1,1,1)).fit().forecast(horizon)
        elif method=='Croston SBA':
            alpha=.1; nz=np.flatnonzero(y>0)
            if not len(nz):return np.zeros(horizon)
            z=y[nz[0]];interval=float(nz[0]+1);last=nz[0]
            for pos in nz[1:]:
                z+=alpha*(y[pos]-z);interval+=alpha*((pos-last)-interval);last=pos
            out=np.repeat((1-alpha/2)*z/interval,horizon)
        elif method=='Prophet':
            try:from prophet import Prophet
            except ImportError as e:raise ValueError('Install requirements-forecast.txt to use Prophet.') from e
            model=Prophet(yearly_seasonality=False,daily_seasonality=False,weekly_seasonality=True)
            train=pd.DataFrame({'ds':pd.date_range('2020-01-01',periods=len(y)),'y':y})
            model.fit(train)
            out=model.predict(model.make_future_dataframe(periods=horizon))['yhat'].tail(horizon).to_numpy()
        elif method=='Chronos-2':
            from src.core.config import flag
            if not flag('ENABLE_MODEL_DOWNLOADS'):raise ValueError('Enable model downloads explicitly before running Chronos-2.')
            try:from chronos import Chronos2Pipeline
            except ImportError as e:raise ValueError('Install requirements-forecast.txt to use Chronos-2.') from e
            pipeline=_chronos()
            df=pd.DataFrame({'item_id':['series']*len(y),'timestamp':pd.date_range('2020-01-01',periods=len(y)),'target':y})
            fc=pipeline.predict_df(df,prediction_length=horizon,quantile_levels=[.1,.5,.9],id_column='item_id',timestamp_column='timestamp',target='target')
            col='0.5' if '0.5' in fc else 'predictions'
            out=fc[col].to_numpy()[-horizon:]
        else:raise ValueError('Unknown forecasting method.')
    return np.maximum(0,np.asarray(out,dtype=float))

from functools import lru_cache
@lru_cache(maxsize=1)
def _chronos():
    from chronos import Chronos2Pipeline
    return Chronos2Pipeline.from_pretrained('amazon/chronos-2',device_map='cpu')

def daily_series(frame,sku,zero_days=False):
    group=frame[frame.sku==sku]
    if group.empty:raise ValueError('No sales for this product.')
    s=group.groupby('date').quantity.sum().sort_index()
    index=pd.date_range(s.index.min(),s.index.max(),freq='D')
    s=s.reindex(index)
    if s.isna().any() and not zero_days:
        raise ValueError('Missing dates are not confirmed zero-sales days. Review the upload setting or provide complete daily data.')
    return s.fillna(0).clip(lower=0)

def score(actual,pred):
    actual=np.asarray(actual);error=np.asarray(pred)-actual
    denom=np.abs(actual).sum()
    return {'mae':round(float(np.abs(error).mean()),3),'wape_pct':round(float(np.abs(error).sum()/denom*100),2) if denom>0 else None,'bias':round(float(error.mean()),3)}

def run_forecast(series,horizon=14,method='Auto benchmark'):
    if horizon not in {7,14,30,90}:raise ValueError('Choose a supported horizon.')
    y=series.to_numpy(float)
    if len(y)<28:raise ValueError('Provide at least 28 daily observations for evaluation. New products need a separately labelled scenario.')
    validation_h=min(14,max(7,len(y)//6))
    holdout_start=len(y)-validation_h
    # Model choice uses earlier folds. The last block is untouched until evaluation.
    train=y[:holdout_start]
    folds=[len(train)-validation_h,len(train)-2*validation_h]
    folds=[f for f in folds if f>=14]
    candidates=['Seasonal naive','Moving average','Exponential smoothing','Croston SBA'] if method=='Auto benchmark' else [method]
    boards=[];failed=[]
    for candidate in candidates:
        actuals=[];preds=[]
        try:
            for cut in folds or [max(7,len(train)-7)]:
                actual=train[cut:cut+validation_h]
                pred=predict(train[:cut],len(actual),candidate)
                actuals.extend(actual);preds.extend(pred)
            m=score(actuals,preds)
            boards.append({'model':candidate,**m})
        except Exception as exc:failed.append({'model':candidate,'reason':str(exc)[:250]})
    if not boards:raise ValueError('No eligible model completed: '+str(failed))
    champion=min(boards,key=lambda r:r['mae'])['model']
    test_prediction=predict(train,validation_h,champion)
    test=score(y[holdout_start:],test_prediction)
    baseline=score(y[holdout_start:],predict(train,validation_h,'Seasonal naive'))
    residual=y[holdout_start:]-test_prediction
    sigma=float(np.std(residual,ddof=1)) if len(residual)>1 else 0.0
    forecast=predict(y,horizon,champion)
    # An empirical planning band, not a claim of calibrated probability coverage.
    width=1.645*sigma*np.sqrt(np.arange(1,horizon+1)/7+1)
    dates=pd.date_range(series.index[-1]+pd.Timedelta(days=1),periods=horizon)
    warnings_list=['Intervals are heuristic planning bands estimated from held-out residuals; coverage is not guaranteed.','Observed sales can understate demand during stockouts.']
    if horizon>len(y)//2:warnings_list.append('Long horizon relative to history: use with additional review.')
    return {'model':champion,'train_end':series.index[-1].date().isoformat(),'history_days':len(y),'horizon':horizon,'forecasts':[{'date':d.date().isoformat(),'prediction':round(float(p),2),'lower':round(float(max(0,l)),2),'upper':round(float(u),2)} for d,p,l,u in zip(dates,forecast,forecast-width,forecast+width)],'validation':boards,'holdout':test,'baseline_holdout':baseline,'residual_std':sigma,'failed_models':failed,'warnings':warnings_list,'history':[{'date':d.date().isoformat(),'quantity':float(v)} for d,v in series.tail(90).items()]}

