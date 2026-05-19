from typing import Optional
from pydantic import Field

from mem0.configs.rerankers.base import BaseRerankerConfig


class SiliconFlowRerankerConfig(BaseRerankerConfig):
    """Configuration for SiliconFlow reranker API."""

    model: Optional[str] = Field(
        default="BAAI/bge-reranker-v2-m3",
        description="SiliconFlow reranker model name",
    )
    base_url: str = Field(
        default="https://api.siliconflow.cn/v1",
        description="SiliconFlow API base URL",
    )
    normalize: bool = Field(default=True, description="Whether to normalize scores to [0, 1]")
    min_relevance: float = Field(
        default=0.1,
        description="Absolute raw score threshold. Results below this are discarded before normalization to prevent irrelevant results from being inflated to 1.0.",
    )
