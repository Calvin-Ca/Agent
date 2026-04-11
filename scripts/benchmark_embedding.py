#!/usr/bin/env python3
"""Benchmark embedding throughput and latency.

Usage:
    python scripts/benchmark_embedding.py
    python scripts/benchmark_embedding.py --chunks 50 --batch-size 16
"""

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--chunks", type=int, default=20, help="Number of test chunks")
    parser.add_argument("--batch-size", type=int, default=32, help="Batch size for embedding")
    args = parser.parse_args()

    from app.config import get_settings
    from app.pipeline.embedder import embed_texts

    settings = get_settings()
    print(f"Model: {settings.ollama_embed_model}")
    print(f"Ollama: {settings.ollama_base_url}")
    print(f"Chunks: {args.chunks}, Batch size: {args.batch_size}")
    print()

    # Generate test texts (realistic lengths)
    test_texts = [
        f"这是第{i+1}段测试文本。本周项目整体进度达到{60+i}%，"
        f"主体结构施工已完成第{i%5+1}层浇筑，钢筋绑扎和模板安装同步推进。"
        f"现场共投入作业人员{30+i*2}人，塔吊{i%3+1}台，混凝土泵车{i%2+1}台。"
        f"本周累计完成混凝土浇筑{100+i*50}立方米。"
        for i in range(args.chunks)
    ]

    avg_chars = sum(len(t) for t in test_texts) / len(test_texts)
    print(f"Average chunk length: {avg_chars:.0f} chars")

    # Warmup
    print("Warming up...")
    embed_texts(test_texts[:1], batch_size=1)

    # Benchmark
    print(f"Running benchmark ({args.chunks} chunks)...")
    start = time.perf_counter()
    embeddings = embed_texts(test_texts, batch_size=args.batch_size)
    elapsed = time.perf_counter() - start

    # Results
    dim = len(embeddings[0]) if embeddings else 0
    throughput = args.chunks / elapsed

    print(f"\nResults:")
    print(f"  Time:       {elapsed:.2f}s")
    print(f"  Throughput: {throughput:.1f} chunks/sec")
    print(f"  Latency:    {elapsed/args.chunks*1000:.1f} ms/chunk")
    print(f"  Dimension:  {dim}")
    print(f"  Batch size: {args.batch_size}")

    # Sanity check
    if dim != settings.milvus_dim:
        print(f"\n  ⚠ WARNING: embedding dim ({dim}) != milvus_dim ({settings.milvus_dim})")
        print(f"    Update MILVUS_DIM in .env to {dim}")
    else:
        print(f"\n  ✓ Dimension matches Milvus config")


if __name__ == "__main__":
    main()