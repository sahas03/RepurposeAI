"""
Model interface every AI/ML component implements.

Keeping a narrow, stable interface (fit / predict / metadata) means the
scikit-learn baselines used today (RandomForest, GradientBoosting,
LogisticRegression) can be swapped for XGBoost, PyTorch, or graph neural
network implementations later without touching calling code.
"""
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any

import numpy as np


class BaseModel(ABC):
    model_name: str = "base_model"
    model_version: str = "1.0.0"

    def __init__(self, random_state: int = 42):
        self.random_state = random_state
        self.is_fitted: bool = False
        self.trained_at: datetime | None = None

    @abstractmethod
    def fit(self, X: np.ndarray, y: np.ndarray) -> "BaseModel":
        ...

    @abstractmethod
    def predict(self, X: np.ndarray) -> np.ndarray:
        ...

    def metadata(self) -> dict[str, Any]:
        return {
            "model_name": self.model_name,
            "model_version": self.model_version,
            "is_fitted": self.is_fitted,
            "trained_at": self.trained_at.isoformat() if self.trained_at else None,
        }

    def _mark_fitted(self) -> None:
        self.is_fitted = True
        self.trained_at = datetime.now(timezone.utc)
