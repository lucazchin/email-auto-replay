# 邮箱自动监控与 AI 自动回复系统 — 细化技术方案 V2

> 基于 V1 需求文档，针对每个执行步骤给出可落地的细化方案，补全选择器策略、富文本输入、状态管理、错误处理、幂等性等关键缺口。

---

## 一、V1 → V2 改进总览

| 维度 | V1 状态 | V2 细化内容 |
|------|---------|-------------|
| 选择器 | 占位符 `.xxx-selector` | 基于 aria/role 的稳定选择器 + 多级回退 + 配置化 |
| 富文本输入 | `reply_box.fill()` | contenteditable 专用输入策略（click → focus → keyboard.type / evaluate） |
| mail_uid | 未说明获取方式 | URL 解析 + data-attribute 提取 + 哈希兜底 |
| 登录态过期 | 无处理 | 启动校验 + 运行时检测 + 告警通知 + 自动暂停 |
| 定时任务并发 | 无控制 | `max_instances=1` + `coalesce=True` + 分布式锁（可选） |
| 错误处理 | 基础 try/except | 分层异常体系 + 重试策略 + 熔断机制 |
| 日志 | 仅 `app.log` | 结构化日志 + 按模块分文件 + 关键事件告警 |
| HTML 正文清洗 | 无 | html2text 转纯文本 + 签名/引用剥离 |
| 配置管理 | 简单 yaml 示例 | 完整 config.yaml schema + 环境变量覆盖 + 校验 |
| 测试策略 | 无 | 单元测试 + Playwright 录制回放 + 端到端冒烟 |

---

## 二、环境搭建（详细步骤）

### 2.1 Python 虚拟环境

```bash
# 在项目根目录执行
python -m venv .venv

# Windows
.venv\Scripts\activate

# Linux/Mac
source .venv/bin/activate
```

### 2.2 依赖清单（requirements.txt）

```txt
# 浏览器自动化
playwright==1.49.0

# 定时任务
APScheduler==3.10.4

# 数据库
PyMySQL==1.1.1
dbutils==3.1.0

# AI 接口
openai==1.58.1          # DeepSeek/OpenAI/Qwen 统一用 openai SDK
requests==2.32.3        # Ollama 本地调用

# 配置与工具
PyYAML==6.0.2
html2text==2024.2.26    # HTML 邮件转纯文本
python-dotenv==1.0.1    # .env 环境变量

# 日志
loguru==0.7.3

# 测试（开发环境）
pytest==8.3.4
pytest-asyncio==0.25.0
```

### 2.3 安装 Playwright 浏览器

```bash
# 安装 Chromium 内核（约 150MB）
playwright install chromium

# Linux 额外需要系统依赖
playwright install-deps chromium
```

### 2.4 验证安装

```bash
python -c "from playwright.sync_api import sync_playwright; print('Playwright OK')"
python -c "import pymysql; print('PyMySQL OK')"
python -c "import apscheduler; print('APScheduler OK')"
```

---

## 三、配置系统设计

### 3.1 完整 config.yaml

```yaml
# ============ 数据库配置 ============
database:
  host: "127.0.0.1"
  port: 3306
  user: "root"
  password: ""              # 建议通过环境变量 DB_PASSWORD 覆盖
  database: "email_auto_reply"
  pool_size: 5              # 连接池大小
  pool_recycle: 3600        # 连接回收周期（秒）

# ============ AI 模型配置 ============
ai:
  provider: "deepseek"      # deepseek / openai / qwen / ollama
  api_key: ""               # 环境变量 AI_API_KEY 覆盖
  base_url: "https://api.deepseek.com/v1"
  model: "deepseek-chat"
  max_tokens: 1000          # 回复最大 token 数
  temperature: 0.7          # 生成温度
  timeout: 30               # API 超时（秒）
  retry_times: 3            # 失败重试次数
  retry_interval: 5         # 重试间隔（秒）

# ============ 浏览器配置 ============
browser:
  headless: false           # MVP 阶段建议 false，便于调试
  slow_mo: 100              # 操作间隔（毫秒），模拟人工节奏
  viewport:
    width: 1920
    height: 1080
  user_agent: ""            # 留空使用默认；填写可伪装特定浏览器
  timeout: 30000            # 页面操作默认超时（毫秒）

# ============ Outlook 配置 ============
outlook:
  url: "https://outlook.live.com"
  inbox_path: "/mail/0/inbox"
  state_file: "state/outlook_state.json"
  max_emails_per_run: 20    # 每次轮询最多处理邮件数
  page_load_timeout: 60000  # 页面加载超时

# ============ 定时任务配置 ============
scheduler:
  interval_minutes: 1       # 轮询间隔（分钟）
  max_instances: 1          # 最大并发实例（防重叠）
  coalesce: true            # 错过的任务合并为一次

# ============ 日志配置 ============
logging:
  level: "INFO"             # DEBUG / INFO / WARNING / ERROR
  dir: "logs"
  rotation: "10 MB"         # 日志文件大小轮转
  retention: "30 days"      # 日志保留天数

# ============ 告警配置 ============
alert:
  enabled: false
  webhook_url: ""           # 企业微信/钉钉/飞书 webhook
  notify_on:
    - "login_expired"       # 登录态过期
    - "selector_failed"     # 选择器失效
    - "send_failed"         # 发送失败
    - "ai_error"            # AI 接口异常
```

### 3.2 配置加载与校验

```python
# config/loader.py
import os
import yaml
from pathlib import Path

class Config:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._load()
        return cls._instance

    def _load(self):
        config_path = Path(__file__).parent.parent / "config.yaml"
        with open(config_path, "r", encoding="utf-8") as f:
            self._data = yaml.safe_load(f)

        # 环境变量覆盖敏感字段
        if os.getenv("DB_PASSWORD"):
            self._data["database"]["password"] = os.getenv("DB_PASSWORD")
        if os.getenv("AI_API_KEY"):
            self._data["ai"]["api_key"] = os.getenv("AI_API_KEY")

        self._validate()

    def _validate(self):
        """启动时校验关键配置项"""
        required = [
            ("database.host",),
            ("database.database",),
            ("ai.provider",),
            ("outlook.url",),
            ("outlook.state_file",),
        ]
        for keys in required:
            val = self._data
            for k in keys:
                if not isinstance(val, dict) or k not in val:
                    raise ValueError(f"配置缺失: {'.'.join(keys)}")
                val = val[k]
            if not val:
                raise ValueError(f"配置值为空: {'.'.join(keys)}")

    def get(self, *keys, default=None):
        val = self._data
        for k in keys:
            if not isinstance(val, dict) or k not in val:
                return default
            val = val[k]
        return val
```

### 3.3 .env 文件（敏感信息，gitignore）

```env
DB_PASSWORD=your_mysql_password
AI_API_KEY=sk-your-api-key
```

---

## 四、数据库层细化

### 4.1 连接池管理

```python
# db/connection.py
from dbutils.pooled_db import PooledDB
import pymysql
from config.loader import Config

class DBPool:
    _pool = None

    @classmethod
    def get_pool(cls):
        if cls._pool is None:
            cfg = Config().get("database")
            cls._pool = PooledDB(
                creator=pymysql,
                maxconnections=cfg["pool_size"],
                mincached=1,
                maxcached=cfg["pool_size"],
                host=cfg["host"],
                port=cfg["port"],
                user=cfg["user"],
                password=cfg["password"],
                database=cfg["database"],
                charset="utf8mb4",
                cursorclass=pymysql.cursors.DictCursor,
                autocommit=False,
            )
        return cls._pool

    @classmethod
    def get_conn(cls):
        return cls.get_pool().connection()
```

### 4.2 数据操作层（关键方法）

