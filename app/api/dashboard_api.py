"""Dashboard REST API for managing tenants, menus, and tickets."""

import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.core import (
    ServiceMenu,
    Tenant,
    TenantMenu,
    TicketBalance,
    TicketLog,
)
from app.schemas.deploy import DeployLimbRequest
from app.schemas.menu_factory import MenuInstallRequest
from app.schemas.tenant import TenantConfigUpdate, TenantCreate, TenantResponse
from app.schemas.ticket import TicketAddRequest, TicketBalanceResponse

logger = logging.getLogger("smartexec.dashboard")

router = APIRouter()


# ── Tenants ──────────────────────────────────────────────────────────


@router.get("/tenants")
def list_tenants(db: Session = Depends(get_db)):
    """List all tenants with ticket balance and enabled menus."""
    tenants = db.query(Tenant).order_by(Tenant.created_at.desc()).all()
    results = []
    for t in tenants:
        balance = db.query(TicketBalance).filter_by(tenant_id=t.id).first()
        menus = (
            db.query(TenantMenu, ServiceMenu)
            .join(ServiceMenu, TenantMenu.menu_id == ServiceMenu.id)
            .filter(TenantMenu.tenant_id == t.id)
            .all()
        )
        menu_list = [
            {
                "menu_id": tm.menu_id,
                "name": sm.name,
                "status": tm.status,
                "installed_at": tm.installed_at.isoformat() if tm.installed_at else None,
            }
            for tm, sm in menus
        ]
        results.append(
            {
                "id": t.id,
                "name": t.name,
                "industry": t.industry,
                "line_user_id": t.line_user_id,
                "created_at": t.created_at.isoformat() if t.created_at else None,
                "ticket_balance": balance.current_balance if balance else 0,
                "menus": menu_list,
            }
        )
    return results


@router.post("/tenants")
def create_tenant(req: TenantCreate, db: Session = Depends(get_db)):
    """Create a new tenant."""
    tenant_id = str(uuid.uuid4())
    tenant = Tenant(
        id=tenant_id,
        name=req.name,
        industry=req.industry,
        line_user_id=req.line_user_id,
        config=req.config,
    )
    db.add(tenant)
    db.add(TicketBalance(tenant_id=tenant_id, current_balance=10))
    db.commit()
    logger.info("Created tenant %s (%s)", tenant_id, req.name)
    return {"id": tenant_id, "name": req.name, "message": "Tenant created"}


