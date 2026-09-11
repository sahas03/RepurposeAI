"""
DrugRepurposingModel: combines a handcrafted evidence score with a scikit-learn
classifier that learns how to weight the engineered features.

No real-world labeled drug-disease outcome dataset is bundled with this
repository (that would require a licensed/proprietary source). Instead, at
first use the model calibrates itself on a synthetic, clearly-labeled bootstrap
sample whose labels are a noisy function of the same evidence features
(more gene overlap + more/stronger supporting interactions => more likely
"positive"). This lets the platform demonstrate a real, fit/predict-based
ML component end-to-end. Swap `_bootstrap_training_data` for a loader over a
real labeled dataset (e.g. validated repurposing outcomes) to make this
production-grade without touching any calling code - the BaseModel interface
does not change.
"""
import numpy as np
from sklearn.ensemble import RandomForestClassifier

from app.ai.feature_engineering.feature_engineering import RepurposingFeatures
from app.ai.models.base import BaseModel
from app.core.config import settings


class DrugRepurposingModel(BaseModel):
    model_name = "drug_repurposing_random_forest"
    model_version = settings.ML_MODEL_VERSION

    def __init__(self, random_state: int = settings.ML_RANDOM_STATE):
        super().__init__(random_state=random_state)
        self.classifier = RandomForestClassifier(
            n_estimators=200,
            max_depth=6,
            min_samples_leaf=3,
            random_state=random_state,
        )

    def fit(self, X: np.ndarray, y: np.ndarray) -> "DrugRepurposingModel":
        self.classifier.fit(X, y)
        self._mark_fitted()
        return self

    def predict(self, X: np.ndarray) -> np.ndarray:
        if not self.is_fitted:
            raise RuntimeError("DrugRepurposingModel must be fit before predict()")
        return self.classifier.predict_proba(X)[:, 1]

    def feature_importances(self) -> dict[str, float]:
        if not self.is_fitted:
            return {}
        return dict(zip(RepurposingFeatures.feature_names(), self.classifier.feature_importances_.tolist()))

    @classmethod
    def bootstrap_trained(cls, random_state: int = settings.ML_RANDOM_STATE, n_samples: int = 1500) -> "DrugRepurposingModel":
        """Build and fit a model on a synthetic, clearly-labeled bootstrap sample."""
        rng = np.random.default_rng(random_state)
        gene_overlap_ratio = rng.beta(2, 5, n_samples)
        gene_overlap_count = (gene_overlap_ratio * rng.integers(1, 20, n_samples)).round()
        target_count = rng.integers(0, 15, n_samples)
        evidence_count = rng.poisson(2, n_samples)
        evidence_mean_confidence = rng.beta(2, 2, n_samples)
        compound_similarity_score = rng.beta(2, 3, n_samples)
        known_target_interaction_score = np.clip(evidence_mean_confidence * (evidence_count / 3), 0, 1)

        X = np.column_stack([
            gene_overlap_count, gene_overlap_ratio, target_count,
            evidence_count, evidence_mean_confidence,
            compound_similarity_score, known_target_interaction_score,
        ])

        signal = (
            0.35 * gene_overlap_ratio
            + 0.25 * evidence_mean_confidence
            + 0.2 * known_target_interaction_score
            + 0.2 * compound_similarity_score
        )
        noise = rng.normal(0, 0.12, n_samples)
        probability = np.clip(signal + noise, 0, 1)
        y = rng.binomial(1, probability)

        model = cls(random_state=random_state)
        model.fit(X, y)
        return model


_cached_model: DrugRepurposingModel | None = None


def get_repurposing_model() -> DrugRepurposingModel:
    """Process-local singleton: train once per worker/API process, reuse after."""
    global _cached_model
    if _cached_model is None:
        _cached_model = DrugRepurposingModel.bootstrap_trained()
    return _cached_model
