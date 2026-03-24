
import json
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import redis.asyncio as aioredis
from jose import JWTError, jwt

from ..config import settings
from ..game.player import Player

ALGORITHM = "HS256"
SESSION_TTL = 86400 * 7  # 7 days
class SessionService:
    def __init__(self) -> None:
        self._redis: aioredis.Redis | None = None

    async def _get_redis(self) -> aioredis.Redis:
        if self._redis is None:
            self._redis = aioredis.from_url(
                settings.REDIS_URL,
                encoding="utf-8",
                decode_responses=True,
            )
        return self._redis

    def _encode_token(self, session_id: str, jti: str) -> tuple[str, datetime]:
        """Encode a JWT and return (token, expires_at)."""
        now = datetime.now(tz=timezone.utc)
        expires_at = now + timedelta(seconds=settings.JWT_EXPIRY_SECONDS)
        payload: dict[str, Any] = {
            "sub": session_id,
            "jti": jti,
            "iat": int(now.timestamp()),
            "exp": int(expires_at.timestamp()),
        }
        token = jwt.encode(payload, settings.SECRET_KEY, algorithm=ALGORITHM)
        return token, expires_at

    async def create_session(self, name: str) -> tuple[Player, str, datetime]:
        """Create a new session, store in Redis, return (player, token, expires_at)."""
        redis = await self._get_redis()
        session_id = str(uuid.uuid4())
        jti = str(uuid.uuid4())

        player = Player(
            session_id=session_id,
            name=name,
            stack=0,
            hole_cards=[],
            seat=-1,
            status="active",
            is_admin=False,
            joined_at=datetime.utcnow(),
        )

        # Store session in Redis
        session_data = player.to_dict()
        session_data["jti"] = jti
        await redis.setex(f"session:{session_id}", SESSION_TTL, json.dumps(session_data))

        # Also write to a sessions index for listing/revocation
        await redis.hset("sessions:index", session_id, json.dumps({"name": name, "jti": jti}))

        token, expires_at = self._encode_token(session_id, jti)
        return player, token, expires_at

    async def get_session(self, session_id: str) -> Player:
        """Load a player from Redis by session_id."""
        redis = await self._get_redis()
        raw = await redis.get(f"session:{session_id}")
        if raw is None:
            raise KeyError(f"Session {session_id} not found")
        data = json.loads(raw)
        return Player.from_dict(data)

    async def validate_token(self, token: str) -> str:
        """Validate JWT. Returns session_id. Raises on invalid or expired."""
        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
        except JWTError as exc:
            raise ValueError(f"Invalid token: {exc}")

        session_id: str = payload.get("sub", "")
        jti: str = payload.get("jti", "")

        if not session_id:
            raise ValueError("Token missing subject")

        # Check for revoked JTI
        redis = await self._get_redis()
        revoked = await redis.get(f"revoked_jti:{jti}")
        if revoked:
            raise ValueError("Token has been revoked")

        # Verify the JTI matches stored session
        raw = await redis.get(f"session:{session_id}")
        if raw is None:
            raise ValueError(f"Session {session_id} not found")

        session_data = json.loads(raw)
        if session_data.get("jti") != jti:
            raise ValueError("Token JTI mismatch — token may have been refreshed")

        return session_id

    async def refresh_token(self, token: str) -> tuple[str, str, datetime]:
        """Exchange a valid token for a new one. Returns (new_token, session_id, expires_at)."""
        session_id = await self.validate_token(token)

        # Decode old token to get old JTI for revocation
        try:
            old_payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
            old_jti = old_payload.get("jti", "")
        except JWTError:
            raise ValueError("Cannot decode old token")

        redis = await self._get_redis()

        # Revoke old JTI
        if old_jti:
            await redis.setex(
                f"revoked_jti:{old_jti}",
                settings.JWT_EXPIRY_SECONDS,
                "1",
            )

        # Generate new JTI
        new_jti = str(uuid.uuid4())

        # Update session record with new JTI
        raw = await redis.get(f"session:{session_id}")
        if raw:
            session_data = json.loads(raw)
            session_data["jti"] = new_jti
            await redis.setex(f"session:{session_id}", SESSION_TTL, json.dumps(session_data))

        new_token, expires_at = self._encode_token(session_id, new_jti)
        return new_token, session_id, expires_at

    async def revoke_token(self, token: str) -> None:
        """Explicitly revoke a JWT (e.g. on player kick)."""
        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
            jti = payload.get("jti", "")
            exp = payload.get("exp", 0)
            ttl = max(int(exp - datetime.now(tz=timezone.utc).timestamp()), 1)
            if jti:
                redis = await self._get_redis()
                await redis.setex(f"revoked_jti:{jti}", ttl, "1")
        except JWTError:
            pass  # token already invalid
