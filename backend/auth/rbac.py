"""Minimal JWT authentication and role dependencies. Set SPECTRA_JWT_SECRET in production."""
from __future__ import annotations
import os
from datetime import datetime, timedelta, timezone
from enum import Enum
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt

SECRET=os.getenv("SPECTRA_JWT_SECRET","development-only-change-me")
ALGORITHM="HS256"
class Role(str,Enum): ADMIN="Admin"; EDITOR="Editor"; VIEWER="Viewer"
security=HTTPBearer(auto_error=False)
def create_token(subject: str, role: Role=Role.VIEWER, tenant: str="default", expires_minutes: int=60):
    now=datetime.now(timezone.utc)
    return jwt.encode({"sub":subject,"role":role.value,"tenant":tenant,"iat":now,"exp":now+timedelta(minutes=expires_minutes)},SECRET,algorithm=ALGORITHM)
async def current_user(credentials: HTTPAuthorizationCredentials|None=Depends(security)):
    if not credentials: return {"sub":"anonymous","role":Role.VIEWER.value,"tenant":"default"}
    try: return jwt.decode(credentials.credentials,SECRET,algorithms=[ALGORITHM])
    except JWTError: raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,detail="Invalid or expired bearer token")
def require_role(*roles: Role):
    async def check(user=Depends(current_user)):
        if user.get("role") not in {r.value for r in roles}: raise HTTPException(403,"Insufficient role")
        return user
    return check
