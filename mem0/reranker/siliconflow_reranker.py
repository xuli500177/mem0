import logging
from typing import Any, Dict, List, Union

import httpx

from mem0.configs.rerankers.base import BaseRerankerConfig
from mem0.configs.rerankers.siliconflow import SiliconFlowRerankerConfig
from mem0.reranker.base import BaseReranker

logger = logging.getLogger(__name__)


class SiliconFlowReranker(BaseReranker):
    """SiliconFlow API-based reranker implementation."""

    def __init__(self, config: Union[BaseRerankerConfig, SiliconFlowRerankerConfig, Dict]):
        if isinstance(config, dict):
            config = SiliconFlowRerankerConfig(**config)
        elif isinstance(config, BaseRerankerConfig) and not isinstance(config, SiliconFlowRerankerConfig):
            config = SiliconFlowRerankerConfig(
                provider=getattr(config, "provider", "siliconflow"),
                model=getattr(config, "model", "BAAI/bge-reranker-v2-m3"),
                api_key=getattr(config, "api_key", None),
                top_k=getattr(config, "top_k", None),
                base_url=getattr(config, "base_url", "https://api.siliconflow.cn/v1"),
            )
        self.config = config
        if not self.config.api_key:
            raise ValueError("SiliconFlow reranker requires an api_key")

    def rerank(self, query: str, documents: List[Dict[str, Any]], top_k: int = None) -> List[Dict[str, Any]]:
        if not documents:
            return documents

        doc_texts = []
        for doc in documents:
            if "memory" in doc:
                doc_texts.append(doc["memory"])
            elif "text" in doc:
                doc_texts.append(doc["text"])
            elif "content" in doc:
                doc_texts.append(doc["content"])
            else:
                doc_texts.append(str(doc))

        try:
            url = f"{self.config.base_url}/rerank"
            payload = {
                "query": query,
                "documents": doc_texts,
                "model": self.config.model,
                "return_documents": False,
            }
            headers = {
                "Authorization": f"Bearer {self.config.api_key}",
                "Content-Type": "application/json",
            }

            with httpx.Client(timeout=30) as client:
                resp = client.post(url, json=payload, headers=headers)
                resp.raise_for_status()
                data = resp.json()

            results = data.get("results", [])

            # Map index -> score
            score_map = {}
            for r in results:
                idx = r.get("index", 0)
                score = r.get("relevance_score", 0.0)
                score_map[idx] = float(score)

            # Normalize if requested
            if self.config.normalize and score_map:
                scores = list(score_map.values())
                min_s, max_s = min(scores), max(scores)
                rng = max_s - min_s
                if rng > 0:
                    score_map = {k: (v - min_s) / rng for k, v in score_map.items()}

            # Build reranked list
            doc_score_pairs = []
            for i, doc in enumerate(documents):
                reranked_doc = doc.copy()
                reranked_doc["rerank_score"] = score_map.get(i, 0.0)
                doc_score_pairs.append((reranked_doc, reranked_doc["rerank_score"]))

            doc_score_pairs.sort(key=lambda x: x[1], reverse=True)

            final_top_k = top_k or self.config.top_k
            if final_top_k:
                doc_score_pairs = doc_score_pairs[:final_top_k]

            return [doc for doc, _ in doc_score_pairs]

        except Exception as e:
            logger.warning(f"SiliconFlow reranker failed: {e}")
            for doc in documents:
                doc["rerank_score"] = 0.0
            final_top_k = top_k or self.config.top_k
            return documents[:final_top_k] if final_top_k else documents