```python
# db/models.py
from db.connection import DBPool
from datetime import datetime
from loguru import logger

class EmailRecord:
    @staticmethod
    def is_processed(mail_uid: str) -> bool:
        """检查邮件是否已处理（幂等性核心）"""
        conn = DBPool.get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id FROM email_record WHERE mail_uid = %s AND processed = 1",
                    (mail_uid,)
                )
                return cur.fetchone() is not None
        finally:
            conn.close()

    @staticmethod
    def insert_or_get(mail_uid, mailbox_id, sender, subject, content):
        """
        插入邮件记录，若已存在则返回已有 ID。
        使用 INSERT IGNORE + UNIQUE 索引保证幂等。
        """
        conn = DBPool.get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT IGNORE INTO email_record (mailbox_id, mail_uid, sender, subject, content)
                    VALUES (%s, %s, %s, %s, %s)
                """, (mailbox_id, mail_uid, sender, subject, content))
                conn.commit()

                cur.execute(
                    "SELECT id, processed FROM email_record WHERE mail_uid = %s",
                    (mail_uid,)
                )
                row = cur.fetchone()
                return row["id"], row["processed"] == 1
        except Exception as e:
            conn.rollback()
            logger.error(f"插入邮件记录失败: {e}")
            raise
        finally:
            conn.close()

    @staticmethod
    def mark_processed(email_id: int):
        """标记邮件为已处理"""
        conn = DBPool.get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE email_record SET processed = 1 WHERE id = %s",
                    (email_id,)
                )
                conn.commit()
        finally:
            conn.close()


class ReplyRecord:
    @staticmethod
    def create(email_id: int, reply_content: str, status: str = "pending"):
        conn = DBPool.get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO reply_record (email_id, reply_content, status)
                    VALUES (%s, %s, %s)
                """, (email_id, reply_content, status))
                conn.commit()
                return cur.lastrowid
        finally:
            conn.close()

    @staticmethod
    def update_status(reply_id: int, status: str, error_msg: str = None):
        conn = DBPool.get_conn()
        try:
            with conn.cursor() as cur:
                sent_at = datetime.now() if status == "sent" else None
                cur.execute("""
                    UPDATE reply_record
                    SET status = %s, sent_at = %s, error_msg = %s
                    WHERE id = %s
                """, (status, sent_at, error_msg, reply_id))
                conn.commit()
        finally:
            conn.close()


class Rule:
    @staticmethod
    def get_active_rules(mailbox_id: int):
        """获取邮箱的所有启用规则"""
        conn = DBPool.get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT * FROM rule WHERE mailbox_id = %s",
                    (mailbox_id,)
                )
                return cur.fetchall()
        finally:
            conn.close()


class Mailbox:
    @staticmethod
    def get_active():
        """获取所有启用的邮箱配置"""
        conn = DBPool.get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM mailbox WHERE status = 1")
                return cur.fetchall()
        finally:
            conn.close()
```

### 4.3 建表 SQL 补充

在 V1 基础上增加索引：

```sql
-- 在 email_record 表上增加索引（V1 已有 UNIQUE(mail_uid)）
ALTER TABLE email_record ADD INDEX idx_mailbox_processed (mailbox_id, processed);
ALTER TABLE email_record ADD INDEX idx_received_at (received_at);

-- reply_record 增加索引
ALTER TABLE reply_record ADD INDEX idx_email_id (email_id);
ALTER TABLE reply_record ADD INDEX idx_status (status);
```

---

## 五、浏览器上下文管理

### 5.1 上下文管理器（单例复用）

```python
# browser/context_manager.py
from playwright.sync_api import sync_playwright, Browser, BrowserContext, Page
from config.loader import Config
from loguru import logger
from pathlib import Path

class BrowserManager:
    """管理 Playwright 生命周期，复用 browser 实例"""

    def __init__(self):
        self._playwright = None
        self._browser = None

    def start(self):
        """启动 Playwright 和浏览器"""
        cfg = Config().get("browser")
        self._playwright = sync_playwright().start()
        self._browser = self._playwright.chromium.launch(
            headless=cfg["headless"],
            slow_mo=cfg.get("slow_mo", 0),
        )
        logger.info("浏览器启动完成")

    def new_context(self, state_file: str = None) -> BrowserContext:
        """创建新的浏览器上下文，加载已保存的登录状态"""
        cfg = Config().get("browser")
        kwargs = {
            "viewport": cfg.get("viewport"),
        }
        if cfg.get("user_agent"):
            kwargs["user_agent"] = cfg["user_agent"]

        state_path = Path(state_file) if state_file else None
        if state_path and state_path.exists():
            kwargs["storage_state"] = str(state_path)
            logger.info(f"加载登录状态: {state_path}")
        else:
            logger.warning(f"登录状态文件不存在: {state_path}")

        return self._browser.new_context(**kwargs)

    def stop(self):
        """关闭浏览器和 Playwright"""
        if self._browser:
            self._browser.close()
        if self._playwright:
            self._playwright.stop()
        logger.info("浏览器已关闭")

    def save_state(self, context: BrowserContext, state_file: str):
        """保存当前上下文的登录状态"""
        state_path = Path(state_file)
        state_path.parent.mkdir(parents=True, exist_ok=True)
        context.storage_state(path=state_file)
        logger.info(f"登录状态已保存: {state_file}")
```

### 5.2 登录态校验

```python
# browser/auth_checker.py
from loguru import logger
from config.loader import Config

class AuthChecker:
    """检测登录状态是否有效"""

    # Outlook 登录页 URL 特征
    LOGIN_URL_PATTERNS = [
        "login.live.com",
        "login.microsoftonline.com",
        "account.live.com",
    ]

    @staticmethod
    def is_logged_in(page) -> bool:
        """
        判断当前页面是否处于已登录状态。
        策略：检查 URL 是否跳转到了登录页。
        """
        current_url = page.url
        for pattern in AuthChecker.LOGIN_URL_PATTERNS:
            if pattern in current_url:
                logger.warning(f"检测到登录页跳转，登录态可能已过期: {current_url}")
                return False

        # 额外检查：页面上是否有登录后的特征元素
        # Outlook Web 登录后通常有导航栏
        try:
            page.wait_for_selector(
                '[role="navigation"], [aria-label*="导航"], [data-app-bar]',
                timeout=5000
            )
            return True
        except Exception:
            logger.warning("未找到登录后特征元素，登录态可能已过期")
            return False
```

---

## 六、登录与状态保存（步骤 1-2 细化）

### 6.1 login.py 完整实现

```python
# login.py
"""
一次性登录脚本：打开浏览器，人工完成登录，保存 state.json。
运行方式：python login.py
"""
import sys
from pathlib import Path
from loguru import logger
from config.loader import Config
from browser.context_manager import BrowserManager
from browser.auth_checker import AuthChecker


def main():
    cfg = Config()
    outlook_cfg = cfg.get("outlook")
    browser_cfg = cfg.get("browser")

    state_file = outlook_cfg["state_file"]
    outlook_url = outlook_cfg["url"]

    # 确保状态目录存在
    Path(state_file).parent.mkdir(parents=True, exist_ok=True)

    logger.info("=== 邮箱登录状态保存工具 ===")
    logger.info(f"目标: {outlook_url}")
    logger.info(f"状态文件: {state_file}")

    bm = BrowserManager()
    try:
        bm.start()

        # 创建无状态的新上下文（首次登录）
        context = bm._browser.new_context(
            viewport=browser_cfg.get("viewport"),
        )
        page = context.new_page()

        logger.info(f"正在打开 {outlook_url} ...")
        page.goto(outlook_url, wait_until="domcontentloaded")

        logger.info("请在浏览器中完成登录（包括二次验证）")
        logger.info("登录完成后，确认收件箱页面完全加载，然后回到终端按 Enter")

        input("\n>>> 登录完成后按 Enter 保存状态 <<<\n")

        # 验证登录状态
        if not AuthChecker.is_logged_in(page):
            logger.error("登录状态验证失败，请确认已成功登录后重试")
            sys.exit(1)

        # 保存状态
        bm.save_state(context, state_file)
        logger.info(f"登录状态保存成功: {state_file}")

        context.close()
    finally:
        bm.stop()


if __name__ == "__main__":
    main()
```

