# 邮箱自动监控与 AI 自动回复系统（MVP 快速落地版）

---

## 一、项目目标

在**无法接入 IMAP / POP3 / Graph API** 的受限环境下，利用 **Playwright 模拟浏览器操作**，实现以下核心功能：

1. 自动监控 Outlook Web 邮箱
2. 识别指定发件人的来信
3. 提取邮件主题与正文
4. 调用 AI 大模型生成回复内容
5. 自动点击回复并发送
6. 写入 MySQL 处理日志，避免重复回复

---

## 二、MVP 范围（最小可用版本）

| 编号 | 功能点           | 是否纳入 MVP |
|------|-----------------|-------------|
| 1    | 单个 Outlook Web 邮箱监控 | ✅ 是 |
| 2    | 监控指定发件人   | ✅ 是 |
| 3    | 获取邮件主题与正文 | ✅ 是 |
| 4    | 调用 AI 模型生成回复 | ✅ 是 |
| 5    | 自动点击回复并发送 | ✅ 是 |
| 6    | MySQL 记录处理日志 | ✅ 是 |
| 7    | Web 管理后台     | ❌ 暂不实现  |
| 8    | 多邮箱支持       | ❌ 暂不实现  |
| 9    | 人工审核模式     | ❌ 暂不实现  |
| 10   | Redis 任务队列   | ❌ 暂不实现  |

---

## 三、技术选型

| 层次     | 技术方案                           | 说明                         |
|----------|------------------------------------|------------------------------|
| 语言     | Python 3.10+                       | 主开发语言                   |
| 自动化   | Playwright (Python binding)        | 浏览器自动化，模拟人工操作    |
| 数据库   | MySQL 8.x                          | 记录邮件处理日志              |
| AI 接口  | DeepSeek / OpenAI / Qwen / Ollama  | 通过统一适配器切换            |
| 定时任务 | APScheduler 或系统 crontab         | 每分钟轮询收件箱              |
| 部署     | Windows Server 或 Linux 云主机     | Docker 可选                  |
| 前端     | 无（首版暂不实现）                 | —                            |

---

## 四、系统架构

```
定时任务（每分钟）
    │
    ▼
Playwright 加载已保存的浏览器登录状态
    │
    ▼
访问 Outlook Web 收件箱
    │
    ▼
遍历邮件列表 → 检查 mail_uid 是否已处理（查 email_record）
    │
    ├─ 已处理 → 跳过
    │
    └─ 未处理 → 匹配发件人规则（rule 表）
                    │
                    ▼
                提取邮件主题、正文内容
                    │
                    ▼
                AI 生成回复（调用适配器接口）
                    │
                    ▼
                Playwright 点击「回复」→ 粘贴内容 → 点击「发送」
                    │
                    ▼
                写入 email_record + reply_record（MySQL）
```

---

## 五、核心流程（分步说明）

### 步骤 1：人工登录一次邮箱

使用 Playwright 打开 Outlook Web，由人工完成账号密码及二次验证登录。

```python
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    context = browser.new_context()
    page = context.new_page()
    page.goto("https://outlook.live.com")
    # 等待人工完成登录 ...
    input("登录完成后按 Enter 保存状态")
    context.storage_state(path="state.json")
    browser.close()
```

### 步骤 2：保存登录状态文件

将登录态保存至 `state.json`（包含 Cookies 和 localStorage），后续轮询复用。

```python
# state.json 路径在 mailbox 表的 state_file 字段中配置
context.storage_state(path="state.json")
```

### 步骤 3：每分钟检查收件箱

```python
# 使用 APScheduler 定时触发
from apscheduler.schedulers.blocking import BlockingScheduler

scheduler = BlockingScheduler()

@scheduler.scheduled_job('interval', minutes=1)
def check_inbox():
    run_email_monitor()

scheduler.start()
```

### 步骤 4：识别指定发件人邮件

从数据库 `rule` 表读取 `sender_pattern`（支持精确匹配或正则），与收件箱邮件发件人地址进行匹配。

```python
import re

def is_sender_match(sender: str, pattern: str) -> bool:
    return bool(re.search(pattern, sender, re.IGNORECASE))
```

### 步骤 5：提取邮件正文

使用 Playwright 定位并提取邮件 DOM 中的文本内容。

```python
page.click(email_selector)  # 点击打开邮件
subject = page.inner_text(".subject-selector")
body = page.inner_text(".body-selector")
```

### 步骤 6：调用 AI 生成回复

通过统一适配器接口调用大模型：

```python
reply_content = ai_adapter.generate(
    prompt_template=rule.prompt_template,
    email_content=body
)
```

### 步骤 7：写入回复内容并发送

```python
page.click(".reply-button-selector")       # 点击「回复」按钮
reply_box = page.locator(".reply-box")
reply_box.fill(reply_content)              # 填入 AI 生成的回复
page.click(".send-button-selector")        # 点击「发送」
```

