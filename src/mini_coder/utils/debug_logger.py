"""
调试日志工具 - 用于诊断 Agent 间上下文传递问题

使用方法：
1. 在 orchestrator.py 中导入: from mini_coder.utils.debug_logger import DebugLogger
2. 创建实例: self._debug_logger = DebugLogger()
3. 在关键位置调用日志方法

日志文件保存在 logs/ 目录下
"""

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional


class DebugLogger:
    """调试日志器，用于诊断多 Agent 系统中的上下文传递问题"""

    def __init__(self, log_dir: str = "logs"):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.log_file = self.log_dir / f"debug_{self.session_id}.jsonl"
        self._logger = logging.getLogger("debug")

    def _write_log(self, event_type: str, data: Dict[str, Any]) -> None:
        """写入一条日志记录"""
        record = {
            "timestamp": datetime.now().isoformat(),
            "session_id": self.session_id,
            "event_type": event_type,
            "data": self._sanitize(data)
        }
        try:
            with open(self.log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
        except Exception as e:
            self._logger.warning(f"Failed to write debug log: {e}")

    def _sanitize(self, data: Any, max_len: int = 2000) -> Any:
        """清理数据，限制长度"""
        if isinstance(data, dict):
            return {k: self._sanitize(v, max_len) for k, v in data.items()}
        elif isinstance(data, list):
            return [self._sanitize(item, max_len) for item in data[:10]]
        elif isinstance(data, str):
            if len(data) > max_len:
                return data[:max_len] + f"...[truncated, total {len(data)} chars]"
            return data
        elif hasattr(data, '__dict__'):
            # 处理对象
            return f"<{type(data).__name__}: {str(data)[:100]}>"
        return data

    # ========== Blackboard 相关日志 ==========

    def log_blackboard_state(
        self,
        source: str,
        blackboard_id: Optional[str],
        context_keys: list,
        artifact_names: list,
        work_dir: Optional[str] = None
    ) -> None:
        """记录 Blackboard 状态"""
        self._write_log("blackboard_state", {
            "source": source,
            "blackboard_id": blackboard_id,
            "context_keys": context_keys,
            "artifact_names": artifact_names,
            "work_dir": work_dir,
        })

    def log_blackboard_artifact(
        self,
        source: str,
        artifact_name: str,
        content_type: str,
        content_preview: str,
        created_by: str
    ) -> None:
        """记录 Blackboard artifact 详情"""
        self._write_log("blackboard_artifact", {
            "source": source,
            "artifact_name": artifact_name,
            "content_type": content_type,
            "content_preview": content_preview[:500] if content_preview else None,
            "created_by": created_by,
        })

    # ========== Agent 派发相关日志 ==========

    def log_dispatch_start(
        self,
        intent: str,
        agent_type: str,
        context_keys: Optional[list] = None,
        has_blackboard: bool = False,
        blackboard_id: Optional[str] = None
    ) -> None:
        """记录 Agent 派发开始"""
        self._write_log("dispatch_start", {
            "intent": intent[:200] if intent else None,
            "agent_type": agent_type,
            "context_keys": context_keys or [],
            "has_blackboard": has_blackboard,
            "blackboard_id": blackboard_id,
        })

    def log_dispatch_context(
        self,
        source: str,
        dispatch_context: Dict[str, Any]
    ) -> None:
        """记录派发上下文"""
        self._write_log("dispatch_context", {
            "source": source,
            "context_keys": list(dispatch_context.keys()) if dispatch_context else [],
            "work_dir": dispatch_context.get("work_dir"),
            "bash_mode": dispatch_context.get("bash_mode"),
            "has_plan": bool(dispatch_context.get("plan")),
            "has_code": bool(dispatch_context.get("code")),
            "plan_preview": (dispatch_context.get("plan") or "")[:200],
            "code_preview": (dispatch_context.get("code") or "")[:200],
        })

    def log_agent_created(
        self,
        agent_type: str,
        agent_class: str,
        has_blackboard: bool = False,
        blackboard_id: Optional[str] = None,
        work_dir: Optional[str] = None
    ) -> None:
        """记录 Agent 创建"""
        self._write_log("agent_created", {
            "agent_type": agent_type,
            "agent_class": agent_class,
            "has_blackboard": has_blackboard,
            "blackboard_id": blackboard_id,
            "work_dir": work_dir,
        })

    def log_agent_execute(
        self,
        agent_type: str,
        task_preview: str,
        context_keys: Optional[list] = None,
        context_work_dir: Optional[str] = None,
        context_has_plan: bool = False,
        context_has_code: bool = False
    ) -> None:
        """记录 Agent 执行"""
        self._write_log("agent_execute", {
            "agent_type": agent_type,
            "task_preview": task_preview[:200] if task_preview else None,
            "context_keys": context_keys or [],
            "context_work_dir": context_work_dir,
            "context_has_plan": context_has_plan,
            "context_has_code": context_has_code,
        })

    # ========== 结果相关日志 ==========

    def log_agent_result(
        self,
        agent_type: str,
        success: bool,
        output_len: int,
        error: Optional[str] = None,
        artifact_names: Optional[list] = None
    ) -> None:
        """记录 Agent 执行结果"""
        self._write_log("agent_result", {
            "agent_type": agent_type,
            "success": success,
            "output_len": output_len,
            "error": error[:200] if error else None,
            "artifact_names": artifact_names or [],
        })

    # ========== Prompt 相关日志 ==========

    def log_prompt_dump(
        self,
        agent_type: str,
        system_prompt: str,
        user_prompt: str,
        prompt_context: Optional[Dict] = None
    ) -> None:
        """Dump prompt 到单独文件"""
        prompt_file = self.log_dir / f"prompt_{self.session_id}_{agent_type}.txt"
        try:
            content = f"""=== System Prompt ===
{system_prompt}

=== User Prompt ===
{user_prompt}

=== Prompt Context ===
{json.dumps(prompt_context, ensure_ascii=False, default=str, indent=2) if prompt_context else "None"}
"""
            with open(prompt_file, "w", encoding="utf-8") as f:
                f.write(content)
            self._write_log("prompt_dump", {
                "agent_type": agent_type,
                "file": str(prompt_file),
                "system_len": len(system_prompt) if system_prompt else 0,
                "user_len": len(user_prompt) if user_prompt else 0,
            })
        except Exception as e:
            self._logger.warning(f"Failed to dump prompt: {e}")

    # ========== GSSC 流水线日志 ==========

    def log_gssc_pipeline(
        self,
        phase: str,
        source: str,
        message_count: int,
        token_count: Optional[int] = None,
        details: Optional[Dict] = None
    ) -> None:
        """记录 GSSC 流水线状态"""
        self._write_log("gssc_pipeline", {
            "phase": phase,  # gather, select, structure, compress
            "source": source,
            "message_count": message_count,
            "token_count": token_count,
            "details": details or {},
        })


# 全局实例
_debug_logger: Optional[DebugLogger] = None


def get_debug_logger() -> DebugLogger:
    """获取全局调试日志器"""
    global _debug_logger
    if _debug_logger is None:
        _debug_logger = DebugLogger()
    return _debug_logger


def enable_debug_logging() -> DebugLogger:
    """启用调试日志"""
    global _debug_logger
    _debug_logger = DebugLogger()
    return _debug_logger