### 6.2 登录态过期恢复流程

```
运行时检测到登录态过期
    │
    ▼
暂停定时任务（设置全局 flag）
    │
    ▼
发送告警通知（webhook / 邮件 / 日志）
    │
    ▼
等待人工重新执行 python login.py
    │
    ▼
检测到 state.json 更新时间变化 → 恢复定时任务
```

```python
# monitor/health_check.py
import os
from loguru import logger
from config.loader import Config

class HealthChecker:
    _state_file_mtime = None
    _paused = False

    @classmethod
    def check_state_freshness(cls, state_file: str) -> bool:
        """检查 state.json 是否近期被更新（人工重新登录后）"""
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
        """暂停监控"""
        cls._paused = True
        logger.error(f"监控已暂停，原因: {reason}")
        # TODO: 发送告警通知
```

---

## 七、收件箱监控与选择器策略（步骤 3-5 细化）

### 7.1 选择器配置化（核心改进）

> **原则**：Outlook Web 的 DOM 结构经常变化，CSS class 名是动态生成的（如 `_3mXx_7`），绝对不能依赖。应优先使用 `role`、`aria-label`、`data-*` 等语义属性。

```python
# browser/selectors.py
"""
Outlook Web 选择器集中管理。
所有选择器使用多级回退策略：优先用 aria/role，其次用 data 属性，最后用文本匹配。
"""

class OutlookSelectors:
    # ===== 邮件列表区域 =====
    # 邮件列表容器
    MAIL_LIST = [
        '[role="listbox"][aria-label*="邮件"]',        # 中文界面
        '[role="listbox"][aria-label*="Message"]',      # 英文界面
        'div[role="list"]',                              # 通用回退
    ]

    # 单封邮件条目
    MAIL_ITEM = [
        '[role="option"]',
        'div[role="listbox"] > div[role="option"]',
        '[data-convid]',                                 # 部分版本有 conversation ID
    ]

    # ===== 邮件详情区域 =====
    # 邮件主题
    MAIL_SUBJECT = [
        '[role="heading"][aria-level="2"]',
        'h1[class*="subject"]',
        'div[aria-label*="主题"]',
        'div[aria-label*="Subject"]',
    ]

    # 邮件正文容器
    MAIL_BODY = [
        '[role="document"]',
        'div[aria-label*="邮件正文"]',
        'div[aria-label*="message body"]',
        'div[class*="ReadingPane"]',
    ]

    # 发件人信息
    MAIL_SENDER = [
        '[role="heading"][aria-level="3"]',              # 发件人姓名/邮箱
        'span[class*="EmailAddress"]',
        'div[aria-label*="发件人"]',
        'div[aria-label*="From"]',
    ]

    # ===== 回复操作区域 =====
    # 回复按钮
    REPLY_BUTTON = [
        'button[aria-label*="回复"]',
        'button[aria-label*="Reply"]',
        'button[title*="回复"]',
        'button[title*="Reply"]',
        'div[role="button"][aria-label*="回复"]',
    ]

    # 回复输入框（contenteditable div）
    REPLY_INPUT = [
        'div[role="textbox"][contenteditable="true"]',
        'div[contenteditable="true"][aria-label*="邮件"]',
        'div[contenteditable="true"][aria-label*="message"]',
        'iframe[id*="editor"]',                          # 某些版本用 iframe
    ]

    # 发送按钮
    SEND_BUTTON = [
        'button[aria-label*="发送"]',
        'button[aria-label*="Send"]',
        'button[title*="发送"]',
        'button[title*="Send"]',
    ]

    # ===== 其他 =====
    # 关闭邮件详情按钮
    CLOSE_BUTTON = [
        'button[aria-label*="关闭"]',
        'button[aria-label*="Close"]',
        'button[aria-label*="返回"]',
    ]
```

### 7.2 选择器多级回退查找工具

```python
# browser/selector_helper.py
from playwright.sync_api import Page
from loguru import logger

def try_selectors(page: Page, selectors: list, timeout: int = 5000):
    """
    依次尝试选择器列表，返回第一个匹配到的元素。
    所有选择器都失败时返回 None。
    """
    for sel in selectors:
        try:
            el = page.wait_for_selector(sel, timeout=timeout, state="visible")
            if el:
                logger.debug(f"选择器命中: {sel}")
                return el
        except Exception:
            continue
    logger.warning(f"所有选择器均未命中: {selectors}")
    return None

def try_click(page: Page, selectors: list, timeout: int = 5000) -> bool:
    """依次尝试点击选择器列表，成功返回 True"""
    for sel in selectors:
        try:
            page.click(sel, timeout=timeout)
            logger.debug(f"点击成功: {sel}")
            return True
        except Exception:
            continue
    logger.warning(f"所有点击选择器均未命中: {selectors}")
    return False
```

### 7.3 收件箱轮询核心逻辑

