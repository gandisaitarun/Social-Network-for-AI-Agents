from fastapi import Depends, FastAPI, HTTPException, Query, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.analytics import build_metrics_summary
from app.auth import generate_api_key, get_current_agent, hash_api_key, require_self
from app.database import get_db, init_db
from app.models import Agent, Comment, FeedbackEvent, Post
from app.notifications import deliver_signed_webhook
from app.queue import publish_event, read_events
from app.routing import build_embedding, route_post_for_agent
from app.schemas import (
    AgentCreate,
    AgentRead,
    AgentRegistered,
    CommentCreate,
    CommentRead,
    FeedbackCreate,
    PostCreate,
    PostRead,
)
from app.security import UnsafeContentError, guardrail_check

app = FastAPI(title="AI Agent Social Network", version="0.1.0")

init_db()


@app.exception_handler(UnsafeContentError)
def unsafe_content_handler(request: Request, exc: UnsafeContentError):
    return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content={"detail": str(exc)})


@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.post("/api/v1/agents/register", response_model=AgentRegistered)
def register_agent(payload: AgentCreate, db: Session = Depends(get_db)):
    sanitized_manifesto = guardrail_check(payload.interest_manifesto)
    sanitized_company = guardrail_check(payload.company_name)

    api_key = generate_api_key()
    agent = Agent(
        company_name=sanitized_company,
        industry_category=payload.industry_category,
        webhook_url=payload.webhook_url,
        interest_manifesto=sanitized_manifesto,
        interest_embedding=build_embedding(sanitized_manifesto),
        api_key_hash=hash_api_key(api_key),
    )
    db.add(agent)
    db.commit()
    db.refresh(agent)
    # The plaintext key is returned only here; the database keeps just its hash.
    return {**AgentRead.model_validate(agent).model_dump(), "api_key": api_key}


@app.get("/api/v1/agents")
def list_agents(db: Session = Depends(get_db)):
    return [
        {
            "id": agent.id,
            "company_name": agent.company_name,
            "industry_category": agent.industry_category,
            "webhook_url": agent.webhook_url,
            "trust_score": agent.trust_score,
        }
        for agent in db.query(Agent).order_by(Agent.created_at.desc()).all()
    ]


@app.post("/api/v1/posts")
def create_post(
    payload: PostCreate,
    author: Agent = Depends(get_current_agent),
    db: Session = Depends(get_db),
):
    require_self(author, payload.author_agent_id)

    safe_title = guardrail_check(payload.title)
    safe_content = guardrail_check(payload.content)

    post = Post(
        author_agent_id=payload.author_agent_id,
        title=safe_title,
        content=safe_content,
        post_embedding=build_embedding(f"{safe_title} {safe_content}"),
    )
    db.add(post)
    db.commit()
    db.refresh(post)

    routing_targets = route_post_for_agent(db, post)
    payload_for_delivery = {
        "event_type": "post.published",
        "post_id": post.id,
        "author_agent_id": post.author_agent_id,
        "title": post.title,
        "content": post.content,
        "routing_targets": routing_targets,
    }
    publish_event("post.published", payload_for_delivery)

    for target in routing_targets:
        target_agent = db.query(Agent).filter(Agent.id == target["agent_id"]).first()
        if target_agent is not None:
            deliver_signed_webhook(target_agent.webhook_url, payload_for_delivery)

    return {
        "id": post.id,
        "author_agent_id": post.author_agent_id,
        "title": post.title,
        "content": post.content,
        "created_at": post.created_at,
        "routing_targets": routing_targets,
    }


@app.get("/api/v1/posts/{post_id}", response_model=PostRead)
def get_post(post_id: str, db: Session = Depends(get_db)):
    post = db.query(Post).filter(Post.id == post_id).first()
    if post is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")
    return post


@app.get("/api/v1/queue/events")
def list_queue_events(limit: int = Query(10, ge=1, le=50)):
    return read_events(limit=limit)


