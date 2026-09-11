"""
Generic similarity utilities backed by scikit-learn / numpy / scipy.

`SimilarityModel` is intentionally chemistry-agnostic: it works on any numeric
feature vector. app/biotech/compound_similarity.py is responsible for turning
a Compound row into the feature vector (molecular weight, formula-derived atom
counts, declared properties) that gets passed in here.
"""
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.neighbors import NearestNeighbors


class SimilarityModel:
    model_name = "similarity_model"
    model_version = "1.0.0"

    @staticmethod
    def cosine(vector_a: list[float], vector_b: list[float]) -> float:
        a = np.asarray(vector_a, dtype=float).reshape(1, -1)
        b = np.asarray(vector_b, dtype=float).reshape(1, -1)
        if not np.any(a) or not np.any(b):
            return 0.0
        return float(cosine_similarity(a, b)[0][0])

    @staticmethod
    def jaccard(set_a: set, set_b: set) -> float:
        if not set_a and not set_b:
            return 0.0
        union = set_a | set_b
        if not union:
            return 0.0
        return len(set_a & set_b) / len(union)

    @staticmethod
    def nearest_neighbors(query_vector: list[float], candidate_vectors: list[list[float]], k: int = 5) -> list[tuple[int, float]]:
        """Return [(index, distance), ...] for the k nearest candidates to query_vector."""
        if not candidate_vectors:
            return []
        X = np.asarray(candidate_vectors, dtype=float)
        k = min(k, len(candidate_vectors))
        nn = NearestNeighbors(n_neighbors=k, algorithm="auto")
        nn.fit(X)
        distances, indices = nn.kneighbors(np.asarray(query_vector, dtype=float).reshape(1, -1))
        return list(zip(indices[0].tolist(), distances[0].tolist()))