```python
# monitor/inbox_checker.py
import time
import hashlib
from loguru import logger
from playwright.sync_api import Page
from config.loader import Config
from browser.selectors import OutlookSelectors as S
from browser.selector_helper import try_selectors, try_click
from browser.auth_checker import AuthChecker
from monitor.health_check import HealthChecker
from monitor.sender_matcher import SenderMatcher
from monitor.content_extractor import ContentExtractor
from ai.adapter_factory import get_ai_adapter
from browser.reply_sender import ReplySender
from db.models import EmailRecord, ReplyRecord, Rule, Mailbox


class InboxChecker:
    def __init__(self, page: Page, mailbox: dict):
        self.page = page
        self.mailbox = mailbox
        self.config = Config()
        self.ai_adapter = get_ai_adapter(self.config)
        self.content_extractor = ContentExtractor()
        self.reply_sender = ReplySender(page)

    def run(self):
        """主入口：检查收件箱并处理新邮件"""
        logger.info(f"开始检查邮箱: {self.mailbox['email']}")

        # 1. 检查登录状态
        if not AuthChecker.is_logged_in(self.page):
            HealthChecker.pause("登录态已过期")
            return

        # 2. 导航到收件箱
        if not self._navigate_to_inbox():
            return

        # 3. 获取邮件列表
        mail_items = self._get_mail_list()
        if not mail_items:
            logger.info("收件箱无新邮件或无法获取邮件列表")
            return

        # 4. 逐封处理
        max_per_run = self.config.get("outlook", "max_emails_per_run", default=20)
        processed = 0

        for index, item in enumerate(mail_items):
            if processed >= max_per_run:
                logger.info(f"达到单次处理上限 {max_per_run}，剩余下次处理")
                break
            try:
                if self._process_mail_item(index):
                    processed += 1
            except Exception as e:
                logger.error(f"处理邮件#{index} 异常: {e}")
                continue

        logger.info(f"本轮处理完成，共处理 {processed} 封邮件")

    def _navigate_to_inbox(self) -> bool:
        """导航到收件箱页面"""
        outlook_url = self.config.get("outlook", "url")
        inbox_path = self.config.get("outlook", "inbox_path", default="/mail/0/inbox")

        target_url = f"{outlook_url}{inbox_path}"
        logger.info(f"导航到收件箱: {target_url}")

        try:
            self.page.goto(target_url, wait_until="domcontentloaded")
            # 等待邮件列表加载
            list_el = try_selectors(self.page, S.MAIL_LIST, timeout=15000)
            if not list_el:
                logger.error("邮件列表未加载")
                return False
            # 额外等待，确保列表渲染完成
            self.page.wait_for_timeout(2000)
            return True
        except Exception as e:
            logger.error(f"导航到收件箱失败: {e}")
            return False

    def _get_mail_list(self) -> list:
        """获取邮件列表元素"""
        # 使用第一个命中的选择器
        for sel in S.MAIL_ITEM:
            try:
                items = self.page.query_selector_all(sel)
                if items and len(items) > 0:
                    logger.info(f"获取到 {len(items)} 封邮件 (选择器: {sel})")
                    return items
            except Exception:
                continue

        logger.warning("未找到邮件列表项")
        return []

    def _process_mail_item(self, index: int) -> bool:
        """处理单封邮件：点击 → 提取 → 匹配 → 回复 → 记录"""
        # 1. 点击邮件打开
        for sel in S.MAIL_ITEM:
            try:
                items = self.page.query_selector_all(sel)
                if index < len(items):
                    items[index].click()
                    self.page.wait_for_timeout(1500)  # 等待邮件详情加载
                    break
            except Exception:
                continue
        else:
            logger.warning(f"无法点击邮件#{index}")
            return False

        # 2. 提取 mail_uid（关键：用于幂等去重）
        mail_uid = self._extract_mail_uid()
        if not mail_uid:
            logger.warning(f"邮件#{index} 无法提取 mail_uid，跳过")
            self._close_mail()
            return False

        # 3. 检查是否已处理
        if EmailRecord.is_processed(mail_uid):
            logger.debug(f"邮件已处理，跳过: {mail_uid}")
            self._close_mail()
            return False

        # 4. 提取发件人、主题、正文
        sender = self._extract_sender()
        subject = self._extract_subject()
        body = self._extract_body()

        logger.info(f"邮件: uid={mail_uid}, sender={sender}, subject={subject[:50]}")

        # 5. 匹配发件人规则
        rules = Rule.get_active_rules(self.mailbox["id"])
        matched_rule = SenderMatcher.match(sender, rules)

        if not matched_rule:
            logger.info(f"发件人不匹配任何规则，跳过: {sender}")
            # 仍记录邮件，标记为已处理（避免重复检查）
            EmailRecord.insert_or_get(
                mail_uid, self.mailbox["id"], sender, subject, body
            )
            self._close_mail()
            return False

        # 6. 清洗正文
        clean_body = self.content_extractor.clean(body)

        # 7. AI 生成回复
        try:
            reply_content = self.ai_adapter.generate(
                prompt_template=matched_rule["prompt_template"],
                email_content=clean_body
            )
            logger.info(f"AI 回复生成完成 ({len(reply_content)} 字符)")
        except Exception as e:
            logger.error(f"AI 回复生成失败: {e}")
            self._close_mail()
            return False

        # 8. 写入数据库
        email_id, already_processed = EmailRecord.insert_or_get(
            mail_uid, self.mailbox["id"], sender, subject, body
        )
        reply_id = ReplyRecord.create(email_id, reply_content, status="pending")

        # 9. 发送回复
        if matched_rule["auto_send"] == 1:
            try:
                self.reply_sender.send(reply_content)
                ReplyRecord.update_status(reply_id, "sent")
                EmailRecord.mark_processed(email_id)
                logger.info(f"回复发送成功: mail_uid={mail_uid}")
            except Exception as e:
                ReplyRecord.update_status(reply_id, "failed", str(e))
                logger.error(f"回复发送失败: {e}")
        else:
            # 人工审核模式：仅写入草稿不发送
            logger.info(f"人工审核模式，未自动发送: mail_uid={mail_uid}")
            EmailRecord.mark_processed(email_id)

        # 10. 关闭邮件详情，返回列表
        self._close_mail()
        return True

    def _extract_mail_uid(self) -> str:
        """
        提取邮件唯一标识。策略优先级：
        1. 从 URL 中提取 conversation ID / message ID
        2. 从邮件元素 data-convid 属性获取
        3. 使用 subject + sender + body前100字符 生成哈希兜底
        """
        # 策略 1：URL 解析
        current_url = self.page.url
        if "id=" in current_url:
            # Outlook URL 格式: /mail/0/inbox/id/xxxxx
            uid = current_url.split("id=")[-1].split("&")[0]
            if uid:
                return f"url:{uid}"

        # 从路径中提取
        parts = current_url.rstrip("/").split("/")
        if len(parts) >= 2:
            last_segment = parts[-1]
            if last_segment and last_segment not in ("inbox", "sent", "drafts"):
                return f"path:{last_segment}"

        # 策略 2：data-convid 属性
        try:
            conv_el = self.page.query_selector("[data-convid]")
            if conv_el:
                conv_id = conv_el.get_attribute("data-convid")
                if conv_id:
                    return f"conv:{conv_id}"
        except Exception:
            pass

        # 策略 3：哈希兜底
        sender = self._extract_sender() or ""
        subject = self._extract_subject() or ""
        body = self._extract_body() or ""
        hash_input = f"{sender}|{subject}|{body[:100]}"
        uid_hash = hashlib.md5(hash_input.encode()).hexdigest()
        return f"hash:{uid_hash}"

    def _extract_sender(self) -> str:
        """提取发件人地址"""
        el = try_selectors(self.page, S.MAIL_SENDER, timeout=3000)
        if el:
            text = el.inner_text().strip()
            # 尝试从 "Name <email@example.com>" 格式中提取邮箱
            if "<" in text and ">" in text:
                return text.split("<")[1].split(">")[0].strip()
            return text
        return ""

    def _extract_subject(self) -> str:
        """提取邮件主题"""
        el = try_selectors(self.page, S.MAIL_SUBJECT, timeout=3000)
        if el:
            return el.inner_text().strip()
        return ""

    def _extract_body(self) -> str:
        """提取邮件正文"""
        el = try_selectors(self.page, S.MAIL_BODY, timeout=3000)
        if el:
            return el.inner_text().strip()
        return ""

    def _close_mail(self):
        """关闭邮件详情，返回列表视图"""
        try_click(self.page, S.CLOSE_BUTTON, timeout=3000)
        self.page.wait_for_timeout(1000)
```

### 7.4 发件人匹配

```python
# monitor/sender_matcher.py
import re
from loguru import logger

class SenderMatcher:
    @staticmethod
    def match(sender: str, rules: list) -> dict | None:
        """
        将发件人地址与规则列表匹配。
        支持正则匹配，返回第一个命中的规则。
        """
        if not sender:
            return None

        for rule in rules:
            pattern = rule["sender_pattern"]
            try:
                if re.search(pattern, sender, re.IGNORECASE):
                    logger.info(f"发件人匹配规则: {sender} -> rule#{rule['id']}")
                    return rule
            except re.error as e:
                logger.error(f"规则#{rule['id']} 正则表达式无效: {pattern}, 错误: {e}")
                continue

        return None
```

### 7.5 邮件正文清洗

```python
# monitor/content_extractor.py
import html2text
import re
from loguru import logger

class ContentExtractor:
    def __init__(self):
        self.h2t = html2text.HTML2Text()
        self.h2t.ignore_links = False
        self.h2t.ignore_images = True
        self.h2t.body_width = 0  # 不换行

    def clean(self, raw_body: str) -> str:
        """
        清洗邮件正文：
        1. HTML 转纯文本
        2. 去除引用回复（"On xxx wrote:" 之后的内容）
        3. 去除签名（"--" 分隔线之后）
        4. 压缩多余空白
        """
        # 如果包含 HTML 标签，先转换
        if "<" in raw_body and ">" in raw_body:
            text = self.h2t.handle(raw_body)
        else:
            text = raw_body

        # 去除引用回复
        text = self._strip_quoted_reply(text)

        # 去除签名
        text = self._strip_signature(text)

        # 压缩空白
        text = re.sub(r'\n{3,}', '\n\n', text)
        text = text.strip()

        logger.debug(f"正文清洗完成: {len(raw_body)} -> {len(text)} 字符")
        return text

    def _strip_quoted_reply(self, text: str) -> str:
        """去除引用的回复内容"""
        patterns = [
            r'On .+ wrote:',
            r'在 .+ 写道：',
            r'发件人:.+',
            r'From:.+',
            r'-----原始邮件-----',
            r'-----Original Message-----',
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.MULTILINE)
            if match:
                text = text[:match.start()]
        return text

    def _strip_signature(self, text: str) -> str:
        """去除邮件签名"""
        # "--" 签名分隔符
        sig_match = re.search(r'^--\s*$', text, re.MULTILINE)
        if sig_match:
            text = text[:sig_match.start()]

        # "此致/敬礼/Best regards" 等常见签名开头
        sig_patterns = [
            r'(此致|敬礼|Best regards|Regards|Sincerely|Thanks)\s*$',
        ]
        for pattern in sig_patterns:
            match = re.search(pattern, text, re.MULTILINE | re.IGNORECASE)
            if match:
                text = text[:match.start()]

        return text
```

