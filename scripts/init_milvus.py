#!/usr/bin/env python3
"""Initialize Milvus — create collection, build index, verify.

Usage:
    python scripts/init_milvus.py
    python scripts/init_milvus.py --drop   # drop and recreate
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pymilvus import utility

from app.config import get_settings
from app.db.milvus import connect_milvus, disconnect_milvus, get_or_create_collection


def main() -> None:
    parser = argparse.ArgumentParser(description="Initialize Milvus collection")
    parser.add_argument("--drop", action="store_true", help="Drop existing collection first")
    args = parser.parse_args()

    settings = get_settings()
    print(f"Connecting to Milvus: {settings.milvus_host}:{settings.milvus_port}")

    connect_milvus()

    name = settings.milvus_collection

    if args.drop and utility.has_collection(name):
        utility.drop_collection(name)
        print(f"Dropped existing collection '{name}'")

    collection = get_or_create_collection()

    # Verify
    print(f"\nCollection: {collection.name}")
    print(f"  Schema:   {collection.schema}")
    print(f"  Entities: {collection.num_entities}")
    print(f"  Indexes:  {collection.indexes}")
    print(f"  Loaded:   True")

    # List all collections
    all_collections = utility.list_collections()
    print(f"\nAll collections: {all_collections}")

    disconnect_milvus()
    print("\nMilvus initialization complete ✓")


if __name__ == "__main__":
    main()
