"""Server-operator maintenance. Dry run by default; never deletes source records."""
import argparse,os
from datetime import timedelta
from sqlalchemy import select,delete,func
from src.core.db import session
from src.core.models import Report,AgentRun,Research,Job,Session,LoginAttempt,now

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--days',type=int,default=int(os.getenv('RETENTION_DAYS','90')))
    parser.add_argument('--apply',action='store_true',help='Delete expired derived records across all workspaces')
    args=parser.parse_args()
    if args.days<1:parser.error('days must be positive')
    cutoff=now()-timedelta(days=args.days)
    with session() as s:
        for model in [Report,AgentRun,Research,Job,LoginAttempt]:
            criteria=model.created_at<cutoff
            if model is Job:criteria=criteria & Job.state.in_(['completed','failed','cancelled'])
            count=s.scalar(select(func.count()).select_from(model).where(criteria))
            print(model.__tablename__,count,'delete' if args.apply else 'eligible (dry run)')
            if args.apply:s.execute(delete(model).where(criteria))
        expired=s.scalar(select(func.count()).select_from(Session).where(Session.expires_at<now()))
        print('expired sessions',expired)
        if args.apply:s.execute(delete(Session).where(Session.expires_at<now()))
    print('Source sales, knowledge, audit records and business commitments are preserved.')

if __name__=='__main__':main()