---

## 八、AI 回复生成（步骤 6 细化）

### 8.1 统一适配器接口

```python
# ai/base.py
from abc import ABC, abstractmethod
import time
from loguru import logger

class AIAdapter(ABC):
    def __init__(self, config: dict):
        self.config = config
        self.max_tokens = config.get("max_tokens", 1000)
        self.temperature = config.get("temperature", 0.7)
        self.timeout = config.get("timeout", 30)
        self.retry_times = config.get("retry_times", 3)
        self.retry_interval = config.get("retry_interval", 5)

    @abstractmethod
    def _call_api(self, prompt: str) -> str:
        """子类实现：调用具体 AI API"""
        pass

    def generate(self, prompt_template: str, email_content: str) -> str:
        """
        生成回复内容。包含重试逻辑。
        :param prompt_template: 包含 {email_content} 占位符的提示词模板
        :param email_content: 清洗后的邮件正文
        :return: AI 生成的回复文本
        """
        prompt = prompt_template.replace("{email_content}", email_content)

        # 安全检查：确保 prompt 不超过模型上下文限制
        max_input_chars = 12000  # 保守限制
        if len(prompt) > max_input_chars:
            logger.warning(f"Prompt 过长 ({len(prompt)} 字符)，截断处理")
            prompt = prompt[:max_input_chars]

        for attempt in range(1, self.retry_times + 1):
            try:
                logger.info(f"调用 AI 生成回复 (第 {attempt} 次)")
                result = self._call_api(prompt)
                if result and result.strip():
                    return result.strip()
                logger.warning(f"AI 返回空内容 (第 {attempt} 次)")
            except Exception as e:
                logger.error(f"AI 调用失败 (第 {attempt}/{self.retry_times} 次): {e}")
                if attempt < self.retry_times:
                    time.sleep(self.retry_interval)

        raise RuntimeError(f"AI 调用失败，已重试 {self.retry_times} 次")
```

### 8.2 OpenAI 兼容适配器（DeepSeek/OpenAI/Qwen 通用）

```python
# ai/openai_adapter.py
from openai import OpenAI
from ai.base import AIAdapter
from loguru import logger

class OpenAIAdapter(AIAdapter):
    """适用于 DeepSeek / OpenAI / Qwen 等 OpenAI 兼容接口"""

    def __init__(self, config: dict):
        super().__init__(config)
        self.client = OpenAI(
            api_key=config["api_key"],
            base_url=config["base_url"],
            timeout=config.get("timeout", 30),
        )
        self.model = config["model"]
        logger.info(f"AI 适配器初始化: provider={config['provider']}, model={self.model}")

    def _call_api(self, prompt: str) -> str:
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "你是一个专业的邮件回复助手。请根据收到的邮件内容，"
                        "生成一封礼貌、专业、简洁的回复邮件。"
                        "只输出回复正文，不要包含主题行。"
                    )
                },
                {"role": "user", "content": prompt}
            ],
            max_tokens=self.max_tokens,
            temperature=self.temperature,
        )
        return response.choices[0].message.content
```

### 8.3 Ollama 适配器

```python
# ai/ollama_adapter.py
import requests
from ai.base import AIAdapter
from loguru import logger

class OllamaAdapter(AIAdapter):
    """Ollama 本地模型适配器"""

    def __init__(self, config: dict):
        super().__init__(config)
        self.base_url = config.get("base_url", "http://localhost:11434")
        self.model = config["model"]
        logger.info(f"Ollama 适配器初始化: {self.base_url}, model={self.model}")

    def _call_api(self, prompt: str) -> str:
        resp = requests.post(
            f"{self.base_url}/api/generate",
            json={
                "model": self.model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": self.temperature,
                    "num_predict": self.max_tokens,
                }
            },
            timeout=self.timeout
        )
        resp.raise_for_status()
        return resp.json().get("response", "")
```

### 8.4 适配器工厂

```python
# ai/adapter_factory.py
from ai.base import AIAdapter
from ai.openai_adapter import OpenAIAdapter
from ai.ollama_adapter import OllamaAdapter

def get_ai_adapter(config) -> AIAdapter:
    ai_cfg = config.get("ai")
    provider = ai_cfg["provider"]

    if provider in ("deepseek", "openai", "qwen"):
        return OpenAIAdapter(ai_cfg)
    elif provider == "ollama":
        return OllamaAdapter(ai_cfg)
    else:
        raise ValueError(f"不支持的 AI provider: {provider}")
```

---

## 九、回复发送（步骤 7 细化 — 富文本输入）

> **关键问题**：Outlook Web 的回复输入框是 `contenteditable="true"` 的 div（或 iframe），不是 `<textarea>` 或 `<input>`，Playwright 的 `fill()` 方法无效。必须使用其他输入策略。

### 9.1 回复发送器

```python
# browser/reply_sender.py
import time
from loguru import logger
from playwright.sync_api import Page
from browser.selectors import OutlookSelectors as S
from browser.selector_helper import try_click, try_selectors


class ReplySender:
    def __init__(self, page: Page):
        self.page = page

    def send(self, reply_content: str):
        """
        完整的回复发送流程：
        1. 点击「回复」按钮
        2. 等待回复编辑器加载
        3. 输入回复内容（contenteditable 专用策略）
        4. 点击「发送」
        5. 验证发送成功
        """
        # 1. 点击回复按钮
        logger.info("点击「回复」按钮")
        if not try_click(self.page, S.REPLY_BUTTON, timeout=10000):
            raise RuntimeError("无法找到回复按钮")

        self.page.wait_for_timeout(2000)  # 等待编辑器加载

        # 2. 定位回复输入框
        logger.info("定位回复输入框")
        input_el = try_selectors(self.page, S.REPLY_INPUT, timeout=10000)
        if not input_el:
            raise RuntimeError("无法找到回复输入框")

        # 3. 输入回复内容
        logger.info(f"输入回复内容 ({len(reply_content)} 字符)")
        self._input_content(input_el, reply_content)

        # 4. 验证内容已输入
        self.page.wait_for_timeout(500)
        if not self._verify_content(input_el, reply_content):
            logger.warning("回复内容验证失败，尝试重新输入")
            self._input_content(input_el, reply_content)

        # 5. 点击发送
        logger.info("点击「发送」按钮")
        if not try_click(self.page, S.SEND_BUTTON, timeout=10000):
            raise RuntimeError("无法找到发送按钮")

        # 6. 等待发送完成
        self.page.wait_for_timeout(3000)

        # 7. 验证发送成功（回复窗口消失）
        if self._verify_sent():
            logger.info("回复发送成功")
        else:
            logger.warning("发送验证不确定，请人工确认")

    def _input_content(self, element, content: str):
        """
        向 contenteditable 元素输入内容。
        策略：
        1. 先点击聚焦
        2. 清空已有内容
        3. 使用 keyboard.type 逐字输入（最可靠）
        4. 如果内容过长，回退到 evaluate 设置 innerHTML
        """
        # 点击聚焦
        element.click()
        self.page.wait_for_timeout(300)

        # 清空已有内容（全选后删除）
        self.page.keyboard.press("Control+A")
        self.page.keyboard.press("Delete")
        self.page.wait_for_timeout(200)

        # 如果内容较短（< 2000字符），使用 keyboard.type
        if len(content) <= 2000:
            self.page.keyboard.type(content, delay=10)
        else:
            # 内容过长时使用 evaluate 直接设置
            self._set_content_via_evaluate(element, content)

    def _set_content_via_evaluate(self, element, content: str):
        """通过 JavaScript 直接设置 contenteditable 内容"""
        try:
            # 将纯文本转换为 HTML（换行转 <br>）
            html_content = content.replace("\n", "<br>")
            self.page.evaluate(
                """(el, html) => {
                    el.innerHTML = html;
                    // 触发 input 事件让 Outlook 识别内容变化
                    el.dispatchEvent(new Event('input', { bubbles: true }));
                }""",
                {"arg": element, "html": html_content}
            )
            logger.info("通过 evaluate 设置回复内容完成")
        except Exception as e:
            logger.error(f"evaluate 设置内容失败: {e}")
            # 最终回退：逐字输入
            self.page.keyboard.type(content, delay=5)

    def _verify_content(self, element, expected: str) -> bool:
        """验证回复内容是否成功输入"""
        try:
            actual = element.inner_text()
            # 检查输入内容的前 50 个字符是否匹配
            if expected[:50] in actual:
                return True
            logger.warning(f"内容验证不匹配，期望前50字符: {expected[:50]}")
            return False
        except Exception:
            return False

    def _verify_sent(self) -> bool:
        """验证邮件是否发送成功（回复窗口关闭）"""
        try:
            # 发送成功后，回复编辑器应该消失
            el = self.page.query_selector(S.REPLY_INPUT[0])
            if el is None:
                return True
            # 或者检查是否有成功提示
            # Outlook 发送成功后可能显示 "已发送" 或跳回收件箱
            return False
        except Exception:
            return True  # 无法确定时默认成功
```

