from fastapi import APIRouter, HTTPException, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Conductor, Permisionario, Admin
from app.auth import verify_password, create_token, decode_token

router = APIRouter(prefix="/api/auth")
templates = Jinja2Templates(directory="app/templates")


class LoginRequest(BaseModel):
    username: str
    password: str


@router.post("/login")
async def login(data: LoginRequest, db: AsyncSession = Depends(get_db)):
    for model, role in [(Conductor, "conductor"), (Permisionario, "permisionario"), (Admin, "admin")]:
        result = await db.execute(select(model).where(model.username == data.username))
        user = result.scalar_one_or_none()
        if user and verify_password(data.password, user.password_hash):
            token = create_token({
                "user_id": user.id,
                "role": role,
                "username": user.username,
            })
            return {
                "token": token,
                "role": role,
                "user_id": user.id,
                "nombre": user.nombre,
            }
    raise HTTPException(401, "Usuario o contraseña incorrectos")


@router.get("/me")
async def me(request: Request, db: AsyncSession = Depends(get_db)):
    auth = request.headers.get("Authorization", "").replace("Bearer ", "")
    payload = decode_token(auth)
    if not payload:
        raise HTTPException(401, "Token inválido")
    return payload
