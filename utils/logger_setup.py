"""
日志系统配置：使用 loguru，按级别分文件输出。
"""
import sys
from pathlib import Path
from loguru import logger
from config.loader import Config


def setup_logger():
    """初始化日志系统。"""
    cfg = Config().get("logging")
    log_dir = Path(cfg.get("dir", "logs"))
    log_dir.mkdir(parents=True, exist_ok=True)

    # 清除默认 handler
    logger.remove()

    # 控制台输出
    logger.add(
        sys.stdout,
        level=cfg.get("level", "INFO"),
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
               "<level>{level: <8}</level> | "
               "<cyan>{module}</cyan>:<cyan>{line}</cyan> - "
               "<level>{message}</level>",
        colorize=True,
    )

    # 全量日志文件
    logger.add(
        str(log_dir / "app_{time:YYYY-MM-DD}.log"),
        level=cfg.get("level", "INFO"),
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {module}:{line} - {message}",
        rotation=cfg.get("rotation", "10 MB"),
        retention=cfg.get("retention", "30 days"),
        encoding="utf-8",
    )

    # 错误日志单独文件
    logger.add(
        str(log_dir / "error_{time:YYYY-MM-DD}.log"),
        level="ERROR",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {module}:{line} - {message}",
        rotation="10 MB",
        retention="30 days",
        encoding="utf-8",
    )

    logger.info("日志系统初始化完成")
