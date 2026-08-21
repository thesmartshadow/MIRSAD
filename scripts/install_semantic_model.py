from __future__ import annotations

from pathlib import Path
from time import perf_counter

MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
CACHE = Path("data/models")


def main() -> None:
    try:
        from fastembed import TextEmbedding
    except ImportError as error:
        raise SystemExit(
            "FAIL: optional semantic dependencies are missing; install .[semantic] first"
        ) from error
    CACHE.mkdir(parents=True, exist_ok=True)
    started = perf_counter()
    model = TextEmbedding(model_name=MODEL, cache_dir=str(CACHE), threads=4)
    vector = next(model.query_embed("MIRSAD semantic readiness"))
    elapsed_ms = (perf_counter() - started) * 1000
    print(f"PASS: {MODEL}")
    print(f"cache: {CACHE.resolve()}")
    print(f"dimensions: {len(vector)}")
    print(f"initialization_ms: {elapsed_ms:.2f}")


if __name__ == "__main__":
    main()
