"""
系统主入口（EWS 版）。
使用 exchangelib 通过 EWS 协议监听收件箱，替代 Playwright 浏览器自动化。

特性：
- 纯 API 调用，无需浏览器，延迟从分钟级降到秒级
- 支持自动回复 / 人工审核两种模式
- Ctrl+C 优雅退出

运行方式：python main.py
"""
import os
import signal
import sys
from loguru import logger
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.executors.pool import ThreadPoolExecutor

from config.loader import Config
from utils.logger_setup import setup_logger
from monitor.inbox_checker import InboxChecker
from db.models import Mailbox
from db.connection import DBPool
from ewser.connection import EWSConnection

# 全局状态
_scheduler = None
_shutting_down = False


def connect_ews() -> bool:
    """建立 EWS 连接。"""
    cfg = Config()
    ews_cfg = cfg.get("ews")

    if not ews_cfg:
        logger.error("未配置 EWS 连接信息，请在 config.yaml 中添加 ews 节")
        return False

    email = ews_cfg.get("email")
    password = ews_cfg.get("password")
    server = ews_cfg.get("server")

    if not all([email, password, server]):
        logger.error("EWS 配置不完整: email/password/server 不能为空")
        return False

    try:
        conn = EWSConnection()
        conn.connect(email, password, server)
        logger.info("EWS 连接已建立")
        return True
    except Exception as e:
        logger.error(f"EWS 连接失败: {e}")
        return False


def check_inbox_job():
    """定时任务：检查收件箱并处理新邮件。"""
    global _shutting_down

    if _shutting_down:
        return

    try:
        conn = EWSConnection()
        mailboxes = Mailbox.get_active()
        if not mailboxes:
            logger.warning("没有启用的邮箱配置，请检查 mailbox 表")
            return

        for mailbox in mailboxes:
            if _shutting_down:
                return
            try:
                checker = InboxChecker(conn.account, mailbox)
                checker.run()
            except Exception as e:
                logger.error(f"邮箱 {mailbox['email']} 处理异常: {e}")

    except Exception as e:
        logger.error(f"检查任务异常: {e}")


def cleanup(signum=None, frame=None):
    """清理资源，优雅退出。"""
    global _shutting_down
    if _shutting_down:
        os._exit(1)
    _shutting_down = True

    logger.info("正在关闭系统...")

    try:
        if _scheduler is not None:
            _scheduler.shutdown(wait=False)
            logger.info("调度器已停止")
    except Exception:
        pass

    try:
        EWSConnection().disconnect()
    except Exception:
        pass

    try:
        DBPool.close_pool()
        logger.info("数据库连接池已关闭")
    except Exception:
        pass

    logger.info("系统已关闭")
    os._exit(0)


def main():
    global _scheduler

    setup_logger()
    logger.info("=" * 50)
    logger.info("  邮箱自动回复系统 v2.0 (EWS 版)")
    logger.info("=" * 50)

    # 注册信号处理
    signal.signal(signal.SIGINT, cleanup)
    signal.signal(signal.SIGTERM, cleanup)

    # 连接 EWS
    if not connect_ews():
        logger.error("EWS 连接失败，系统退出")
        cleanup()
        return

    # 配置定时任务
    scheduler_cfg = Config().get("scheduler")

    _scheduler = BlockingScheduler(
        executors={"default": ThreadPoolExecutor(max_workers=2)},
        job_defaults={
            "coalesce": scheduler_cfg.get("coalesce", True),
            "max_instances": scheduler_cfg.get("max_instances", 1),
        },
    )

    interval_seconds = scheduler_cfg.get("interval_seconds", 10)
    _scheduler.add_job(
        check_inbox_job,
        "interval",
        seconds=interval_seconds,
        id="check_inbox",
    )

    logger.info(
        f"定时任务已启动，收件箱检查间隔 {interval_seconds} 秒"
    )
    logger.info(
        f"监控邮箱: {Config().get('ews', 'email')}"
    )

    try:
        # 启动前先执行一次
        logger.info("执行首次检查...")
        check_inbox_job()

        _scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        cleanup()


if __name__ == "__main__":
    main()
