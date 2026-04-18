"""Tool: MinIO video query — scan entire bucket, find latest video by filename."""

from __future__ import annotations

from pathlib import Path

from loguru import logger

from app.tools.base import BaseTool, ToolResult
from app.db import minio as minio_db

_VIDEO_EXTS = {".mp4", ".avi", ".mov", ".mkv", ".wmv", ".flv", ".webm"}


def _is_video(name: str) -> bool:
    return Path(name).suffix.lower() in _VIDEO_EXTS


class GetLatestVideoTool(BaseTool):
    """扫描 MinIO 整个 bucket，找出文件名最新的视频（适用时间戳命名）。"""

    @property
    def name(self) -> str:
        return "minio.get_latest_video"

    @property
    def description(self) -> str:
        return "扫描 MinIO bucket 所有目录，找出文件名最新的视频文件，返回元信息和预签名下载链接"

    def execute(self, **kwargs) -> ToolResult:
        """
        无需任何参数，自动扫描整个 bucket。

        Returns:
            ToolResult.data = {
                "filename": str,
                "object_key": str,       # 含完整路径
                "size": int,             # bytes
                "last_modified": str,    # ISO 8601
                "presigned_url": str,    # 1 小时有效
                "total_videos": int,     # bucket 内视频总数
            } or None if no video found
        """
        try:
            # 不传 prefix，recursive=True，扫描整个 bucket
            objects = minio_db.list_objects(prefix="", recursive=True)
            videos = [obj for obj in objects if _is_video(obj.object_name)]

            if not videos:
                logger.info("No videos found in bucket")
                return ToolResult(
                    success=True,
                    data=None,
                    metadata={"message": "MinIO bucket 中未找到任何视频文件"},
                )

            # 按文件名（不含路径）降序排序，文件名为时间戳时即得到最新文件
            videos.sort(key=lambda o: Path(o.object_name).name, reverse=True)
            latest = videos[0]

            url = minio_db.presigned_get_url(latest.object_name, expires_seconds=3600)

            data = {
                "filename": Path(latest.object_name).name,
                "object_key": latest.object_name,
                "size": latest.size,
                "last_modified": latest.last_modified.isoformat() if latest.last_modified else "",
                "presigned_url": url,
                "total_videos": len(videos),
            }
            logger.info(
                "Latest video: {} ({} bytes), total={}",
                latest.object_name, latest.size, len(videos),
            )
            return ToolResult(success=True, data=data)

        except Exception as e:
            logger.error("GetLatestVideoTool failed: {}", e)
            return ToolResult(success=False, error=str(e))
