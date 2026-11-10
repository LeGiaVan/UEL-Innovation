from __future__ import annotations

import hashlib
from typing import Any, Protocol

from app.gold.models import EmbeddedText
from app.gold.policy import BGE_M3_DENSE_DIM
from app.ingestion.exceptions import IngestionError

HASH_DENSE_DIM = 8


class Embedder(Protocol):
    model_name: str
    dense_dim: int

    def embed(self, texts: list[str]) -> list[EmbeddedText]:
        raise NotImplementedError


class HashEmbedder:
    """Deterministic stand-in used in tests; not for production retrieval."""

    model_name = "hash-test"
    dense_dim = HASH_DENSE_DIM

    def embed(self, texts: list[str]) -> list[EmbeddedText]:
        return [_hash_embedding(text, self.dense_dim) for text in texts]


class BgeM3Embedder:
    model_name = "BAAI/bge-m3"
    dense_dim = BGE_M3_DENSE_DIM

    def __init__(
        self,
        model_name: str = "BAAI/bge-m3",
        *,
        batch_size: int = 2,
        max_length: int = 512,
    ) -> None:
        self.model_name = model_name
        self._batch_size = batch_size
        self._max_length = max_length
        self._model: Any = None

    def _load(self) -> Any:
        if self._model is None:
            try:
                from FlagEmbedding import BGEM3FlagModel  # type: ignore[import-untyped]
            except ImportError as exc:
                raise IngestionError(
                    "BGE-M3 requires the gold extra: pip install -e '.[gold]'"
                ) from exc
            import logging

            for logger_name in (
                "httpx",
                "httpcore",
                "huggingface_hub",
                "huggingface_hub.utils",
                "huggingface_hub.file_download",
            ):
                logging.getLogger(logger_name).setLevel(logging.ERROR)
            print(
                f"gold: loading {self.model_name} on CPU "
                f"(batch_size={self._batch_size}; first load can take several minutes)...",
                flush=True,
            )
            self._model = BGEM3FlagModel(
                self.model_name,
                use_fp16=False,
                devices="cpu",
                batch_size=self._batch_size,
                query_max_length=self._max_length,
                passage_max_length=self._max_length,
                return_dense=True,
                return_sparse=True,
                return_colbert_vecs=False,
            )
            print("gold: model ready", flush=True)
        return self._model

    def embed(self, texts: list[str]) -> list[EmbeddedText]:
        if not texts:
            return []
        model = self._load()
        results: list[EmbeddedText] = []
        total = len(texts)
        for start in range(0, total, self._batch_size):
            batch = texts[start : start + self._batch_size]
            end = start + len(batch)
            print(f"gold: embedding {end}/{total}", flush=True)
            output = model.encode(
                batch,
                batch_size=len(batch),
                max_length=self._max_length,
                return_dense=True,
                return_sparse=True,
                return_colbert_vecs=False,
            )
            dense_rows = output["dense_vecs"]
            sparse_rows = output["lexical_weights"]
            for dense, weights in zip(dense_rows, sparse_rows, strict=True):
                indices, values = _sparse_from_weights(weights)
                results.append(
                    EmbeddedText(
                        dense=[float(value) for value in dense],
                        sparse_indices=indices,
                        sparse_values=values,
                    )
                )
        return results


def load_embedder(
    model_name: str,
    *,
    batch_size: int = 2,
    max_length: int = 512,
) -> Embedder:
    if model_name == "hash-test":
        return HashEmbedder()
    return BgeM3Embedder(model_name, batch_size=batch_size, max_length=max_length)


def _hash_embedding(text: str, dim: int) -> EmbeddedText:
    digest = hashlib.sha256(text.encode("utf-8")).digest()
    dense = [((digest[index % len(digest)] / 127.5) - 1.0) for index in range(dim)]
    norm = sum(value * value for value in dense) ** 0.5 or 1.0
    dense = [value / norm for value in dense]
    seen: dict[int, float] = {}
    for token in text.casefold().split():
        index = int(hashlib.sha256(token.encode("utf-8")).hexdigest()[:8], 16) % 30000
        seen[index] = seen.get(index, 0.0) + 1.0
    indices = sorted(seen)
    values = [seen[index] for index in indices]
    if not indices:
        indices, values = [0], [0.0]
    return EmbeddedText(
        dense=dense,
        sparse_indices=indices,
        sparse_values=values,
    )


def _sparse_from_weights(
    weights: dict[str, float] | dict[int, float],
) -> tuple[list[int], list[float]]:
    pairs: list[tuple[int, float]] = []
    for key, value in weights.items():
        index = int(key)
        pairs.append((index, float(value)))
    pairs.sort(key=lambda item: item[0])
    return [item[0] for item in pairs], [item[1] for item in pairs]
