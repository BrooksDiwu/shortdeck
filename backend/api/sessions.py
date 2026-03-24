
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

from ..models.schemas import SessionCreate, SessionResponse
from ..services.session_service import SessionService

router = APIRouter(prefix="/sessions", tags=["sessions"])

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/sessions", auto_error=False)
@router.post("", response_model=SessionResponse, status_code=status.HTTP_201_CREATED)
async def create_session(body: SessionCreate) -> SessionResponse:
    """Create a new named session and return a signed JWT."""
    service = SessionService()
    player, token, expires_at = await service.create_session(body.name)
    return SessionResponse(
        session_id=player.session_id,
        token=token,
        expires_at=expires_at,
    )
@router.post("/refresh", response_model=SessionResponse)
async def refresh_session(token: str = Depends(oauth2_scheme)) -> SessionResponse:
    """Exchange a valid (non-expired) token for a new one."""
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing token")
    service = SessionService()
    try:
        new_token, session_id, expires_at = await service.refresh_token(token)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid or expired token: {exc}",
        )
    return SessionResponse(
        session_id=session_id,
        token=new_token,
        expires_at=expires_at,
    )
@router.get("/me")
async def get_me(token: str = Depends(oauth2_scheme)) -> dict:
    """Return current session info."""
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing token")
    service = SessionService()
    try:
        session_id = await service.validate_token(token)
        player = await service.get_session(session_id)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid or expired token: {exc}",
        )
    return {
        "session_id": player.session_id,
        "name": player.name,
        "is_admin": player.is_admin,
        "joined_at": player.joined_at.isoformat(),
    }
