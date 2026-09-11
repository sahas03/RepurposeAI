"""
Prediction orchestration lives in app.ai.pipeline.RepurposingPipeline (feature
scoring, ranking, explanation) and app.ai.models.repurposing (the fitted
classifier). This package is kept as an extension point for a future dedicated
prediction-serving module (e.g. batched/offline scoring) without needing to
restructure the AI layer.
"""