---

## 十、日志与错误处理

### 10.1 结构化日志配置

```python
# utils/logger_setup.py
import sys
from loguru import logger
from pathlib import Path
from config.loader import Config

def setup_logger():
    cfg = Config().get("logging")
    log_dir = Path(cfg["dir"])
    log_dir.mkdir(parents=True, exist_ok=True)

    # 清除默认 handler
    logger.remove()

    # 控制台输出
    logger.add(
        sys.stdout,
        level=cfg["level"],
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
               "<level>{level: <8}</level> | "
               "<cyan>{module}</cyan>:<cyan>{line}</cyan> - "
               "<level>{message}</level>",
        colorize=True,
    )

    # 文件输出（按模块分文件）
    logger.add(
        log_dir / "app_{time:YYYY-MM-DD}.log",
        level=cfg["level"],
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {module}:{line} - {message}",
        rotation=cfg.get("rotation", "10 MB"),
        retention=cfg.get("retention", "30 days"),
        encoding="utf-8",
    )

    # 错误日志单独文件
    logger.add(
        log_dir / "error_{time:YYYY-MM-DD}.log",
        level="ERROR",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {module}:{line} - {message}",
        rotation="10 MB",
        retention="30 days",
        encoding="utf-8",
    )

    logger.info("日志系统初始化完成")
```

### 10.2 分层异常体系

```python
# utils/exceptions.py

class EmailAutoReplyError(Exception):
    """基础异常"""
    pass

class LoginExpiredError(EmailAutoReplyError):
    """登录态过期"""
    pass

class SelectorNotFoundError(EmailAutoReplyError):
    """选择器未找到（DOM 结构可能已变化）"""
    def __init__(self, selector_desc: str):
        super().__init__(f"选择器未找到: {selector_desc}")
        self.selector_desc = selector_desc

class AIGenerationError(EmailAutoReplyError):
    """AI 回复生成失败"""
    pass

class SendReplyError(EmailAutoReplyError):
    """回复发送失败"""
    pass

class DatabaseError(EmailAutoReplyError):
    """数据库操作失败"""
    pass
```

---

## 十一、定时任务管理（步骤 3 细化）

### 11.1 main.py 完整入口

```python
# main.py
"""
系统主入口：启动定时任务，每分钟检查收件箱。
"""
import signal
import sys
from loguru import logger
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.executors.pool import ThreadPoolExecutor

from config.loader import Config
from utils.logger_setup import setup_logger
from browser.context_manager import BrowserManager
from monitor.inbox_checker import InboxChecker
from monitor.health_check import HealthChecker
from db.models import Mailbox


# 全局浏览器管理器
browser_manager = BrowserManager()
# 全局上下文（复用，减少资源消耗）
_context = None
_page = None


def init_browser():
    """初始化浏览器和页面"""
    global browser_manager, _context, _page
    browser_manager.start()

    cfg = Config()
    state_file = cfg.get("outlook", "state_file")

    _context = browser_manager.new_context(state_file)
    _page = _context.new_page()
    logger.info("浏览器页面初始化完成")


def check_inbox_job():
    """定时任务：检查收件箱"""
    global _context, _page

    cfg = Config()
    state_file = cfg.get("outlook", "state_file")

    # 检查是否暂停（登录态过期等）
    if not HealthChecker.check_state_freshness(state_file):
        logger.warning("监控处于暂停状态，跳过本轮检查")
        return

    try:
        # 获取所有启用的邮箱
        mailboxes = Mailbox.get_active()
        if not mailboxes:
            logger.warning("没有启用的邮箱配置")
            return

        for mailbox in mailboxes:
            try:
                checker = InboxChecker(_page, mailbox)
                checker.run()
            except Exception as e:
                logger.error(f"邮箱 {mailbox['email']} 处理异常: {e}")

    except Exception as e:
        logger.error(f"定时任务执行异常: {e}")


def cleanup(signum=None, frame=None):
    """清理资源"""
    logger.info("正在关闭系统...")
    global _context, browser_manager
    if _context:
        _context.close()
    browser_manager.stop()
    sys.exit(0)


def main():
    setup_logger()
    logger.info("=== 邮箱自动回复系统启动 ===")

    # 注册信号处理
    signal.signal(signal.SIGINT, cleanup)
    signal.signal(signal.SIGTERM, cleanup)

    # 初始化浏览器
    init_browser()

    # 配置定时任务
    scheduler_cfg = Config().get("scheduler")

    scheduler = BlockingScheduler(
        executors={
            "default": ThreadPoolExecutor(max_workers=1)
        },
        job_defaults={
            "coalesce": scheduler_cfg.get("coalesce", True),
            "max_instances": scheduler_cfg.get("max_instances", 1),
        }
    )

    scheduler.add_job(
        check_inbox_job,
        "interval",
        minutes=scheduler_cfg.get("interval_minutes", 1),
        id="check_inbox",
        next_run_time=None,  # 不立即执行，等间隔触发
    )

    logger.info(f"定时任务已启动，间隔 {scheduler_cfg.get('interval_minutes', 1)} 分钟")

    try:
        # 启动前先执行一次
        logger.info("执行首次检查...")
        check_inbox_job()

        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        cleanup()


if __name__ == "__main__":
    main()
```

### 11.2 并发控制说明

```
问题：如果一轮检查超过 1 分钟，下一轮会重叠执行，导致：
  - 同一封邮件被处理两次
  - 浏览器页面状态冲突

解决方案：
  1. max_instances=1：APScheduler 自动跳过重叠的任务实例
  2. coalesce=True：积压的多次触发合并为一次
  3. 数据库 UNIQUE(mail_uid)：即使重叠，DB 层面保证幂等
  4. ThreadPoolExecutor(max_workers=1)：确保单线程执行
```

---

## 十二、部署方案（细化）

### 12.1 Windows Server 部署

