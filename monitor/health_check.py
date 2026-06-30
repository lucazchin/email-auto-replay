"""
系统健康检查：监控登录态文件新鲜度，管理暂停/恢复。
"""
import os
from loguru import logger


class HealthChecker:
    _state_file_mtime = None
    _paused = False

    @classmethod
    def check_state_freshness(cls, state_file: str) -> bool:
        """
        检查 state.json 是否存在且近期被更新。
        人工重新登录后 state.json 的 mtime 会变化，此时自动恢复监控。
        """
        if not os.path.exists(state_file):
            return False

        current_mtime = os.path.getmtime(state_file)
        if cls._state_file_mtime is None:
            cls._state_file_mtime = current_mtime
            return True

        if current_mtime != cls._state_file_mtime:
            cls._state_file_mtime = current_mtime
            cls._paused = False
            logger.info("检测到 state.json 已更新，恢复监控")
            return True

        return not cls._paused

    @classmethod
    def pause(cls, reason: str):
        """暂停监控并发送告警。"""
        cls._paused = True
        logger.error(f"监控已暂停，原因: {reason}")
        # TODO: 集成告警通知（webhook 等）

    @classmethod
    def is_paused(cls) -> bool:
        return cls._paused
