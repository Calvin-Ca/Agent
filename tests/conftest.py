"""Pytest configuration and shared fixtures."""
# conftest.py 是 pytest 的“约定文件名”,pytest 会在运行时自动扫描并加载它
# 自动识别所有 async 测试函数，并给它们加上 @pytest.mark.asyncio 标记
# 执行流程
# pytest 收集所有测试函数
# 进入 pytest_collection_modifyitems
# 遍历每个 test function：
# 如果是 async function
# 并且没有 @pytest.mark.asyncio
# 自动帮它加上：@pytest.mark.asyncio

from __future__ import annotations

import pytest


# Tell pytest-asyncio to auto-detect async test functions，也是 pytest 的“约定式 hook（钩子函数）”
def pytest_collection_modifyitems(items):   # items是一个测试用例对象列表
    """Mark all async test functions with pytest.mark.asyncio."""
    for item in items:
        if item.get_closest_marker("asyncio") is None:
            if hasattr(item, "function") and asyncio_iscoroutinefunction(item.function):
                item.add_marker(pytest.mark.asyncio)


def asyncio_iscoroutinefunction(func) -> bool:
    import asyncio
    return asyncio.iscoroutinefunction(func)  # coroutine 协程
