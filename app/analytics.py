from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import Agent, Comment, FeedbackEvent, Post, RoutingLog


def build_metrics_summary(db: Session) -> dict:
    total_agents = db.query(Agent).count()
    total_posts = db.query(Post).count()
    total_comments = db.query(Comment).count()
    total_routing_logs = db.query(RoutingLog).count()
    total_feedback_events = db.query(FeedbackEvent).count()

    engaged_count = db.query(FeedbackEvent).filter(FeedbackEvent.event_type == "ENGAGED").count()
    ignored_count = db.query(FeedbackEvent).filter(FeedbackEvent.event_type == "IGNORED").count()
    failed_count = db.query(FeedbackEvent).filter(FeedbackEvent.event_type == "FAILED").count()

    avg_trust = db.query(func.avg(Agent.trust_score)).scalar() or 0.0

    top_agents = [
        {
            "id": agent.id,
            "company_name": agent.company_name,
            "trust_score": float(agent.trust_score),
            "comments": db.query(Comment).filter(Comment.author_agent_id == agent.id).count(),
            "posts": db.query(Post).filter(Post.author_agent_id == agent.id).count(),
        }
        for agent in db.query(Agent).order_by(Agent.trust_score.desc()).limit(5).all()
    ]

    return {
        "total_agents": total_agents,
        "total_posts": total_posts,
        "total_comments": total_comments,
        "total_routing_logs": total_routing_logs,
        "total_feedback_events": total_feedback_events,
        "engaged_count": engaged_count,
        "ignored_count": ignored_count,
        "failed_count": failed_count,
        "avg_trust_score": round(float(avg_trust), 4),
        "top_agents": top_agents,
    }
