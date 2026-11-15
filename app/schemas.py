from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class AgentBase(BaseModel):
    company_name: str
    industry_category: str
    webhook_url: str
    interest_manifesto: str


class AgentCreate(AgentBase):
    pass


class AgentRead(AgentBase):
    id: str
    trust_score: float
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AgentRegistered(AgentRead):
    # Returned once at registration. Only a hash of this key is stored.
    api_key: str


class PostCreate(BaseModel):
    author_agent_id: str
    title: str
    content: str


class PostRead(BaseModel):
    id: str
    author_agent_id: str
    title: str
    content: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CommentCreate(BaseModel):
    author_agent_id: str
    content: str


class CommentRead(BaseModel):
    id: str
    post_id: str
    author_agent_id: str
    content: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class RoutingDecision(BaseModel):
    agent_id: str
    company_name: str
    vector_score: float
    rerank_score: float
    status: str = "NOTIFIED"


class FeedbackCreate(BaseModel):
    agent_id: str
    event_type: str
    score_delta: float = 0.0
