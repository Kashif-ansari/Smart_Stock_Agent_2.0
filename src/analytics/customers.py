from collections import Counter
from itertools import combinations
import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import silhouette_score,average_precision_score,brier_score_loss
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline

def rfm(frame,asof=None):
    if frame.empty:return pd.DataFrame()
    d=frame[frame.customer_id.notna() & (frame.customer_id!='') & (frame.quantity>0)].copy()
    if d.empty:return pd.DataFrame()
    cutoff=pd.Timestamp(asof) if asof is not None else d.date.max()+pd.Timedelta(days=1)
    d=d[d.date<cutoff]
    if d.empty:return pd.DataFrame()
    d['frequency_id']=d.transaction_id.where(d.transaction_id.notna(),d.date.astype(str))
    result=d.groupby('customer_id').agg(last_purchase=('date','max'),frequency=('frequency_id','nunique'),monetary=('revenue',lambda x:x.sum(min_count=1)))
    result['recency']=(cutoff-result.last_purchase).dt.days
    result['segment']=np.select([result.recency>60,result.recency>30,(result.frequency>=result.frequency.quantile(.7)) & (result.recency<=14)],['Inactive','At risk','Loyal'],default='Active')
    return result.reset_index()

def segment_customers(frame):
    result=rfm(frame)
    metrics={}
    valid=result.dropna(subset=['recency','frequency','monetary']) if not result.empty else result
    if len(valid)>=12:
        X=StandardScaler().fit_transform(np.log1p(valid[['recency','frequency','monetary']].clip(lower=0)))
        best=None
        for k in range(2,min(6,len(valid)-1)+1):
            model=KMeans(n_clusters=k,random_state=42,n_init=10)
            labels=model.fit_predict(X)
            if len(set(labels))<2:continue
            quality=silhouette_score(X,labels)
            if best is None or quality>best[0]:best=(quality,labels,k)
        if best:
            result['cluster']=None;result.loc[valid.index,'cluster']=best[1]
            metrics={'k':best[2],'silhouette':round(float(best[0]),3),'note':'Clusters are descriptive groups, not causal customer labels.'}
    return result,metrics

def basket_rules(frame,min_support=.02,min_confidence=.3):
    d=frame[(frame.quantity>0)&frame.transaction_id.notna()]
    if d.empty:return pd.DataFrame(),0
    # Transaction IDs may repeat on another date; scope a basket by date as well.
    baskets=d.groupby(['date','transaction_id']).sku.apply(lambda x:sorted(set(x))).tolist()
    items=Counter();pairs=Counter()
    for basket in baskets:
        if len(basket)>100:continue
        items.update(basket);pairs.update(combinations(basket,2))
    n=len(baskets);rows=[]
    if n<20:return pd.DataFrame(),n
    for (a,b),count in pairs.items():
        support=count/n
        for antecedent,consequent in [(a,b),(b,a)]:
            conf=count/items[antecedent];lift=conf/(items[consequent]/n)
            if support>=min_support and conf>=min_confidence:
                rows.append({'buy':antecedent,'also_buy':consequent,'support':round(support,4),'confidence':round(conf,4),'lift':round(lift,3),'shared_baskets':count})
    result=pd.DataFrame(rows)
    return result.sort_values(['lift','shared_baskets'],ascending=False) if not result.empty else result,n

def churn(frame,horizon=30):
    if frame.empty or (frame.date.max()-frame.date.min()).days<120:return {'available':False,'reason':'At least 120 days of identifiable customer history are required.'}
    end=frame.date.max()+pd.Timedelta(days=1)
    def labelled(cutoff):
        obs=frame[(frame.date>=cutoff-pd.Timedelta(days=90))&(frame.date<cutoff)]
        f=rfm(obs,cutoff)
        if f.empty:return f
        future=frame[(frame.date>=cutoff)&(frame.date<cutoff+pd.Timedelta(days=horizon))&(frame.quantity>0)]
        buyers=set(future.customer_id.dropna())
        f['inactive_next_period']=(~f.customer_id.isin(buyers)).astype(int)
        return f.dropna(subset=['monetary'])
    test_cut=end-pd.Timedelta(days=horizon)
    train_cut=test_cut-pd.Timedelta(days=horizon)
    train=labelled(train_cut);test=labelled(test_cut)
    if min(len(train),len(test))<40 or train.inactive_next_period.value_counts().min()<5 or train.inactive_next_period.nunique()<2 or test.inactive_next_period.nunique()<2:
        return {'available':False,'reason':'Insufficient customers or outcome variation for a defensible supervised model. RFM inactivity flags remain available.'}
    columns=['recency','frequency','monetary']
    model=make_pipeline(StandardScaler(),LogisticRegression(class_weight='balanced',random_state=42,max_iter=1000))
    model.fit(train[columns],train.inactive_next_period)
    pred=model.predict_proba(test[columns])[:,1]
    current=rfm(frame,end).dropna(subset=['monetary'])
    current['inactivity_probability']=model.predict_proba(current[columns])[:,1]
    return {'available':True,'pr_auc':float(average_precision_score(test.inactive_next_period,pred)),'brier':float(brier_score_loss(test.inactive_next_period,pred)),'baseline_prevalence':float(test.inactive_next_period.mean()),'train_cutoff':str(train_cut.date()),'test_cutoff':str(test_cut.date()),'horizon':horizon,'customers':current.sort_values('inactivity_probability',ascending=False),'note':'Outcome: no repeat purchase in the next 30 days. Predictions require prospective calibration; they do not explain customer intent.'}

