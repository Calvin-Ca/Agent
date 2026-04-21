"""Seed documents into the long-term memory store."""

from __future__ import annotations

from pathlib import Path


def main() -> None:
    docs = list(Path("question").glob("**/*"))
    count = len([doc for doc in docs if doc.is_file()])
    print(f"Seed knowledge placeholder: discovered {count} source files under ./question")


if __name__ == "__main__":
    main()

