"""
Generic dataset preprocessing/quality utilities shared by dataset validation
and the generic analysis engine (gene_expression, differential_expression,
dataset_quality, statistical_analysis analysis types).
"""
from typing import Any

import numpy as np
import pandas as pd


def compute_dataframe_metadata(df: pd.DataFrame) -> dict[str, Any]:
    dtypes = {col: str(dtype) for col, dtype in df.dtypes.items()}
    missing_values = {col: int(df[col].isna().sum()) for col in df.columns}

    numeric_df = df.select_dtypes(include=[np.number])
    basic_statistics: dict[str, Any] = {}
    if not numeric_df.empty:
        desc = numeric_df.describe().to_dict()
        basic_statistics = {col: {k: (None if pd.isna(v) else round(float(v), 6)) for k, v in stats.items()} for col, stats in desc.items()}

    columns = [
        {
            "name": col,
            "dtype": dtypes[col],
            "missing_count": missing_values[col],
            "missing_ratio": round(missing_values[col] / len(df), 4) if len(df) else 0.0,
            "unique_count": int(df[col].nunique(dropna=True)),
        }
        for col in df.columns
    ]

    return {
        "row_count": int(len(df)),
        "column_count": int(len(df.columns)),
        "columns": columns,
        "missing_values": missing_values,
        "dtypes": dtypes,
        "basic_statistics": basic_statistics,
        "quality_score": compute_quality_score(df),
    }


def compute_quality_score(df: pd.DataFrame) -> float:
    """A simple, transparent 0-1 quality heuristic: completeness + uniqueness + non-degeneracy."""
    if df.empty:
        return 0.0

    completeness = 1 - (df.isna().sum().sum() / (df.shape[0] * df.shape[1]))

    dup_ratio = df.duplicated().sum() / len(df) if len(df) else 0
    uniqueness = 1 - dup_ratio

    constant_cols = sum(1 for col in df.columns if df[col].nunique(dropna=True) <= 1)
    non_degeneracy = 1 - (constant_cols / len(df.columns)) if len(df.columns) else 1

    score = 0.5 * completeness + 0.25 * uniqueness + 0.25 * non_degeneracy
    return round(max(0.0, min(1.0, float(score))), 4)


def clean_numeric_frame(df: pd.DataFrame) -> pd.DataFrame:
    """Coerce to numeric, drop all-NaN columns, and median-impute remaining gaps."""
    numeric_df = df.apply(pd.to_numeric, errors="coerce")
    numeric_df = numeric_df.dropna(axis=1, how="all")
    if numeric_df.empty:
        return numeric_df
    return numeric_df.fillna(numeric_df.median(numeric_only=True))


def differential_expression(df: pd.DataFrame, group_a_cols: list[str], group_b_cols: list[str]) -> pd.DataFrame:
    """Simple two-sample comparison (mean difference + Welch's t-test) per row/gene."""
    from scipy import stats as scipy_stats

    a = df[group_a_cols].apply(pd.to_numeric, errors="coerce")
    b = df[group_b_cols].apply(pd.to_numeric, errors="coerce")

    mean_a = a.mean(axis=1)
    mean_b = b.mean(axis=1)
    log2fc = np.log2((mean_b + 1e-9) / (mean_a + 1e-9))

    t_stats, p_values = scipy_stats.ttest_ind(b, a, axis=1, equal_var=False, nan_policy="omit")

    result = pd.DataFrame({
        "mean_group_a": mean_a,
        "mean_group_b": mean_b,
        "log2_fold_change": log2fc,
        "t_statistic": t_stats,
        "p_value": p_values,
    })
    result["significant"] = (result["p_value"] < 0.05) & (result["log2_fold_change"].abs() > 1)
    return result
