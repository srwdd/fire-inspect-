"""独立的 Okapi BM25 检索基线（纯标准库实现）。

存在意义：检索评测需要一个公平的外部基线。旧评测里的 naive/dense/hybrid
"基线"都是 rule_retriever 的开关组合（同一系统降配），会结构性抬高主方法
的相对优势。本实现不复用 rule_retriever 的任何打分逻辑。

用法：
    from app.services.bm25_baseline import BM25Baseline
    bm25 = BM25Baseline()
    hits = bm25.search("疏散通道被占用违反哪条", top_k=5)
"""
from __future__ import annotations

import json
import math
import re
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.core.config import settings


def _tokenize(text: str) -> List[str]:
    """英文按词、中文按单字 + 二元组（CJK bigram 是中文检索的标准做法）。"""
    text = (text or "").lower()
    tokens = re.findall(r"[a-z0-9]+", text)
    cjk = re.findall(r"[一-鿿]", text)
    tokens.extend(cjk)
    tokens.extend(a + b for a, b in zip(cjk, cjk[1:]))
    return tokens


def _rule_text(rule: Dict[str, Any]) -> str:
    """检索文本。与 rule_retriever 一样故意不含 rule id（防金标泄漏）。"""
    parts = [
        str(rule.get("source", "")),
        str(rule.get("article", "")),
        str(rule.get("title", "")),
        str(rule.get("text", "")),
        str(rule.get("hazard_type", "")),
        " ".join(rule.get("tags") if isinstance(rule.get("tags"), list) else []),
        " ".join(rule.get("scene") if isinstance(rule.get("scene"), list) else []),
    ]
    return " ".join(parts)


class BM25Baseline:
    """Okapi BM25，k1=1.5, b=0.75（常规默认值）。"""

    def __init__(self, rules_path: Optional[Path] = None, k1: float = 1.5, b: float = 0.75):
        path = Path(rules_path) if rules_path else settings.RULES_FILE
        raw = json.loads(path.read_text(encoding="utf-8"))
        self.rules: List[Dict[str, Any]] = raw.get("rules", []) if isinstance(raw, dict) else list(raw)
        if not self.rules:
            raise ValueError(f"no rules loaded from {path}")
        self.k1 = k1
        self.b = b
        self.doc_tokens = [_tokenize(_rule_text(r)) for r in self.rules]
        self.doc_len = [len(t) for t in self.doc_tokens]
        self.avgdl = (sum(self.doc_len) / len(self.doc_len)) if self.doc_len else 1.0
        df: Counter = Counter()
        for tokens in self.doc_tokens:
            for token in set(tokens):
                df[token] += 1
        n = len(self.doc_tokens)
        self.idf = {t: math.log(1 + (n - c + 0.5) / (c + 0.5)) for t, c in df.items()}
        self.tf = [Counter(tokens) for tokens in self.doc_tokens]

    def search(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        q_tokens = _tokenize(query)
        scored = []
        for idx, tf in enumerate(self.tf):
            score = 0.0
            for token in q_tokens:
                f = tf.get(token)
                if not f:
                    continue
                denom = f + self.k1 * (1 - self.b + self.b * self.doc_len[idx] / self.avgdl)
                score += self.idf.get(token, 0.0) * f * (self.k1 + 1) / denom
            if score > 0:
                scored.append((score, idx))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [
            {"id": str(self.rules[idx].get("id", "")), "score": round(score, 4)}
            for score, idx in scored[:top_k]
        ]