```bash
# 1. 安装 Python 3.11+
# 2. 克隆项目
git clone <repo> C:\email-auto-reply
cd C:\email-auto-reply

# 3. 创建虚拟环境
python -m venv .venv
.venv\Scripts\activate

# 4. 安装依赖
pip install -r requirements.txt
playwright install chromium

# 5. 配置
copy config.yaml.example config.yaml
# 编辑 config.yaml 填写数据库和 AI 配置
copy .env.example .env
# 编辑 .env 填写密码

# 6. 初始化数据库
mysql -u root -p < db/init_db.sql

# 7. 首次登录
python login.py

# 8. 测试运行
python main.py

# 9. 注册为 Windows 服务（使用 NSSM）
nssm install EmailAutoReply "C:\email-auto-reply\.venv\Scripts\python.exe" "C:\email-auto-reply\main.py"
nssm set EmailAutoReply AppDirectory "C:\email-auto-reply"
nssm set EmailAutoReply AppStdout "C:\email-auto-reply\logs\service_stdout.log"
nssm set EmailAutoReply AppStderr "C:\email-auto-reply\logs\service_stderr.log"
nssm start EmailAutoReply
```

### 12.2 Linux 部署（带虚拟显示）

```bash
# Outlook Web 在 headless 模式可能被检测，建议使用 Xvfb 虚拟显示
apt-get install -y xvfb

# 使用 xvfb-run 启动
xvfb-run -a python main.py

# 或配置为 systemd 服务
cat > /etc/systemd/system/email-auto-reply.service << 'EOF'
[Unit]
Description=Email Auto Reply System
After=network.target mysql.service

[Service]
Type=simple
User=appuser
WorkingDirectory=/opt/email-auto-reply
ExecStart=/usr/bin/xvfb-run -a /opt/email-auto-reply/.venv/bin/python main.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable email-auto-reply
systemctl start email-auto-reply
```

### 12.3 Docker 部署

```dockerfile
# Dockerfile
FROM python:3.11-slim

# 安装 Chromium 依赖
RUN apt-get update && apt-get install -y \
    chromium \
    xvfb \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN playwright install chromium

COPY . .

# 创建数据目录
RUN mkdir -p /app/state /app/logs

# 使用 xvfb 运行
CMD ["xvfb-run", "-a", "python", "main.py"]
```

```yaml
# docker-compose.yml
version: "3.8"
services:
  email-auto-reply:
    build: .
    container_name: email-auto-reply
    restart: always
    environment:
      - DB_PASSWORD=${DB_PASSWORD}
      - AI_API_KEY=${AI_API_KEY}
    volumes:
      - ./state:/app/state        # 持久化登录状态
      - ./logs:/app/logs          # 持久化日志
      - ./config.yaml:/app/config.yaml:ro
    depends_on:
      - mysql

  mysql:
    image: mysql:8.0
    container_name: email-mysql
    restart: always
    environment:
      MYSQL_ROOT_PASSWORD: ${DB_PASSWORD}
      MYSQL_DATABASE: email_auto_reply
    volumes:
      - mysql_data:/var/lib/mysql
      - ./db/init_db.sql:/docker-entrypoint-initdb.d/init.sql:ro
    ports:
      - "3306:3306"

volumes:
  mysql_data:
```

---

## 十三、测试策略

### 13.1 测试分层

| 层级 | 范围 | 工具 | 目标 |
|------|------|------|------|
| 单元测试 | 发件人匹配、正文清洗、配置加载 | pytest | 核心逻辑正确性 |
| 集成测试 | 数据库操作、AI 适配器 | pytest + testcontainers | 模块间协作 |
| E2E 测试 | 完整流程 | Playwright + pytest | 端到端验证 |
| 冒烟测试 | 关键路径 | 手动/脚本 | 上线前快速验证 |

### 13.2 关键单元测试

```python
# tests/test_sender_matcher.py
import pytest
from monitor.sender_matcher import SenderMatcher

class TestSenderMatcher:
    def test_exact_match(self):
        rules = [{"id": 1, "sender_pattern": r"test@example\.com"}]
        assert SenderMatcher.match("test@example.com", rules) is not None

    def test_regex_match(self):
        rules = [{"id": 1, "sender_pattern": r".*@company\.com$"}]
        assert SenderMatcher.match("alice@company.com", rules) is not None
        assert SenderMatcher.match("alice@gmail.com", rules) is None

    def test_case_insensitive(self):
        rules = [{"id": 1, "sender_pattern": r"test@example\.com"}]
        assert SenderMatcher.match("TEST@EXAMPLE.COM", rules) is not None

    def test_no_match(self):
        rules = [{"id": 1, "sender_pattern": r"specific@domain\.com"}]
        assert SenderMatcher.match("other@domain.com", rules) is None

    def test_empty_sender(self):
        rules = [{"id": 1, "sender_pattern": r".*"}]
        assert SenderMatcher.match("", rules) is None

    def test_invalid_regex(self):
        rules = [{"id": 1, "sender_pattern": r"["}]  # 无效正则
        assert SenderMatcher.match("test@example.com", rules) is None
```

```python
# tests/test_content_extractor.py
import pytest
from monitor.content_extractor import ContentExtractor

class TestContentExtractor:
    def setup_method(self):
        self.extractor = ContentExtractor()

    def test_html_to_text(self):
        html = "<p>Hello <b>World</b></p>"
        result = self.extractor.clean(html)
        assert "Hello" in result
        assert "World" in result

    def test_strip_quoted_reply_english(self):
        text = "Original message here.\n\nOn Mon, Jan 1, 2024 at 10:00 AM John wrote:\n> Quoted text"
        result = self.extractor.clean(text)
        assert "Original message here" in result
        assert "Quoted text" not in result

    def test_strip_quoted_reply_chinese(self):
        text = "原始内容\n\n在 2024年1月1日，张三 写道：\n> 引用内容"
        result = self.extractor.clean(text)
        assert "原始内容" in result
        assert "引用内容" not in result

    def test_strip_signature(self):
        text = "Email body here.\n\n--\nJohn Doe\nSoftware Engineer"
        result = self.extractor.clean(text)
        assert "Email body here" in result
        assert "John Doe" not in result
```

### 13.3 端到端冒烟测试清单

```
[ ] 1. python login.py 能正常打开浏览器并保存 state.json
[ ] 2. state.json 存在且非空
[ ] 3. python main.py 启动后首次检查能访问收件箱
[ ] 4. 能正确识别邮件列表（日志显示获取到 N 封邮件）
[ ] 5. 能正确提取发件人、主题、正文
[ ] 6. 发件人匹配规则后能触发 AI 生成回复
[ ] 7. AI 回复内容非空且长度合理
[ ] 8. 回复内容能正确输入到 Outlook 回复框
[ ] 9. 点击发送后邮件成功发出
[ ] 10. 数据库中 email_record 和 reply_record 正确写入
[ ] 11. 第二次轮询不会重复处理同一封邮件
[ ] 12. 登录态过期时能正确检测并暂停
```

---

## 十四、开发计划细化

### Day 1：环境搭建 + 登录 + 邮件读取

| 序号 | 任务 | 产出 | 验收标准 |
|------|------|------|----------|
| 1.1 | 搭建项目骨架 | 目录结构 + requirements.txt | `pip install` 成功 |
| 1.2 | 编写 config.yaml + 配置加载 | `config/loader.py` | 配置校验通过 |
| 1.3 | 实现 login.py | `login.py` | 能保存 state.json |
| 1.4 | 实现浏览器上下文管理 | `browser/context_manager.py` | 能加载 state.json |
| 1.5 | 实现收件箱导航 + 邮件列表获取 | `monitor/inbox_checker.py` (部分) | 日志显示获取到邮件列表 |
| 1.6 | 实现选择器配置 + 回退查找 | `browser/selectors.py` + `selector_helper.py` | 选择器命中率 > 90% |

