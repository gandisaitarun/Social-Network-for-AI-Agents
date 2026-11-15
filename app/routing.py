import re

from sqlalchemy.orm import Session

from app.embeddings import cosine_similarity, generate_embedding
from app.models import Agent, FeedbackEvent, Post, RoutingLog


def normalize_text(value: str) -> str:
    return re.sub(r"[^a-z0-9\s]", " ", (value or "").lower())


def build_embedding(text: str, dimensions: int | None = None) -> list[float]:
    return generate_embedding(text, dimensions=dimensions)


def group_tokens(text: str) -> set[str]:
    alias_map = {
        "food": "food",
        "foods": "food",
        "delivery": "delivery",
        "deliveries": "delivery",
        "restaurant": "restaurant",
        "restaurants": "restaurant",
        "promo": "promotion",
        "promos": "promotion",
        "promotion": "promotion",
        "promotions": "promotion",
        "discount": "discount",
        "discounts": "discount",
        "cashback": "cashback",
        "upi": "upi",
        "payment": "payment",
        "payments": "payment",
        "commerce": "commerce",
        "ecommerce": "commerce",
        "festival": "festival",
        "diwali": "festival",
        "partner": "partnership",
        "partners": "partnership",
        "partnership": "partnership",
        "partnerships": "partnership",
    }

    tokens = set(normalize_text(text).split())
    mapped = set()
    for token in tokens:
        mapped.add(alias_map.get(token, token))
    return mapped


def score_match(post_text: str, agent_manifesto: str) -> tuple[float, float]:
    post_vector = build_embedding(post_text)
    agent_vector = build_embedding(agent_manifesto)
    vector_score = cosine_similarity(post_vector, agent_vector)

    post_groups = group_tokens(post_text)
    agent_groups = group_tokens(agent_manifesto)
    semantic_overlap = len(post_groups & agent_groups) / max(len(post_groups | agent_groups), 1)
    rerank_score = min(1.0, max(0.0, vector_score + semantic_overlap))
    return vector_score, rerank_score


def agent_feedback_multiplier(db: Session, agent_id: str) -> float:
    history = db.query(FeedbackEvent).filter(FeedbackEvent.agent_id == agent_id).all()
    if not history:
        return 1.0

    engaged = sum(1 for event in history if event.event_type == "ENGAGED")
    ignored = sum(1 for event in history if event.event_type == "IGNORED")
    total = len(history)
    engagement_rate = engaged / total
    ignore_rate = ignored / total
    return max(0.25, min(1.5, 1.0 + (engagement_rate * 0.5) - (ignore_rate * 0.75)))


def route_post_for_agent(db: Session, post: Post, top_k: int = 5, threshold: float = 0.22) -> list[dict]:
    decisions: list[dict] = []

    for agent in db.query(Agent).filter(Agent.id != post.author_agent_id).all():
        vector_score, rerank_score = score_match(f"{post.title} {post.content}", agent.interest_manifesto)
        feedback_multiplier = agent_feedback_multiplier(db, agent.id)
        adjusted_score = min(1.0, rerank_score * feedback_multiplier * max(agent.trust_score, 0.1))

        if adjusted_score < threshold:
            continue

        decisions.append({
            "agent_id": agent.id,
            "company_name": agent.company_name,
            "vector_score": round(vector_score, 4),
            "rerank_score": round(adjusted_score, 4),
            "status": "NOTIFIED",
        })

        db.add(
            RoutingLog(
                post_id=post.id,
                target_agent_id=agent.id,
                vector_score=vector_score,
                rerank_score=adjusted_score,
                status="NOTIFIED",
            )
        )

    decisions.sort(key=lambda item: item["rerank_score"], reverse=True)
    db.commit()
    return decisions[:top_k]
