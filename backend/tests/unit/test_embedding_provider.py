import subprocess
import sys

from app.services.embedding_provider import HashingEmbeddingProvider, MockEmbeddingProvider
from app.services.similarity_engine import HybridSimilarityEngine


def test_mock_embedding_provider():
    provider = MockEmbeddingProvider(dim=768)
    assert provider.dimension == 768

    vec1 = provider.generate_embedding("Calculate the trajectory of a projectile.")
    assert len(vec1) == 768

    # Determinism check
    vec2 = provider.generate_embedding("Calculate the trajectory of a projectile.")
    assert vec1 == vec2

    # Batch embedding check
    batch_vecs = provider.generate_embeddings_batch(["Q1 text", "Q2 text"])
    assert len(batch_vecs) == 2
    assert len(batch_vecs[0]) == 768


def test_embeddings_are_stable_across_processes():
    # Stored vectors must stay comparable after a restart (Python's hash() is salted per process).
    code = (
        "from app.services.embedding_provider import MockEmbeddingProvider, HashingEmbeddingProvider;"
        "print(MockEmbeddingProvider().generate_embedding('abc')[0], HashingEmbeddingProvider().generate_embedding('abc')[0])"
    )
    outputs = {
        subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True).stdout
        for _ in range(2)
    }
    assert len(outputs) == 1


def test_hashing_provider_reflects_textual_similarity():
    p = HashingEmbeddingProvider()
    cos = HybridSimilarityEngine.compute_cosine_similarity
    base = p.generate_embedding("A 5 kg block is pushed with a force of 20 N. Calculate its acceleration.")
    near = p.generate_embedding("A 5 kg block is pushed with a force of 25 N. Calculate the acceleration.")
    far = p.generate_embedding("State the second law of thermodynamics.")
    assert cos(base, base) > 0.999
    assert cos(base, near) > 0.7
    assert cos(base, far) < 0.3
    assert p.model_id.startswith("hashing")
