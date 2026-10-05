import os,sys,time,json,hashlib,subprocess,threading
from datetime import timedelta
from sqlalchemy import select,update
from src.core.db import session,init_db
from src.core.auth import require,worker_context,audit,allowed
from src.core.models import Job,Schedule,now
from src.core.config import ROOT

def queue(ctx,kind,payload,dedupe=None):
    permissions={'forecast':'forecast.run','index':'knowledge.write','research':'market.read','chat':'chat'}
    if kind not in permissions:raise ValueError('Unsupported job type.')
    require(ctx,permissions[kind])
    # A brief cache suppresses double clicks, without reusing yesterday's analysis
    # or a different staff member's private task.
    current=worker_context(ctx.user_id,ctx.tenant_id)
    key=dedupe or hashlib.sha256((ctx.user_id+current.role+kind+str(int(time.time()//60))+json.dumps(payload,sort_keys=True)).encode()).hexdigest()
    with session() as s:
        old=s.scalar(select(Job).where(Job.tenant_id==ctx.tenant_id,Job.dedupe_key==key))
        if old:return old.id
        j=Job(tenant_id=ctx.tenant_id,user_id=ctx.user_id,kind=kind,payload=payload,dedupe_key=key)
        s.add(j);s.flush();audit(s,ctx,'job.queued',{'job_id':j.id,'kind':kind});return j.id

def jobs(ctx):
    worker_context(ctx.user_id,ctx.tenant_id)
    with session() as s:
        q=select(Job).where(Job.tenant_id==ctx.tenant_id)
        # Jobs can include restricted answers; only the requester sees their results.
        return s.scalars(q.where(Job.user_id==ctx.user_id).order_by(Job.created_at.desc()).limit(50)).all()

def get_job(ctx,jid):
    j=next((j for j in jobs(ctx) if j.id==jid),None)
    if not j:return None
    permission={'forecast':'forecast.run','index':'knowledge.write','research':'market.read','chat':'chat'}[j.kind]
    if not allowed(ctx,permission):return None
    from src.services.reports import scope_allowed
    report=j.result.get('report') if isinstance(j.result,dict) else None
    if report and not scope_allowed(ctx,report.get('scope','general')):return None
    return j

def cancel(ctx,jid):
    worker_context(ctx.user_id,ctx.tenant_id)
    with session() as s:
        j=s.scalar(select(Job).where(Job.id==jid,Job.tenant_id==ctx.tenant_id,Job.user_id==ctx.user_id))
        if not j:raise PermissionError('Job unavailable.')
        if j.state not in {'queued','running'}:raise ValueError('Job is already finished.')
        j.state='cancelled';audit(s,ctx,'job.cancelled',{'job_id':jid})

def execute_job(jid):
    with session() as s:
        j=s.get(Job,jid)
        if not j or j.state not in {'queued','running'}:return
        actor=j.user_id;workspace=j.tenant_id;kind=j.kind;payload=j.payload
    try:
        ctx=worker_context(actor,workspace)
        if kind=='forecast':
            from src.services.analytics import forecast_product
            result=forecast_product(ctx,**payload)
        elif kind=='index':
            from src.rag.retrieval import build_index
            result=build_index(ctx,**payload)
        elif kind=='research':
            from src.services.market import research
            result=research(ctx,**payload)
        elif kind=='chat':
            from src.agents.pipeline import run_case
            result=run_case(ctx,**payload)
        with session() as s:
            j=s.get(Job,jid)
            if j.state!='cancelled':j.state='completed';j.result=json.loads(json.dumps(result,default=str));j.finished_at=now()
    except Exception as exc:
        with session() as s:
            j=s.get(Job,jid)
            if j.state!='cancelled':j.state='failed';j.error=str(exc)[:500];j.finished_at=now()

def claim():
    with session() as s:
        candidate=s.scalar(select(Job).where(Job.state=='queued').order_by(Job.created_at).limit(1))
        if not candidate:return None
        result=s.execute(update(Job).where(Job.id==candidate.id,Job.state=='queued').values(state='running',attempts=Job.attempts+1,started_at=now()))
        return candidate.id if result.rowcount else None

def schedule(ctx,kind,payload,interval_hours):
    require(ctx,'jobs.manage')
    if kind not in {'forecast','research'} or not 1<=interval_hours<=720:raise ValueError('Unsupported schedule.')
    required='forecast.run' if kind=='forecast' else 'market.read';require(ctx,required)
    with session() as s:
        item=Schedule(tenant_id=ctx.tenant_id,user_id=ctx.user_id,kind=kind,payload=payload,interval_hours=interval_hours)
        s.add(item);s.flush();audit(s,ctx,'schedule.created',{'schedule_id':item.id});return item.id

def schedules(ctx):
    require(ctx,'jobs.manage')
    with session() as s:return s.scalars(select(Schedule).where(Schedule.tenant_id==ctx.tenant_id)).all()

def toggle_schedule(ctx,sid,enabled):
    require(ctx,'jobs.manage')
    with session() as s:
        item=s.scalar(select(Schedule).where(Schedule.id==sid,Schedule.tenant_id==ctx.tenant_id))
        if not item:raise ValueError('Schedule unavailable.')
        item.enabled=enabled;audit(s,ctx,'schedule.toggled',{'id':sid,'enabled':enabled})

def tick():
    with session() as s:due=s.scalars(select(Schedule).where(Schedule.enabled.is_(True),Schedule.next_run<=now())).all()
    for item in due:
        try:
            ctx=worker_context(item.user_id,item.tenant_id)
            queue(ctx,item.kind,item.payload,dedupe='schedule:'+item.id+':'+item.next_run.isoformat())
            with session() as s:
                x=s.get(Schedule,item.id);x.next_run=now()+timedelta(hours=x.interval_hours)
        except PermissionError:
            with session() as s:s.get(Schedule,item.id).enabled=False

def run_worker():
    init_db();timeout=int(os.getenv('JOB_TIMEOUT_SECONDS','600'))
    while True:
        try:
            tick()
            with session() as s:
                stale=s.scalars(select(Job).where(Job.state=='running',Job.started_at<now()-timedelta(seconds=timeout+30))).all()
                for j in stale:j.state='failed';j.error='Worker interrupted or deadline exceeded. Submit a new run.';j.finished_at=now()
            jid=claim()
            if not jid:time.sleep(2);continue
            p=subprocess.Popen([sys.executable,'-m','src.services.jobs','--run',jid],cwd=ROOT,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
            start=time.monotonic()
            while p.poll() is None:
                with session() as s:state=s.get(Job,jid).state
                if state=='cancelled' or time.monotonic()-start>timeout:
                    p.terminate()
                    try:p.wait(timeout=5)
                    except subprocess.TimeoutExpired:p.kill()
                    with session() as s:
                        j=s.get(Job,jid)
                        if j.state!='cancelled':j.state='failed';j.error='Job deadline exceeded.';j.finished_at=now()
                    break
                time.sleep(1)
            with session() as s:
                j=s.get(Job,jid)
                if j.state=='running':j.state='failed';j.error='Worker exited without a result.';j.finished_at=now()
        except Exception:time.sleep(3)

def start_local_worker():
    thread=threading.Thread(target=run_worker,daemon=True,name='smartstock-worker');thread.start();return thread

if __name__=='__main__':
    if '--run' in sys.argv:execute_job(sys.argv[sys.argv.index('--run')+1])
    else:run_worker()
