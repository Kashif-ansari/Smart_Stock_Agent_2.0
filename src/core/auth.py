from dataclasses import dataclass
from datetime import timedelta
import base64, hashlib, hmac, os, re, secrets
from sqlalchemy import select, delete
from .db import session
from .models import User, Tenant, Membership, Session, LoginAttempt, Invite, Audit, now
from .config import flag

PERMISSIONS = {
 'owner': {'*'},
 'manager': {'sales.read','sales.write','inventory.read','inventory.write','forecast.run','customers.read','finance.read','market.read','approvals.read','approvals.decide','reports.read','reports.write','knowledge.read','knowledge.write','chat','jobs.manage'},
 'sales': {'sales.read','sales.write','inventory.read','customers.read','reports.read','chat','knowledge.read','approvals.read'},
 'inventory': {'sales.read','inventory.read','inventory.write','forecast.run','reports.read','reports.write','chat','knowledge.read','approvals.read'},
 'finance': {'sales.read','inventory.read','finance.read','finance.write','reports.read','reports.write','chat','knowledge.read','approvals.read'},
 'hr': {'hr.read','hr.write','knowledge.read','knowledge.write','chat','reports.read','reports.write'},
 'analyst': {'sales.read','inventory.read','forecast.run','customers.read','market.read','reports.read','reports.write','knowledge.read','chat'},
}

@dataclass(frozen=True)
class Context:
    user_id: str
    tenant_id: str
    role: str
    name: str = ''

def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()

def password_hash(password):
    if len(password) < 12 or len(password) > 256:
        raise ValueError('Use a password of 12 to 256 characters.')
    salt = secrets.token_bytes(16)
    derived = hashlib.pbkdf2_hmac('sha256', password.encode(), salt, 600000)
    return 'pbkdf2_sha256$600000$' + base64.b64encode(salt).decode() + '$' + base64.b64encode(derived).decode()

def password_ok(password, stored):
    try:
        _, count, salt, expected = stored.split('$')
        actual = hashlib.pbkdf2_hmac('sha256', password.encode(), base64.b64decode(salt), int(count))
        return hmac.compare_digest(actual, base64.b64decode(expected))
    except (ValueError, TypeError):
        return False

def email_clean(email):
    email = email.strip().casefold()
    if not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', email) or len(email)>254:
        raise ValueError('Enter a valid email address.')
    return email

def issue(s, user_id, tenant_id):
    token = secrets.token_urlsafe(40)
    s.add(Session(token_hash=digest(token), user_id=user_id, tenant_id=tenant_id, expires_at=now()+timedelta(hours=int(os.getenv('SESSION_HOURS','8')))))
    return token

def register(name, email, password, business, invite_token=None):
    if not flag('ALLOW_SIGNUP', True) and not invite_token:
        raise ValueError('Registration is disabled. Ask the workspace owner for an invitation.')
    email = email_clean(email)
    if not name.strip() or not business.strip():
        raise ValueError('Name and business name are required.')
    hashed = password_hash(password)
    with session() as s:
        if s.scalar(select(User).where(User.email==email)):
            raise ValueError('This account cannot be created. Try signing in or contact the owner.')
        invite = s.get(Invite, digest(invite_token)) if invite_token else None
        if invite_token and (not invite or invite.email!=email or invite.expires_at < now()):
            raise ValueError('Invitation is invalid or expired.')
        u = User(name=name.strip()[:120], email=email, password_hash=hashed)
        s.add(u); s.flush()
        if invite:
            tid, role = invite.tenant_id, invite.role
            s.delete(invite)
        else:
            t=Tenant(name=business.strip()[:120]); s.add(t); s.flush()
            tid, role = t.id, 'owner'
        s.add(Membership(tenant_id=tid,user_id=u.id,role=role))
        return issue(s,u.id,tid)

