"""Conservative invalidation of artifacts when a business source is removed."""
from sqlalchemy import select,delete,update
from src.core.db import session
from src.core.models import Audit,Report,AgentRun,Job,Approval,now

def purge_revision(ctx):
    with session() as s:
        return s.scalar(select(Audit.id).where(Audit.tenant_id==ctx.tenant_id,Audit.action.in_(['dataset.deleted','knowledge.deleted'])).order_by(Audit.created_at.desc()).limit(1)) or ''

def ensure_current(ctx,revision):
    if purge_revision(ctx)!=revision:raise ValueError('A source was deleted during this task. Run the analysis again.')

def clear_derived(s,ctx):
    # Cross-source provenance can be mixed. Erase all saved answers/reports rather
    # than retaining a fragment from a removed source. Audit records contain IDs only.
    s.execute(delete(Report).where(Report.tenant_id==ctx.tenant_id))
    s.execute(delete(AgentRun).where(AgentRun.tenant_id==ctx.tenant_id))
    s.execute(update(Job).where(Job.tenant_id==ctx.tenant_id).values(state='cancelled',payload={},result={},error='Source deletion invalidated this task.',finished_at=now()))
    s.execute(update(Approval).where(Approval.tenant_id==ctx.tenant_id,Approval.state=='pending').values(state='cancelled',decision_note='Source deleted; submit a current proposal.'))
