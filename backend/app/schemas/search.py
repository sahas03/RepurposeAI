from typing import Any

from pydantic import BaseModel


class SearchResults(BaseModel):
    query: str
    results: dict[str, list[dict[str, Any]]]
    total_results: int
