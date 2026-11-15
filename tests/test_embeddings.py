from app.embeddings import generate_embedding


def test_generate_embedding_returns_vector_with_expected_length():
    embedding = generate_embedding("food delivery promotion", dimensions=64)
    assert len(embedding) == 64
    assert all(isinstance(value, float) for value in embedding)
