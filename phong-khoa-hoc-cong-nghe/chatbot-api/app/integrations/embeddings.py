from __future__ import annotations

import hashlib
import logging
import math
import threading

log = logging.getLogger(__name__)

_bge_model = None
_bge_lock = threading.Lock()
BGE_BATCH = 2
BGE_MAX_LENGTH = 512


def hash_embed(texts: list[str], dim: int = 1024, on_batch=None) -> list[list[float]]:
    """Vector ổn định cho test / khi chưa tải BGE-M3."""
    out: list[list[float]] = []
    total = len(texts)
    for index, text in enumerate(texts, start=1):
        seed = hashlib.sha256((text or "").encode("utf-8")).digest()
        raw: list[float] = []
        while len(raw) < dim:
            seed = hashlib.sha256(seed).digest()
            raw.extend((b / 127.5) - 1.0 for b in seed)
        vec = raw[:dim]
        norm = math.sqrt(sum(x * x for x in vec)) or 1.0
        out.append([x / norm for x in vec])
        if on_batch:
            on_batch(index, total)
    return out


def _l2(vec: list[float]) -> list[float]:
    norm = math.sqrt(sum(x * x for x in vec)) or 1.0
    return [x / norm for x in vec]


def warmup_embedder(backend: str, dim: int = 1024) -> None:
    kind = (backend or "hash").strip().lower()
    if kind not in {"bge", "bge-m3", "bge_m3"}:
        return
    try:
        embed_texts(["warmup"], dim=dim, backend=kind)
        log.info("BGE-M3 warmup done")
    except Exception as exc:  # noqa: BLE001
        log.warning("BGE-M3 warmup failed: %s", exc)


def bge_embed(texts: list[str], dim: int = 1024, on_batch=None) -> list[list[float]]:
    global _bge_model
    with _bge_lock:
        if _bge_model is None:
            from FlagEmbedding import BGEM3FlagModel

            log.info("Loading BGE-M3 dense embedder (batch=%s, max_length=%s)", BGE_BATCH, BGE_MAX_LENGTH)
            print(
                f"embed: loading BAAI/bge-m3 CPU batch={BGE_BATCH} max_length={BGE_MAX_LENGTH}",
                flush=True,
            )
            _bge_model = BGEM3FlagModel(
                "BAAI/bge-m3",
                use_fp16=False,
                devices="cpu",
                batch_size=BGE_BATCH,
                query_max_length=BGE_MAX_LENGTH,
                passage_max_length=BGE_MAX_LENGTH,
            )
            print("embed: model ready", flush=True)
        out: list[list[float]] = []
        total = len(texts)
        for start in range(0, total, BGE_BATCH):
            batch = texts[start : start + BGE_BATCH]
            end = start + len(batch)
            print(f"embed: {end}/{total}", flush=True)
            packed = _bge_model.encode(
                batch,
                batch_size=len(batch),
                max_length=BGE_MAX_LENGTH,
                return_dense=True,
                return_sparse=False,
                return_colbert_vecs=False,
            )
            for row in packed["dense_vecs"]:
                vec = [float(x) for x in row[:dim]]
                if len(vec) < dim:
                    vec.extend([0.0] * (dim - len(vec)))
                out.append(_l2(vec))
            if on_batch:
                on_batch(end, total)
        return out


def embed_texts(texts: list[str], dim: int = 1024, backend: str = "hash", on_batch=None) -> list[list[float]]:
    if not texts:
        return []
    kind = (backend or "hash").strip().lower()
    if kind in {"bge", "bge-m3", "bge_m3"}:
        return bge_embed(texts, dim=dim, on_batch=on_batch)
    return hash_embed(texts, dim=dim, on_batch=on_batch)
