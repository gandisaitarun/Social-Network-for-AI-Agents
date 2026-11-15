import hashlib
import math
import os
import re
from collections import Counter

try:
    from openai import OpenAI
except ImportError:  # pragma: no cover - optional dependency for real embeddings
    OpenAI = None


def normalize_text(value: str) -> str:
    return re.sub(r"[^a-z0-9\s]", " ", (value or "").lower())


def hash_embedding(text: str, dimensions: int = 64) -> list[float]:
    tokens = [token for token in normalize_text(text).split() if token]
    if not tokens:
        return [0.0 for _ in range(dimensions)]

    counts = Counter(tokens)
    vector = [0.0 for _ in range(dimensions)]
    for token, count in counts.items():
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        index = int.from_bytes(digest[:4], byteorder="big", signed=False) % dimensions
        vector[index] += count

    norm = math.sqrt(sum(value * value for value in vector))
    if norm == 0:
        return vector
    return [value / norm for value in vector]


def validate_embedding(embedding: list[float], expected_dimensions: int | None = None) -> list[float]:
    if not embedding:
        return [0.0 for _ in range(expected_dimensions or 0)]

    if expected_dimensions is not None and len(embedding) < expected_dimensions:
        embedding = list(embedding) + [0.0 for _ in range(expected_dimensions - len(embedding))]
    if expected_dimensions is not None and len(embedding) > expected_dimensions:
        embedding = embedding[:expected_dimensions]
    return embedding


def generate_embedding(text: str, dimensions: int | None = None) -> list[float]:
    target_dimensions = dimensions or int(os.getenv("EMBEDDING_DIMENSION", "64"))

    api_key = os.getenv("OPENAI_API_KEY")
    if OpenAI is not None and api_key:
        try:
            client = OpenAI(api_key=api_key)
            model = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")
            response = client.embeddings.create(model=model, input=text)
            embedding = response.data[0].embedding
            return validate_embedding(embedding, target_dimensions)
        except Exception:
            pass

    return hash_embedding(text, dimensions=target_dimensions)


def cosine_similarity(left: list[float], right: list[float]) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0

    dot = sum(a * b for a, b in zip(left, right))
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if left_norm == 0 or right_norm == 0:
        return 0.0

    return max(0.0, min(1.0, dot / (left_norm * right_norm)))
