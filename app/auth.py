import hashlib
import secrets

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Agent

AGENT_KEY_HEADER = "X-Agent-Key"


def generate_api_key() -> str:
    return secrets.token_urlsafe(32)


def hash_api_key(api_key: str) -> str:
    return hashlib.sha256(api_key.encode("utf-8")).hexdigest()


def get_current_agent(
    x_agent_key: str | None = Header(default=None, alias=AGENT_KEY_HEADER),
    db: Session = Depends(get_db),
) -> Agent:
    """Resolve the agent that owns the X-Agent-Key header, or reject the request."""
    if not x_agent_key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing agent API key")

    agent = db.query(Agent).filter(Agent.api_key_hash == hash_api_key(x_agent_key)).first()
    if agent is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid agent API key")
    return agent


def require_self(agent: Agent, claimed_agent_id: str) -> None:
    """An authenticated agent may only act under its own identity."""
    if agent.id != claimed_agent_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="API key does not belong to the agent named in the request",
        )
