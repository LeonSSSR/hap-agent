from __future__ import annotations

import json
import math
import re
from collections import Counter
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any
from uuid import uuid4


def _utc_now() -> str:
  return datetime.now(timezone.utc).isoformat()


# 领域同义词：把“意思相近但用词不同”的表达归并到同一规范标签，
# 在索引与检索两端对称扩展，提升 TF-IDF 召回（无需 embedding/外部依赖）。
_SYNONYM_PHRASES: dict[str, str] = {
  "部署": "syn_deploy", "上线": "syn_deploy", "deploy": "syn_deploy",
  "训练": "syn_train", "training": "syn_train", "train": "syn_train",
  "数据集": "syn_dataset", "数据版本": "syn_dataset", "dataset": "syn_dataset",
  "血缘": "syn_lineage", "上下游": "syn_lineage", "依赖链": "syn_lineage", "lineage": "syn_lineage",
  "漂移": "syn_drift", "drift": "syn_drift",
  "质量": "syn_quality", "quality": "syn_quality",
  "模型": "syn_model", "model": "syn_model",
  "发布": "syn_publish", "publish": "syn_publish",
  "推理": "syn_inference", "inference": "syn_inference", "predict": "syn_inference",
  "监控": "syn_monitor", "monitor": "syn_monitor", "monitoring": "syn_monitor",
  "治理": "syn_gov", "governance": "syn_gov",
  "任务": "syn_task", "job": "syn_task", "pipeline": "syn_task",
  "注册": "syn_register", "register": "syn_register",
  "评估": "syn_eval", "evaluation": "syn_eval", "evaluate": "syn_eval",
  "服务": "syn_service", "service": "syn_service",
}


def _tokenize(text: str) -> list[str]:
  normalized = str(text or "").lower().strip()
  if not normalized:
    return []
  tokens: list[str] = []
  # 注意：用 + 捕获连续 CJK 串（旧实现按单字匹配导致只切单字、bigram 形同虚设）。
  for chunk in re.findall(r"[a-z0-9]+|[\u4e00-\u9fff]+", normalized):
    if re.fullmatch(r"[\u4e00-\u9fff]+", chunk):
      # 单字保召回，2-gram 抓词组，整词提精度。
      for char in chunk:
        tokens.append(char)
      if len(chunk) >= 2:
        for index in range(len(chunk) - 1):
          tokens.append(chunk[index : index + 2])
        tokens.append(chunk)
    else:
      tokens.append(chunk)
  # 同义词短语扩展（子串命中即追加规范标签）。
  for phrase, canonical in _SYNONYM_PHRASES.items():
    if phrase in normalized:
      tokens.append(canonical)
  return tokens


class TextVectorIndex:
  """Lightweight TF-IDF cosine index without external ML dependencies."""

  def __init__(self) -> None:
    self._documents: list[dict[str, Any]] = []
    self._idf: dict[str, float] = {}

  def _rebuild_idf(self) -> None:
    doc_count = len(self._documents)
    if doc_count == 0:
      self._idf = {}
      return
    df: Counter[str] = Counter()
    for document in self._documents:
      terms = set(document.get("tokens") or [])
      for term in terms:
        df[term] += 1
    self._idf = {term: math.log((1 + doc_count) / (1 + count)) + 1.0 for term, count in df.items()}

  def _vectorize(self, tokens: list[str]) -> dict[str, float]:
    counts = Counter(tokens)
    total = float(sum(counts.values()) or 1.0)
    vector: dict[str, float] = {}
    for term, count in counts.items():
      tf = count / total
      vector[term] = tf * self._idf.get(term, 1.0)
    return vector

  @staticmethod
  def _cosine(left: dict[str, float], right: dict[str, float]) -> float:
    if not left or not right:
      return 0.0
    common = set(left) & set(right)
    dot = sum(left[term] * right[term] for term in common)
    left_norm = math.sqrt(sum(value * value for value in left.values()))
    right_norm = math.sqrt(sum(value * value for value in right.values()))
    if left_norm == 0 or right_norm == 0:
      return 0.0
    return dot / (left_norm * right_norm)

  def add(self, *, memory_id: str, text: str, metadata: dict[str, Any]) -> None:
    tokens = _tokenize(text)
    self._documents.append({"memory_id": memory_id, "text": text, "tokens": tokens, "metadata": metadata})
    self._rebuild_idf()

  def load_records(self, records: list[dict[str, Any]]) -> None:
    self._documents = []
    for record in records:
      text = str(record.get("text") or "")
      tokens = _tokenize(text)
      self._documents.append(
        {
          "memory_id": str(record.get("memory_id") or ""),
          "text": text,
          "tokens": tokens,
          "metadata": record.get("metadata") if isinstance(record.get("metadata"), dict) else {},
        }
      )
    self._rebuild_idf()

  def search(self, query: str, *, limit: int = 5, exclude_session_id: str | None = None, username: str | None = None) -> list[dict[str, Any]]:
    query_tokens = _tokenize(query)
    if not query_tokens or not self._documents:
      return []
    query_vector = self._vectorize(query_tokens)
    owner_filter = str(username or "").strip()
    scored: list[tuple[float, str, dict[str, Any]]] = []
    for document in self._documents:
      metadata = document.get("metadata") if isinstance(document.get("metadata"), dict) else {}
      if exclude_session_id and str(metadata.get("session_id") or "") == exclude_session_id:
        continue
      if owner_filter and str(metadata.get("username") or "").strip() != owner_filter:
        continue
      doc_vector = self._vectorize(list(document.get("tokens") or []))
      score = self._cosine(query_vector, doc_vector)
      if score <= 0:
        continue
      created_at = str(metadata.get("created_at") or "")
      scored.append((score, created_at, document))
    # 先按相关度，再按近因（ISO 时间串可直接字典序比较）排序，平分时新记忆优先。
    scored.sort(key=lambda item: (item[0], item[1]), reverse=True)
    results: list[dict[str, Any]] = []
    for score, _created_at, document in scored[: max(1, limit)]:
      metadata = document.get("metadata") if isinstance(document.get("metadata"), dict) else {}
      results.append(
        {
          "memory_id": document.get("memory_id"),
          "text": document.get("text"),
          "score": round(score, 4),
          "session_id": metadata.get("session_id"),
          "plan_id": metadata.get("plan_id"),
          "skill_id": metadata.get("skill_id"),
          "created_at": metadata.get("created_at"),
        }
      )
    return results


