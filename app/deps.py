from fastapi import Request, HTTPException, Depends
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.auth import decode_token
from app.models import Conductor, Permisionario, Admin


async def get_current_user(request: Request, db: AsyncSession = Depends(get_db)):
    auth = request.headers.get("Authorization", "")
    token = auth.replace("Bearer ", "")
    if not token:
        token = request.cookies.get("token", "")
    payload = decode_token(token)
    if not payload:
        raise HTTPException(401, "No autenticado")
    role = payload.get("role")
    user_id = payload.get("user_id")
    models = {
        "conductor": Conductor,
        "permisionario": Permisionario,
        "admin": Admin,
    }
    model = models.get(role)
    if not model:
        raise HTTPException(401, "Rol inválido")
    result = await db.execute(select(model).where(model.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(401, "Usuario no encontrado")
    nombre = getattr(user, "nombre", "")
    apellido = getattr(user, "apellido", "")
    username = getattr(user, "username", "") or getattr(user, "dni", "") or getattr(user, "codigo", "")
    return {
        "id": user.id,
        "role": role,
        "nombre": f"{nombre} {apellido}".strip(),
        "username": username,
    }


def require_role(*roles: str):
    async def _check(current_user=Depends(get_current_user)):
        if current_user["role"] not in roles:
            raise HTTPException(403, "No tenés permisos para esta acción")
        return current_user
    return _check


async def require_auth_page(request: Request, db: AsyncSession = Depends(get_db)):
    token = request.cookies.get("token", "")
    if not token:
        auth = request.headers.get("Authorization", "")
        token = auth.replace("Bearer ", "") if auth else ""
        if not token and request.query_params.get("token"):
            token = request.query_params["token"]
    payload = decode_token(token) if token else None
    if payload:
        return payload
    return RedirectResponse(url="/login", status_code=303)


async def require_role_page(*roles: str):
    async def _check(request: Request, db: AsyncSession = Depends(get_db)):
        result = await require_auth_page(request, db)
        if isinstance(result, RedirectResponse):
            return result
        if result["role"] not in roles:
            return RedirectResponse(url="/login", status_code=303)
        return result
    return _check