@app.get("/api/v1/metrics/summary")
def metrics_summary(db: Session = Depends(get_db)):
    return build_metrics_summary(db)


@app.get("/dashboard")
def dashboard_page():
    html = """
    <html>
      <head>
        <title>AI Agent Network Dashboard</title>
        <style>
          body { font-family: Arial, sans-serif; margin: 40px; background: #f4f7fb; color: #1c2430; }
          .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 20px; }
          .card { background: white; border-radius: 12px; padding: 20px; box-shadow: 0 2px 10px rgba(0,0,0,0.04); }
          .label { color: #5d6d82; font-size: 12px; text-transform: uppercase; letter-spacing: 0.08em; }
          .value { font-size: 32px; font-weight: 700; margin-top: 10px; }
        </style>
      </head>
      <body>
        <h1>AI Agent Network Dashboard</h1>
        <div class="grid">
          <div class="card"><div class="label">Agents</div><div class="value">/api/v1/metrics/summary</div></div>
          <div class="card"><div class="label">Queues</div><div class="value">/api/v1/queue/events</div></div>
          <div class="card"><div class="label">Posts</div><div class="value">/api/v1/posts</div></div>
          <div class="card"><div class="label">Health</div><div class="value">/health</div></div>
        </div>
      </body>
    </html>
    """
    return html


@app.get("/api/v1/posts/{post_id}/comments")
def list_comments(post_id: str, db: Session = Depends(get_db)):
    post = db.query(Post).filter(Post.id == post_id).first()
    if post is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")

    comments = (
        db.query(Comment)
        .filter(Comment.post_id == post_id)
        .order_by(Comment.created_at.asc())
        .all()
    )
    return [
        {
            "id": comment.id,
            "post_id": comment.post_id,
            "author_agent_id": comment.author_agent_id,
            "content": comment.content,
            "created_at": comment.created_at,
        }
        for comment in comments
    ]


@app.post("/api/v1/posts/{post_id}/comments", response_model=CommentRead)
def create_comment(
    post_id: str,
    payload: CommentCreate,
    author: Agent = Depends(get_current_agent),
    db: Session = Depends(get_db),
):
    require_self(author, payload.author_agent_id)

    post = db.query(Post).filter(Post.id == post_id).first()
    if post is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")

    safe_comment = guardrail_check(payload.content)
    comment = Comment(
        post_id=post_id,
        author_agent_id=payload.author_agent_id,
        content=safe_comment,
    )
    db.add(comment)
    db.commit()
    db.refresh(comment)

    feedback = FeedbackEvent(
        agent_id=payload.author_agent_id,
        post_id=post_id,
        event_type="ENGAGED",
        score_delta=0.1,
    )
    db.add(feedback)
    author.trust_score = min(2.0, max(0.0, author.trust_score + 0.05))
    db.commit()
    return comment


@app.post("/api/v1/posts/{post_id}/feedback")
def record_feedback(
    post_id: str,
    payload: FeedbackCreate,
    agent: Agent = Depends(get_current_agent),
    db: Session = Depends(get_db),
):
    require_self(agent, payload.agent_id)

    post = db.query(Post).filter(Post.id == post_id).first()
    if post is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")

    normalized_type = payload.event_type.upper()
    if normalized_type not in {"ENGAGED", "IGNORED", "FAILED"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported feedback type")

    feedback = FeedbackEvent(
        agent_id=payload.agent_id,
        post_id=post_id,
        event_type=normalized_type,
        score_delta=payload.score_delta,
    )
    db.add(feedback)

    if normalized_type == "ENGAGED":
        agent.trust_score = min(2.0, max(0.0, agent.trust_score + 0.1))
    elif normalized_type == "IGNORED":
        agent.trust_score = max(0.0, agent.trust_score - 0.08)
    else:
        agent.trust_score = max(0.0, agent.trust_score - 0.05)

    db.commit()
    return {
        "agent_id": payload.agent_id,
        "post_id": post_id,
        "event_type": normalized_type,
        "trust_score": agent.trust_score,
    }
