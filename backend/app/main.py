from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.database import Base, engine
from app.models import Role, User
from app.routers import auth, dashboard, records, users
from app.security import get_password_hash
from app.services.stages import ensure_default_stages

settings = get_settings()

app = FastAPI(title=settings.app_name)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)


@app.on_event('startup')
def on_startup():
    Base.metadata.create_all(bind=engine)

    # Auto-create default super admin when empty DB.
    from app.database import SessionLocal

    db = SessionLocal()
    try:
        existing = db.query(User).filter(User.role == Role.SUPER_ADMIN).first()
        if not existing:
            db.add(
                User(
                    full_name=settings.default_super_admin_name,
                    email=settings.default_super_admin_email,
                    password_hash=get_password_hash(settings.default_super_admin_password),
                    role=Role.SUPER_ADMIN,
                    is_active=True,
                    receive_alert=True,
                )
            )
        ensure_default_stages(db)
        db.commit()
    finally:
        db.close()


@app.get('/health')
def health():
    return {'status': 'ok'}


@app.get(f'{settings.api_v1_prefix}/health')
def health_v1():
    return {'status': 'ok'}


app.include_router(auth.router, prefix=settings.api_v1_prefix)
app.include_router(users.router, prefix=settings.api_v1_prefix)
app.include_router(records.router, prefix=settings.api_v1_prefix)
app.include_router(dashboard.router, prefix=settings.api_v1_prefix)