@router.get("/tenants/{tenant_id}/config")
def get_tenant_config(tenant_id: str, db: Session = Depends(get_db)):
    """Get tenant config (masks BYOK keys)."""
    tenant = db.query(Tenant).filter_by(id=tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")

    config = dict(tenant.config) if tenant.config else {}
    # Mask sensitive keys
    if "byok" in config and "anthropic_key" in config["byok"]:
        key = config["byok"]["anthropic_key"]
        if len(key) > 10:
            config["byok"]["anthropic_key"] = key[:8] + "..." + key[-4:]
    return {"tenant_id": tenant_id, "config": config}


@router.put("/tenants/{tenant_id}/config")
def update_tenant_config(
    tenant_id: str, req: TenantConfigUpdate, db: Session = Depends(get_db)
):
    """Update tenant config (deep merge)."""
    tenant = db.query(Tenant).filter_by(id=tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")

    existing = dict(tenant.config) if tenant.config else {}
    # Deep merge
    for key, value in req.config.items():
        if isinstance(value, dict) and isinstance(existing.get(key), dict):
            existing[key].update(value)
        else:
            existing[key] = value
    tenant.config = existing
    db.commit()
    return {"tenant_id": tenant_id, "config": existing, "message": "Config updated"}


# ── Menus ────────────────────────────────────────────────────────────


@router.get("/tenants/{tenant_id}/menus")
def list_tenant_menus(tenant_id: str, db: Session = Depends(get_db)):
    """List menus for a tenant, showing available and installed."""
    tenant = db.query(Tenant).filter_by(id=tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")

    all_menus = db.query(ServiceMenu).filter_by(is_active=True).all()
    installed = {
        tm.menu_id: tm
        for tm in db.query(TenantMenu).filter_by(tenant_id=tenant_id).all()
    }

    result = []
    for m in all_menus:
        tm = installed.get(m.id)
        result.append(
            {
                "menu_id": m.id,
                "name": m.name,
                "description": m.description,
                "base_ticket_cost": m.base_ticket_cost,
                "installed": tm is not None,
                "status": tm.status if tm else None,
                "installed_at": tm.installed_at.isoformat() if tm and tm.installed_at else None,
            }
        )
    return result


@router.post("/tenants/{tenant_id}/menus")
def manage_tenant_menu(
    tenant_id: str, req: MenuInstallRequest, db: Session = Depends(get_db)
):
    """Install, enable, or disable a menu for a tenant."""
    tenant = db.query(Tenant).filter_by(id=tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")

    menu = db.query(ServiceMenu).filter_by(id=req.menu_id, is_active=True).first()
    if not menu:
        raise HTTPException(status_code=404, detail="Menu not found")

    existing = (
        db.query(TenantMenu)
        .filter_by(tenant_id=tenant_id, menu_id=req.menu_id)
        .first()
    )

    if req.action == "install":
        if existing:
            return {"message": "Menu already installed", "status": existing.status}

        # Check ticket balance
        balance = db.query(TicketBalance).filter_by(tenant_id=tenant_id).first()
        if not balance or balance.current_balance < menu.base_ticket_cost:
            raise HTTPException(
                status_code=400,
                detail=f"Insufficient tickets. Need {menu.base_ticket_cost}, have {balance.current_balance if balance else 0}",
            )

        # Consume tickets
        balance.current_balance -= menu.base_ticket_cost
        db.add(
            TicketLog(
                tenant_id=tenant_id,
                action="install_menu",
                tickets_consumed=menu.base_ticket_cost,
                description=f"Installed menu: {menu.name}",
            )
        )

        # Install
        db.add(TenantMenu(tenant_id=tenant_id, menu_id=req.menu_id, status="enabled"))
        db.commit()
        return {"message": f"Menu '{menu.name}' installed", "tickets_consumed": menu.base_ticket_cost}

    elif req.action == "enable":
        if not existing:
            raise HTTPException(status_code=400, detail="Menu not installed")
        existing.status = "enabled"
        db.commit()
        return {"message": f"Menu '{menu.name}' enabled"}

    elif req.action == "disable":
        if not existing:
            raise HTTPException(status_code=400, detail="Menu not installed")
        existing.status = "disabled"
        db.commit()
        return {"message": f"Menu '{menu.name}' disabled"}

    else:
        raise HTTPException(status_code=400, detail=f"Unknown action: {req.action}")


# ── Tickets ──────────────────────────────────────────────────────────


@router.get("/tickets")
def list_ticket_balances(db: Session = Depends(get_db)):
    """Get ticket balances and logs for all tenants."""
    balances = (
        db.query(TicketBalance, Tenant)
        .join(Tenant, TicketBalance.tenant_id == Tenant.id)
        .all()
    )
    results = []
    for tb, t in balances:
        logs = (
            db.query(TicketLog)
            .filter_by(tenant_id=tb.tenant_id)
            .order_by(TicketLog.created_at.desc())
            .limit(20)
            .all()
        )
        results.append(
            {
                "tenant_id": tb.tenant_id,
                "tenant_name": t.name,
                "current_balance": tb.current_balance,
                "logs": [
                    {
                        "id": log.id,
                        "action": log.action,
                        "tickets_consumed": log.tickets_consumed,
                        "description": log.description,
                        "created_at": log.created_at.isoformat() if log.created_at else None,
                    }
                    for log in logs
                ],
            }
        )
    return results


@router.post("/tickets")
def add_tickets(req: TicketAddRequest, db: Session = Depends(get_db)):
    """Add (refill) tickets to a tenant."""
    balance = db.query(TicketBalance).filter_by(tenant_id=req.tenant_id).first()
    if not balance:
        raise HTTPException(status_code=404, detail="Tenant not found")

    balance.current_balance += req.tickets
    db.add(
        TicketLog(
            tenant_id=req.tenant_id,
            action="admin_add",
            tickets_consumed=-req.tickets,  # negative = refill
            description=req.description,
        )
    )
    db.commit()
    return {
        "tenant_id": req.tenant_id,
        "new_balance": balance.current_balance,
        "tickets_added": req.tickets,
    }


# ── Limb Deployment ─────────────────────────────────────────────────


@router.post("/tenants/{tenant_id}/deploy-limb")
def deploy_limb(
    tenant_id: str, req: DeployLimbRequest, db: Session = Depends(get_db)
):
    """Generate a Limb bundle (ZIP) for the tenant."""
    from app.services.deploy_service import generate_limb_bundle

    tenant = db.query(Tenant).filter_by(id=tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")

    try:
        zip_path = generate_limb_bundle(tenant, req.pattern, req.menus)
        # Update tenant config with deployment info
        config = dict(tenant.config) if tenant.config else {}
        config["limb"] = {
            "last_deployed_at": datetime.now(timezone.utc).isoformat(),
            "deployed_pattern": req.pattern,
            "limb_version": "1.0",
        }
        tenant.config = config
        db.commit()
        return {"message": "Limb bundle generated", "download_path": f"/api/tenants/{tenant_id}/deploy-limb/download"}
    except Exception as e:
        logger.error("Deploy error: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/tenants/{tenant_id}/deploy-limb/download")
def download_limb(tenant_id: str, db: Session = Depends(get_db)):
    """Download the generated Limb bundle ZIP."""
    import os

    zip_path = os.path.join("limb_bundles", f"{tenant_id}.zip")
    if not os.path.exists(zip_path):
        raise HTTPException(status_code=404, detail="Bundle not found. Generate first.")
    return FileResponse(zip_path, filename=f"limb-{tenant_id}.zip", media_type="application/zip")