### 步骤 8：记录日志，避免重复回复

```python
# 发送成功后写入 MySQL
db.execute("""
    INSERT INTO email_record (mail_uid, sender, subject, content, processed)
    VALUES (%s, %s, %s, %s, 1)
""", (mail_uid, sender, subject, body))

db.execute("""
    INSERT INTO reply_record (email_id, reply_content, status)
    VALUES (%s, %s, 'sent')
""", (email_id, reply_content))
```

---

## 六、数据库设计

### 6.1 表清单

| 表名           | 用途             |
|----------------|-----------------|
| `mailbox`      | 邮箱配置         |
| `rule`         | 监控规则         |
| `email_record` | 邮件记录         |
| `reply_record` | 回复记录         |

### 6.2 建表 SQL

```sql
-- 邮箱配置
CREATE TABLE mailbox (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    email       VARCHAR(255) NOT NULL COMMENT '邮箱地址',
    state_file  VARCHAR(512) NOT NULL COMMENT 'Playwright 登录状态文件路径',
    status      TINYINT DEFAULT 1 COMMENT '是否启用：1=启用，0=禁用',
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 监控规则
CREATE TABLE rule (
    id               INT AUTO_INCREMENT PRIMARY KEY,
    mailbox_id       INT          NOT NULL COMMENT '关联邮箱ID',
    sender_pattern   VARCHAR(255) NOT NULL COMMENT '发件人匹配规则（正则）',
    prompt_template  TEXT         NOT NULL COMMENT 'AI 提示词模板，{email_content} 为占位符',
    auto_send        TINYINT DEFAULT 1 COMMENT '是否自动发送：1=自动，0=人工审核',
    created_at       DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (mailbox_id) REFERENCES mailbox(id)
);

-- 邮件记录
CREATE TABLE email_record (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    mailbox_id  INT          NOT NULL,
    mail_uid    VARCHAR(255) NOT NULL UNIQUE COMMENT '邮件唯一标识（防重复处理）',
    sender      VARCHAR(255) NOT NULL COMMENT '发件人地址',
    subject     VARCHAR(500) COMMENT '邮件主题',
    content     LONGTEXT     COMMENT '邮件正文',
    processed   TINYINT DEFAULT 0 COMMENT '是否已处理：1=已处理',
    received_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (mailbox_id) REFERENCES mailbox(id)
);

-- 回复记录
CREATE TABLE reply_record (
    id            INT AUTO_INCREMENT PRIMARY KEY,
    email_id      INT          NOT NULL COMMENT '关联邮件记录ID',
    reply_content TEXT         NOT NULL COMMENT 'AI 生成的回复内容',
    status        VARCHAR(50)  DEFAULT 'pending' COMMENT 'pending / sent / failed',
    sent_at       DATETIME     COMMENT '实际发送时间',
    error_msg     TEXT         COMMENT '失败时的错误信息',
    FOREIGN KEY (email_id) REFERENCES email_record(id)
);
```

---

## 七、AI 接口适配器设计

### 7.1 统一接口定义

```python
from abc import ABC, abstractmethod

class AIAdapter(ABC):
    @abstractmethod
    def generate(self, prompt_template: str, email_content: str) -> str:
        """
        根据提示词模板和邮件内容生成回复。
        :param prompt_template: 包含 {email_content} 占位符的提示词模板
        :param email_content:   邮件正文
        :return:                AI 生成的回复文本
        """
        pass
```

### 7.2 各模型适配实现

```python
# DeepSeek / OpenAI 兼容接口
class OpenAIAdapter(AIAdapter):
    def __init__(self, api_key: str, base_url: str, model: str):
        from openai import OpenAI
        self.client = OpenAI(api_key=api_key, base_url=base_url)
        self.model = model

    def generate(self, prompt_template: str, email_content: str) -> str:
        prompt = prompt_template.replace("{email_content}", email_content)
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}]
        )
        return response.choices[0].message.content

# Ollama 本地模型
class OllamaAdapter(AIAdapter):
    def __init__(self, base_url: str = "http://localhost:11434", model: str = "llama3"):
        self.base_url = base_url
        self.model = model

    def generate(self, prompt_template: str, email_content: str) -> str:
        import requests
        prompt = prompt_template.replace("{email_content}", email_content)
        resp = requests.post(f"{self.base_url}/api/generate",
                             json={"model": self.model, "prompt": prompt, "stream": False})
        return resp.json()["response"]
```

### 7.3 通过配置切换模型

```python
# config.yaml
ai:
  provider: deepseek   # deepseek / openai / qwen / ollama
  api_key: "sk-xxx"
  base_url: "https://api.deepseek.com/v1"
  model: "deepseek-chat"
```

