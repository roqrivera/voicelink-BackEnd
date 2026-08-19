from fastapi import APIRouter

from app.api.v1.superadmin.endpoints import (
    activity_history,
    admins,
    analytics,
    audit,
    auth,
    billing,
    config,
    dids,
    login_history,
    sip_trunks,
    smtp_settings,
    tenant_activity_history,
    tenants,
    tickets,
    users,
)

api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth", tags=["superadmin-auth"])
api_router.include_router(admins.router, prefix="/admins", tags=["superadmin-admins"])
api_router.include_router(tenants.router, prefix="/tenants", tags=["superadmin-tenants"])
api_router.include_router(users.router, prefix="/users", tags=["superadmin-users"])
api_router.include_router(login_history.router, prefix="/login-history", tags=["superadmin-login-history"])
api_router.include_router(activity_history.router, prefix="/activity-history", tags=["superadmin-activity-history"])
api_router.include_router(
    tenant_activity_history.router, prefix="/tenant-activity-history", tags=["superadmin-tenant-activity-history"]
)
api_router.include_router(dids.router, prefix="/dids", tags=["superadmin-dids"])
api_router.include_router(sip_trunks.router, prefix="/sip-trunks", tags=["superadmin-sip-trunks"])
api_router.include_router(billing.router, prefix="/billing", tags=["superadmin-billing"])
api_router.include_router(tickets.router, prefix="/tickets", tags=["superadmin-tickets"])
api_router.include_router(audit.router, prefix="/audit", tags=["superadmin-audit"])
api_router.include_router(analytics.router, prefix="/analytics", tags=["superadmin-analytics"])
api_router.include_router(config.router, prefix="/config", tags=["superadmin-config"])
api_router.include_router(smtp_settings.router, prefix="/smtp-settings", tags=["superadmin-smtp-settings"])
