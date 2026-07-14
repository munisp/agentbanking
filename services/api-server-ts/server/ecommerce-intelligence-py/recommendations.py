"""
Product Recommendation Engine
- Collaborative filtering (user-item matrix)
- Item-item similarity
- Trending detection
- Interaction recording for model training
"""

import logging
import time
from collections import defaultdict
from typing import Any

import numpy as np

logger = logging.getLogger("recommendations")


class RecommendationEngine:
    def __init__(self, db_url: str, redis_url: str):
        self.db_url = db_url
        self.redis_url = redis_url
        # In-memory interaction matrix for cold start
        self.interactions: dict[int, dict[int, float]] = defaultdict(lambda: defaultdict(float))
        self.product_features: dict[int, dict[str, Any]] = {}
        self.trending_cache: list[dict] = []
        self.trending_cache_time: float = 0

    def get_for_customer(self, customer_id: int, limit: int = 10) -> list[dict]:
        """Get personalized recommendations using collaborative filtering."""
        customer_prefs = self.interactions.get(customer_id, {})

        if not customer_prefs:
            # Cold start: return trending products
            return self.get_trending(0, limit)

        # Find similar customers (cosine similarity)
        scores: dict[int, float] = defaultdict(float)
        customer_vec = customer_prefs

        for other_id, other_prefs in self.interactions.items():
            if other_id == customer_id:
                continue

            similarity = self._cosine_similarity(customer_vec, other_prefs)
            if similarity <= 0:
                continue

            # Weight unseen products by similarity
            for product_id, rating in other_prefs.items():
                if product_id not in customer_prefs:
                    scores[product_id] += similarity * rating

        # Sort by score and return top-N
        ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:limit]
        return [
            {
                "productId": pid,
                "score": round(score, 4),
                "reason": "collaborative_filtering",
            }
            for pid, score in ranked
        ]

    def get_similar_products(self, product_id: int, limit: int = 8) -> list[dict]:
        """Item-item collaborative filtering — find products bought by similar users."""
        # Find all customers who interacted with this product
        buyers = [
            cid
            for cid, prefs in self.interactions.items()
            if product_id in prefs
        ]

        if not buyers:
            return []

        # Count co-occurrence
        cooccurrence: dict[int, int] = defaultdict(int)
        for cid in buyers:
            for other_pid in self.interactions[cid]:
                if other_pid != product_id:
                    cooccurrence[other_pid] += 1

        ranked = sorted(cooccurrence.items(), key=lambda x: x[1], reverse=True)[:limit]
        return [
            {
                "productId": pid,
                "cooccurrence": count,
                "confidence": round(count / max(len(buyers), 1), 4),
                "reason": "item_similarity",
            }
            for pid, count in ranked
        ]

    def get_trending(self, category_id: int, limit: int = 20) -> list[dict]:
        """Return trending products based on recent interaction volume."""
        now = time.time()
        # Cache trending for 5 minutes
        if now - self.trending_cache_time < 300 and self.trending_cache:
            results = self.trending_cache
            if category_id > 0:
                results = [r for r in results if r.get("categoryId") == category_id]
            return results[:limit]

        # Aggregate recent interactions
        product_scores: dict[int, float] = defaultdict(float)
        for _, prefs in self.interactions.items():
            for pid, score in prefs.items():
                product_scores[pid] += score

        ranked = sorted(product_scores.items(), key=lambda x: x[1], reverse=True)[:100]
        self.trending_cache = [
            {
                "productId": pid,
                "trendScore": round(score, 2),
                "categoryId": self.product_features.get(pid, {}).get("categoryId", 0),
                "reason": "trending",
            }
            for pid, score in ranked
        ]
        self.trending_cache_time = now

        results = self.trending_cache
        if category_id > 0:
            results = [r for r in results if r.get("categoryId") == category_id]
        return results[:limit]

    def record_interaction(
        self,
        customer_id: int,
        product_id: int,
        interaction_type: str = "view",
        metadata: dict | None = None,
    ):
        """Record customer-product interaction for model training."""
        weight_map = {
            "view": 1.0,
            "add_to_cart": 3.0,
            "purchase": 5.0,
            "review": 4.0,
            "wishlist": 2.0,
        }
        weight = weight_map.get(interaction_type, 1.0)
        self.interactions[customer_id][product_id] += weight

        if metadata and "categoryId" in metadata:
            self.product_features[product_id] = metadata

    def _cosine_similarity(self, vec_a: dict[int, float], vec_b: dict[int, float]) -> float:
        """Compute cosine similarity between two sparse vectors."""
        common_keys = set(vec_a.keys()) & set(vec_b.keys())
        if not common_keys:
            return 0.0

        a_vals = np.array([vec_a[k] for k in common_keys])
        b_vals = np.array([vec_b[k] for k in common_keys])

        dot = np.dot(a_vals, b_vals)
        norm_a = np.linalg.norm(a_vals)
        norm_b = np.linalg.norm(b_vals)

        if norm_a == 0 or norm_b == 0:
            return 0.0

        return float(dot / (norm_a * norm_b))
