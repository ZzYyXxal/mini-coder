"""权限服务 - 管理命令执行授权"""

import uuid
import time
from dataclasses import dataclass, field
from typing import Optional, Callable, Dict, Set
from collections import defaultdict


@dataclass
class PermissionRequest:
    """权限请求

    Attributes:
        id: 请求唯一 ID
        session_id: 会话 ID
        command: 请求的命令
        description: 请求描述
        timestamp: 请求时间戳
    """
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    session_id: str = ""
    command: str = ""
    description: str = ""
    timestamp: float = field(default_factory=time.time)


class PermissionService:
    """权限服务

    管理命令执行的授权机制，支持：
    - 会话级权限缓存
    - 自动批准模式
    - 权限请求回调
    - 权限超时
    """

    def __init__(
        self,
        on_request_callback: Optional[Callable[[PermissionRequest], bool]] = None,
        cache_ttl: int = 3600,
    ):
        """初始化权限服务

        Args:
            on_request_callback: 权限请求回调函数，接收 PermissionRequest 返回 bool
            cache_ttl: 权限缓存超时时间 (秒)，默认 1 小时
        """
        self._on_request_callback = on_request_callback
        self._cache_ttl = cache_ttl

        # 会话级权限缓存 {session_id: {command: timestamp}}
        self._granted: Dict[str, Dict[str, float]] = defaultdict(dict)

        # 待处理请求 {request_id: PermissionRequest}
        self._pending: Dict[str, PermissionRequest] = {}

        # 自动批准会话列表
        self._auto_approve_sessions: Set[str] = set()

    def request(
        self,
        session_id: str,
        command: str,
        description: Optional[str] = None
    ) -> bool:
        """请求执行权限

        Args:
            session_id: 会话 ID
            command: 请求的命令
            description: 可选的描述信息

        Returns:
            bool: 是否批准
        """
        # 检查是否在自动批准会话中
        if session_id in self._auto_approve_sessions:
            return True

        # 检查缓存中是否有已授权的权限
        if self._is_cached(session_id, command):
            return True

        # 创建权限请求
        request = PermissionRequest(
            session_id=session_id,
            command=command,
            description=description or f"执行命令：{command}"
        )

        # 保存到待处理列表
        self._pending[request.id] = request

        # 调用回调函数
        if self._on_request_callback:
            try:
                approved = self._on_request_callback(request)
                if approved:
                    self.grant(request.id, session_id, command)
                return approved
            except Exception:
                # 回调异常，默认拒绝
                return False

        # 没有回调函数，默认拒绝
        return False

    def grant(
        self,
        request_id: str,
        session_id: str,
        command: str
    ) -> None:
        """授予权限

        Args:
            request_id: 请求 ID
            session_id: 会话 ID
            command: 命令
        """
        # 添加到缓存
        self._granted[session_id][command] = time.time()

        # 从待处理列表移除
        if request_id in self._pending:
            del self._pending[request_id]

    def grant_persistent(
        self,
        session_id: str,
        command: str
    ) -> None:
        """持久授予权限 (会话内缓存)

        Args:
            session_id: 会话 ID
            command: 命令
        """
        self._granted[session_id][command] = time.time()

    def revoke(
        self,
        session_id: str,
        command: str
    ) -> bool:
        """撤销权限

        Args:
            session_id: 会话 ID
            command: 命令

        Returns:
            bool: 是否成功撤销
        """
        if session_id in self._granted and command in self._granted[session_id]:
            del self._granted[session_id][command]
            return True
        return False

    def revoke_all(self, session_id: str) -> None:
        """撤销会话的所有权限

        Args:
            session_id: 会话 ID
        """
        if session_id in self._granted:
            del self._granted[session_id]

    def auto_approve_session(self, session_id: str) -> None:
        """设置会话为自动批准模式

        Args:
            session_id: 会话 ID
        """
        self._auto_approve_sessions.add(session_id)

    def remove_auto_approve(self, session_id: str) -> None:
        """移除自动批准会话

        Args:
            session_id: 会话 ID
        """
        self._auto_approve_sessions.discard(session_id)

    def is_auto_approved(self, session_id: str) -> bool:
        """检查会话是否为自动批准模式

        Args:
            session_id: 会话 ID

        Returns:
            bool: 是否为自动批准模式
        """
        return session_id in self._auto_approve_sessions

    def _is_cached(self, session_id: str, command: str) -> bool:
        """检查命令是否在缓存中且未超时

        Args:
            session_id: 会话 ID
            command: 命令

        Returns:
            bool: 是否在缓存中且有效
        """
        if session_id not in self._granted:
            return False

        if command not in self._granted[session_id]:
            return False

        # 检查是否超时
        timestamp = self._granted[session_id][command]
        if time.time() - timestamp > self._cache_ttl:
            # 超时，移除缓存
            del self._granted[session_id][command]
            return False

        return True

    def get_pending_requests(self, session_id: Optional[str] = None) -> list[PermissionRequest]:
        """获取待处理请求列表

        Args:
            session_id: 可选的会话 ID 过滤

        Returns:
            list[PermissionRequest]: 待处理请求列表
        """
        if session_id is None:
            return list(self._pending.values())
        return [
            req for req in self._pending.values()
            if req.session_id == session_id
        ]

    def get_granted_commands(self, session_id: str) -> list[str]:
        """获取会话已授权的命令列表

        Args:
            session_id: 会话 ID

        Returns:
            list[str]: 已授权命令列表
        """
        if session_id not in self._granted:
            return []

        # 清理超时的命令
        self._cleanup_cache(session_id)

        return list(self._granted[session_id].keys())

    def _cleanup_cache(self, session_id: str) -> None:
        """清理会话超时的缓存

        Args:
            session_id: 会话 ID
        """
        if session_id not in self._granted:
            return

        current_time = time.time()
        expired_commands = [
            cmd for cmd, ts in self._granted[session_id].items()
            if current_time - ts > self._cache_ttl
        ]

        for cmd in expired_commands:
            del self._granted[session_id][cmd]

    def get_stats(self) -> dict:
        """获取权限服务统计信息

        Returns:
            dict: 统计信息
        """
        total_granted = sum(len(cmds) for cmds in self._granted.values())
        return {
            "total_granted": total_granted,
            "pending_requests": len(self._pending),
            "auto_approve_sessions": len(self._auto_approve_sessions),
            "active_sessions": len(self._granted),
        }