class LongTermMemoryStore:
  """Cross-session L3 memory backed by JSONL + local vector search."""

  def __init__(self, base_path: str | None = None, *, search_limit: int = 5) -> None:
    self._records: list[dict[str, Any]] = []
    self._index = TextVectorIndex()
    self._lock = Lock()
    self._search_limit = max(1, search_limit)
    self._base_path = Path(base_path) if base_path else None
    if self._base_path is not None:
      self._base_path.mkdir(parents=True, exist_ok=True)
      self._load_from_disk()

  @property
  def enabled(self) -> bool:
    return self._base_path is not None

  def _memories_file(self) -> Path:
    assert self._base_path is not None
    return self._base_path / "memories.jsonl"

  def _load_from_disk(self) -> None:
    path = self._memories_file()
    if not path.exists():
      return
    records: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
      for line in handle:
        raw = line.strip()
        if not raw:
          continue
        try:
          parsed = json.loads(raw)
        except json.JSONDecodeError:
          continue
        if isinstance(parsed, dict) and parsed.get("memory_id"):
          records.append(parsed)
    with self._lock:
      self._records = records
      self._index.load_records(records)

  def _append_record(self, record: dict[str, Any]) -> None:
    with self._lock:
      self._records.append(record)
      self._index.add(
        memory_id=str(record["memory_id"]),
        text=str(record.get("text") or ""),
        metadata=record.get("metadata") if isinstance(record.get("metadata"), dict) else {},
      )
    if self._base_path is not None:
      line = json.dumps(record, ensure_ascii=False, sort_keys=True)
      with self._lock:
        with self._memories_file().open("a", encoding="utf-8") as handle:
          handle.write(line + "\n")

  def index_turn(
    self,
    *,
    session_id: str,
    user_input: str,
    assistant_reply: str,
    skill_id: str | None = None,
    plan_id: str | None = None,
    username: str | None = None,
  ) -> dict[str, Any] | None:
    text = f"用户: {user_input.strip()}\n助手: {assistant_reply.strip()}".strip()
    if not text:
      return None
    truncated_text = text[:2000]
    # 写入去重：完全相同的问答不重复入库，避免索引被重复内容灌满、稀释 IDF。
    with self._lock:
      for existing in self._records:
        if str(existing.get("text") or "") == truncated_text:
          return None
    memory_id = f"mem-{uuid4().hex[:12]}"
    created_at = _utc_now()
    record = {
      "memory_id": memory_id,
      "text": truncated_text,
      "metadata": {
        "session_id": session_id,
        "plan_id": plan_id,
        "skill_id": skill_id,
        "created_at": created_at,
        "username": str(username or "").strip() or None,
      },
    }
    self._append_record(record)
    return deepcopy(record)

  def search(
    self,
    query: str,
    *,
    limit: int | None = None,
    exclude_session_id: str | None = None,
    username: str | None = None,
  ) -> list[dict[str, Any]]:
    with self._lock:
      return self._index.search(
        query,
        limit=limit or self._search_limit,
        exclude_session_id=exclude_session_id,
        username=username,
      )


from config import settings

_memory_base_path = settings.session_store_path.strip() if settings.session_store_path else None
long_term_memory = LongTermMemoryStore(
  base_path=_memory_base_path,
  search_limit=settings.long_term_memory_search_limit,
)