def login(email,password):
    identity = digest(email.strip().casefold())
    with session() as s:
        recent=s.scalars(select(LoginAttempt).where(LoginAttempt.identity_hash==identity,LoginAttempt.created_at>now()-timedelta(minutes=15))).all()
        if len(recent)>=5:
            raise ValueError('Too many attempts. Try again after 15 minutes.')
        u=s.scalar(select(User).where(User.email==email.strip().casefold(),User.active.is_(True)))
        valid=bool(u and password_ok(password,u.password_hash))
        if valid:
            m=s.scalar(select(Membership).where(Membership.user_id==u.id,Membership.active.is_(True)))
            valid=bool(m)
        if not valid:
            s.add(LoginAttempt(identity_hash=identity)); s.flush()
        else:
            s.execute(delete(LoginAttempt).where(LoginAttempt.identity_hash==identity))
            return issue(s,u.id,m.tenant_id)
    raise ValueError('Email or password is incorrect.')

def context_from_token(token):
    if not token:return None
    with session() as s:
        sess=s.get(Session,digest(token))
        if not sess or sess.expires_at<now():return None
        u=s.get(User,sess.user_id)
        m=s.scalar(select(Membership).where(Membership.user_id==sess.user_id,Membership.tenant_id==sess.tenant_id,Membership.active.is_(True)))
        return Context(u.id,m.tenant_id,m.role,u.name) if u and u.active and m else None

def worker_context(user_id,tenant_id):
    with session() as s:
        u=s.get(User,user_id)
        m=s.scalar(select(Membership).where(Membership.user_id==user_id,Membership.tenant_id==tenant_id,Membership.active.is_(True)))
        if not u or not u.active or not m:raise PermissionError('Workspace access was revoked.')
        return Context(u.id,tenant_id,m.role,u.name)

def allowed(ctx,permission):
    try:
        current=worker_context(ctx.user_id,ctx.tenant_id)
        values=PERMISSIONS.get(current.role,set())
        return '*' in values or permission in values
    except (PermissionError,AttributeError):return False

def require(ctx,permission):
    if not allowed(ctx,permission):raise PermissionError('Your role does not allow this action.')

def logout(token):
    with session() as s:s.execute(delete(Session).where(Session.token_hash==digest(token)))

def tenant(ctx):
    worker_context(ctx.user_id,ctx.tenant_id)
    with session() as s:return s.get(Tenant,ctx.tenant_id)

def audit(s,ctx,action,detail):
    s.add(Audit(tenant_id=ctx.tenant_id,user_id=ctx.user_id,action=action,detail=detail))

def invite(ctx,email,role):
    require(ctx,'admin')
    if role not in PERMISSIONS or role=='owner':raise ValueError('Choose a staff role.')
    token=secrets.token_urlsafe(32)
    with session() as s:
        s.add(Invite(token_hash=digest(token),tenant_id=ctx.tenant_id,email=email_clean(email),role=role,expires_at=now()+timedelta(days=2)))
        audit(s,ctx,'invitation.created',{'role':role})
    return token

def oidc_login(info):
    if not info.get('email_verified',False) or not info.get('sub') or not info.get('iss'):
        raise ValueError('A verified email, subject and issuer are required from the identity provider.')
    subject=str(info['iss'])+'|'+str(info['sub'])
    email=email_clean(info.get('email',''))
    with session() as s:
        u=s.scalar(select(User).where(User.oidc_subject==subject))
        if not u:
            if not flag('ALLOW_SIGNUP',True):raise ValueError('Ask the owner to provision your account.')
            if s.scalar(select(User).where(User.email==email)):
                raise ValueError('An account already exists. Identity linking requires administrator verification.')
            u=User(name=info.get('name','Owner')[:120],email=email,oidc_subject=subject)
            t=Tenant(name='My store');s.add_all([u,t]);s.flush()
            s.add(Membership(user_id=u.id,tenant_id=t.id,role='owner'));s.flush()
        if not u.active:raise ValueError('Account disabled.')
        m=s.scalar(select(Membership).where(Membership.user_id==u.id,Membership.active.is_(True)))
        if not m:raise ValueError('No active membership.')
        return issue(s,u.id,m.tenant_id)