### Day 2：邮件提取 + AI 回复

| 序号 | 任务 | 产出 | 验收标准 |
|------|------|------|----------|
| 2.1 | 实现发件人/主题/正文提取 | `_extract_sender/subject/body` | 提取内容正确 |
| 2.2 | 实现 mail_uid 提取 | `_extract_mail_uid` | 每封邮件 uid 唯一 |
| 2.3 | 实现正文清洗 | `monitor/content_extractor.py` | 去除引用/签名 |
| 2.4 | 实现发件人匹配 | `monitor/sender_matcher.py` | 正则匹配正确 |
| 2.5 | 实现 AI 适配器 | `ai/` 全部模块 | 能调用 API 返回回复 |
| 2.6 | 编写单元测试 | `tests/` | 核心逻辑测试通过 |

### Day 3：回复发送

| 序号 | 任务 | 产出 | 验收标准 |
|------|------|------|----------|
| 3.1 | 实现回复按钮点击 | `browser/reply_sender.py` (部分) | 回复编辑器弹出 |
| 3.2 | 实现 contenteditable 输入 | `_input_content` | 回复内容正确填入 |
| 3.3 | 实现发送 + 验证 | `_verify_sent` | 邮件成功发出 |
| 3.4 | 错误处理与重试 | 异常处理 | 发送失败时记录错误 |

### Day 4：数据库 + 日志 + 定时任务

| 序号 | 任务 | 产出 | 验收标准 |
|------|------|------|----------|
| 4.1 | 数据库建表 + 索引 | `db/init_db.sql` | 表结构正确 |
| 4.2 | 实现数据操作层 | `db/models.py` | CRUD 正常 |
| 4.3 | 实现连接池 | `db/connection.py` | 连接复用正常 |
| 4.4 | 配置日志系统 | `utils/logger_setup.py` | 日志正确输出 |
| 4.5 | 实现定时任务入口 | `main.py` | 每分钟触发 |
| 4.6 | 实现并发控制 | APScheduler 配置 | 无重叠执行 |
| 4.7 | 实现登录态检测 | `browser/auth_checker.py` | 过期能检测 |

### Day 5：端到端测试 + 上线

| 序号 | 任务 | 产出 | 验收标准 |
|------|------|------|----------|
| 5.1 | 端到端冒烟测试 | 测试报告 | 13 项全部通过 |
| 5.2 | 修复测试发现的问题 | 代码修复 | 问题解决 |
| 5.3 | 编写部署文档 | 部署指南 | 按文档能独立部署 |
| 5.4 | 生产环境部署 | 运行中的系统 | 稳定运行 24h |
| 5.5 | 监控告警配置 | 告警规则 | 异常时能通知 |

---

## 十五、关键风险应对补充

| 风险 | 概率 | 影响 | 应对方案 |
|------|------|------|----------|
| Outlook Web DOM 变更导致选择器失效 | 高 | 高 | 选择器配置化 + 多级回退 + 启动时选择器健康检查 + 告警 |
| 登录态过期（Cookie/Token 失效） | 中 | 高 | 运行时检测 + 自动暂停 + 告警通知 + 人工重新登录 |
| contenteditable 输入失败 | 中 | 高 | 三级策略：keyboard.type → evaluate innerHTML → 逐字输入 |
| AI 接口超时/限流 | 中 | 中 | 重试 3 次 + 间隔递增 + 失败记录到 DB |
| 重复回复 | 低 | 高 | DB UNIQUE 索引 + max_instances=1 + 处理前查询 |
| Outlook 检测自动化 | 中 | 高 | slow_mo 模拟人工 + headed 模式 + 合理轮询间隔 |
| 邮件正文过长导致 AI 上下文溢出 | 中 | 低 | 正文截断（12000 字符）+ 摘要提取 |
| state.json 被覆盖 | 低 | 高 | 文件权限控制 + 备份机制 + 更新时间检测 |

---

## 十六、反自动化检测应对

Outlook Web 可能通过以下方式检测自动化：

1. **navigator.webdriver 标记** — Playwright 默认会设置此标记
2. **鼠标行为模式** — 完全规则的点击坐标
3. **操作速度** — 过快的操作节奏
4. **浏览器指纹** — User-Agent、屏幕分辨率等

### 应对措施

```python
# browser/stealth.py
"""反检测脚本：在页面加载前注入，隐藏自动化标记"""

STEALTH_SCRIPT = """
// 移除 webdriver 标记
Object.defineProperty(navigator, 'webdriver', { get: () => undefined });

// 伪造 plugins
Object.defineProperty(navigator, 'plugins', {
    get: () => [1, 2, 3, 4, 5],
});

// 伪造 languages
Object.defineProperty(navigator, 'languages', {
    get: () => ['zh-CN', 'zh', 'en'],
});
"""

def apply_stealth(context):
    """在所有新页面加载前注入反检测脚本"""
    context.add_init_script(STEALTH_SCRIPT)
```

在 `context_manager.py` 中调用：

```python
def new_context(self, state_file: str = None) -> BrowserContext:
    # ... 原有代码 ...
    context = self._browser.new_context(**kwargs)
    apply_stealth(context)  # 注入反检测脚本
    return context
```

---

## 十七、完整项目目录结构（V2）

```
email-auto-reply/
├── config.yaml                  # 主配置文件
├── config.yaml.example          # 配置模板（提交到 git）
├── .env.example                 # 环境变量模板
├── .env                         # 环境变量（gitignore）
├── .gitignore
├── requirements.txt
├── main.py                      # 入口：启动定时任务
├── login.py                     # 一次性登录脚本
├── README.md
│
├── config/
│   ├── __init__.py
│   └── loader.py                # 配置加载与校验
│
├── browser/
│   ├── __init__.py
│   ├── context_manager.py       # 浏览器上下文管理
│   ├── auth_checker.py          # 登录态校验
│   ├── selectors.py             # Outlook Web 选择器配置
│   ├── selector_helper.py       # 多级回退选择器工具
│   ├── reply_sender.py          # 回复发送（contenteditable 输入）
│   └── stealth.py               # 反自动化检测
│
├── monitor/
│   ├── __init__.py
│   ├── inbox_checker.py         # 收件箱轮询核心逻辑
│   ├── sender_matcher.py        # 发件人规则匹配
│   ├── content_extractor.py     # 邮件正文清洗
│   └── health_check.py          # 系统健康检查
│
├── ai/
│   ├── __init__.py
│   ├── base.py                  # AIAdapter 抽象基类 + 重试逻辑
│   ├── openai_adapter.py        # OpenAI/DeepSeek/Qwen 适配
│   ├── ollama_adapter.py        # Ollama 本地模型适配
│   └── adapter_factory.py       # 适配器工厂
│
├── db/
│   ├── __init__.py
│   ├── connection.py            # 连接池管理
│   ├── models.py                # 数据操作层
│   └── init_db.sql              # 建表 SQL（含索引）
│
├── utils/
│   ├── __init__.py
│   ├── logger_setup.py          # 日志系统配置
│   └── exceptions.py            # 自定义异常体系
│
├── state/
│   └── outlook_state.json       # 登录状态（gitignore）
│
├── logs/
│   └── app.log                  # 运行日志（gitignore）
│
├── tests/
│   ├── __init__.py
│   ├── test_sender_matcher.py   # 发件人匹配测试
│   ├── test_content_extractor.py # 正文清洗测试
│   ├── test_config_loader.py    # 配置加载测试
│   └── test_e2e.py              # 端到端测试
│
└── docker/
    ├── Dockerfile
    └── docker-compose.yml
```

---

## 十八、.gitignore

```gitignore
# 敏感信息
.env
config.yaml
state/*.json

# 日志
logs/

# Python
__pycache__/
*.pyc
.venv/

# IDE
.idea/
.vscode/
*.swp
```