```python
def get_ai_adapter(config: dict) -> AIAdapter:
    provider = config["ai"]["provider"]
    if provider in ("deepseek", "openai", "qwen"):
        return OpenAIAdapter(config["ai"]["api_key"],
                             config["ai"]["base_url"],
                             config["ai"]["model"])
    elif provider == "ollama":
        return OllamaAdapter(config["ai"].get("base_url", "http://localhost:11434"),
                             config["ai"]["model"])
    raise ValueError(f"Unsupported provider: {provider}")
```

---

## 八、项目目录结构

```
email-auto-reply/
├── config.yaml                  # 配置文件（DB、AI、邮箱等）
├── requirements.txt             # Python 依赖
├── main.py                      # 入口：启动定时任务
├── login.py                     # 一次性登录并保存 state.json
├── monitor/
│   ├── __init__.py
│   ├── inbox_checker.py         # 收件箱轮询逻辑
│   └── sender_matcher.py        # 发件人规则匹配
├── ai/
│   ├── __init__.py
│   ├── base.py                  # AIAdapter 抽象基类
│   ├── openai_adapter.py        # OpenAI / DeepSeek / Qwen 适配
│   └── ollama_adapter.py        # Ollama 本地模型适配
├── browser/
│   ├── __init__.py
│   ├── context_manager.py       # 加载 state.json，管理浏览器上下文
│   └── reply_sender.py          # 自动填写回复并发送
├── db/
│   ├── __init__.py
│   ├── models.py                # 数据库表 ORM / SQL 操作
│   └── init_db.sql              # 建表 SQL
├── state/
│   └── outlook_state.json       # Playwright 登录状态（gitignore）
└── logs/
    └── app.log                  # 运行日志
```

---

## 九、部署方案

### 9.1 依赖安装

```bash
pip install playwright apscheduler pymysql openai pyyaml
playwright install chromium
```

### 9.2 初始化数据库

```bash
mysql -u root -p email_auto_reply < db/init_db.sql
```

### 9.3 首次登录保存状态

```bash
python login.py
```

### 9.4 启动监控服务

```bash
# 直接运行
python main.py

# 或以 Windows 服务方式运行（使用 nssm）
nssm install EmailAutoReply python main.py
nssm start EmailAutoReply
```

### 9.5 Docker（可选）

```dockerfile
FROM python:3.11-slim
RUN apt-get update && apt-get install -y chromium && \
    pip install playwright apscheduler pymysql openai pyyaml && \
    playwright install chromium
COPY . /app
WORKDIR /app
CMD ["python", "main.py"]
```

---

## 十、开发计划

| 天数  | 任务                           | 产出                         |
|-------|-------------------------------|------------------------------|
| Day 1 | 邮箱登录 + 邮件读取            | `login.py` + `inbox_checker.py` |
| Day 2 | AI 回复集成                    | `ai/` 适配器模块             |
| Day 3 | 自动发送回复                   | `browser/reply_sender.py`    |
| Day 4 | MySQL 日志写入                 | `db/` 模块 + SQL             |
| Day 5 | 端到端测试 + 上线              | 完整流程验证                 |

---

## 十一、后续优化路线图

| 优先级 | 功能                   | 说明                                     |
|--------|----------------------|------------------------------------------|
| P1     | 多邮箱支持             | `mailbox` 表已设计好，扩展 monitor 即可  |
| P1     | 人工审核模式           | `rule.auto_send=0` 时写入草稿，人工确认后发送 |
| P2     | Web 管理后台           | 规则配置、日志查看、状态监控              |
| P2     | Redis 任务队列         | 解耦定时触发与执行，支持并发处理          |
| P3     | 浏览器池               | 多账号并发，提高吞吐量                   |
| P3     | RAG 知识库             | 结合企业知识库生成更精准的回复            |
| P3     | 企业级权限管理         | 多用户、角色、审计日志                   |

---

## 十二、风险与注意事项

| 风险点                | 说明                                              | 缓解措施                           |
|-----------------------|--------------------------------------------------|-----------------------------------|
| Outlook Web 页面结构变化 | 微软可能随时更新 DOM 结构，导致选择器失效         | 对关键选择器加监控告警，及时修复   |
| 登录状态过期           | `state.json` 在 Token 过期后失效                  | 检测到登录失效时发告警，触发人工重新登录 |
| 重复回复               | 极端情况下可能重复处理同一封邮件                  | `mail_uid` 设唯一索引，DB 层保障幂等性 |
| AI 回复质量            | 生成内容可能不符合预期                            | 初期建议开启人工审核模式（`auto_send=0`）|
| 敏感信息泄露           | 邮件内容中可能包含隐私或机密信息                  | 确保 AI 接口使用私有化部署或企业级 API，不使用公共免费接口 |
