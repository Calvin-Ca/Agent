"""Unit tests for the text chunker."""

from __future__ import annotations

from app.perception.chunker import chunk_text, Chunk


class TestChunker:

    def test_empty_text(self):
        assert chunk_text("") == []
        assert chunk_text("   ") == []

    def test_short_text_single_chunk(self):
        text = "这是一段很短的文本。"
        chunks = chunk_text(text, chunk_size=500)
        assert len(chunks) == 1
        assert chunks[0].text == text
        assert chunks[0].index == 0

    def test_splits_long_text(self):
        text = "这是第一段内容。\n\n这是第二段内容。\n\n这是第三段内容。" * 20
        chunks = chunk_text(text, chunk_size=100, chunk_overlap=20)
        assert len(chunks) > 1
        # All chunks should have content
        for c in chunks:
            assert len(c.text) > 0

    def test_overlap_applied(self):
        text = "A" * 200 + "\n\n" + "B" * 200 + "\n\n" + "C" * 200
        chunks = chunk_text(text, chunk_size=250, chunk_overlap=50)
        # Second chunk should start with tail of first chunk
        if len(chunks) >= 2:
            assert len(chunks[1].text) > 50

    def test_respects_min_chunk_size(self):
        text = "短。\n\n这是一段正常长度的文本内容，用来测试最小分块长度过滤。"
        chunks = chunk_text(text, chunk_size=100, min_chunk_size=10)
        for c in chunks:
            assert c.char_count >= 10

    def test_chinese_separators(self):
        text = "第一句话。第二句话。第三句话。第四句话。第五句话。" * 10
        chunks = chunk_text(text, chunk_size=50)
        assert len(chunks) > 1

    def test_indices_sequential(self):
        text = "内容段落。\n\n" * 50
        chunks = chunk_text(text, chunk_size=100)
        for i, c in enumerate(chunks):
            assert c.index == i

    def test_chunk_dataclass(self):
        c = Chunk(index=0, text="hello", char_count=5)
        assert c.index == 0
        assert c.text == "hello"
        assert c.char_count == 5