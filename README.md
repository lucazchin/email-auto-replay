# 邮箱自动监控与 AI 自动回复系统

基于 Playwright 模拟浏览器操作，在无法接入 IMAP/POP3/Graph API 的受限环境下，实现 Exchange OWA 邮箱自动监控与 AI 回复。

## 快速开始

### 1. 安装依赖

```bash
# 创建虚拟环境
python -m venv .venv

# Windows
.venv\Scripts\activate
# Linux/Mac
source .venv/bin/activate

# 安装依赖
pip install -r requirements.txt

# 安装 Playwright 浏览器
playwright install chromium
```

### 2. 配置

```bash
# 复制配置模板
copy config.yaml.example config.yaml    # Windows
cp config.yaml.example config.yaml      # Linux

# 编辑 config.yaml，填写数据库和 AI 配置

# 复制环境变量模板
copy .env.example .env                  # Windows
cp .env.example .env                    # Linux

# 编辑 .env，填写密码
```

### 3. 初始化数据库

```bash
mysql -u root -p < db/init_db.sql
```

### 4. 首次登录

支持两种模式：

**自动登录模式（推荐）**：在 `.env` 中配置 `OWA_USERNAME` 和 `OWA_PASSWORD`，并在 `config.yaml` 中设置 `owa.credentials.enabled: true`：

```bash
python login.py
# 系统自动填入账号密码登录，检测到 MFA 时回退人工模式
```

**人工登录模式**：不配置凭据或设置 `owa.credentials.enabled: false`：

```bash
python login.py
# 浏览器会打开，手动完成登录后按 Enter 保存状态
```

### 5. 启动监控

```bash
python main.py
# 启动时自动校验登录态，过期则自动重新登录
# 运行中检测到登录态过期也会自动重登（无需人工介入）
```

## 项目结构

```
email-auto-replay/
├── config.yaml              # 主配置（从 .example 复制）
├── .env                     # 环境变量（从 .example 复制）
├── requirements.txt
├── main.py                  # 入口：启动定时任务
├── login.py                 # 一次性登录脚本
├── config/
│   └── loader.py            # 配置加载与校验
├── browser/
│   ├── context_manager.py   # 浏览器上下文管理
│   ├── auth_checker.py      # 登录态校验
│   ├── auto_login.py        # 自动登录模块（账号密码 + MFA 兜底）
│   ├── selectors.py         # OWA 选择器配置
│   ├── selector_helper.py   # 多级回退选择器工具
│   ├── reply_sender.py      # 回复发送（contenteditable 输入）
│   └── stealth.py           # 反自动化检测
├── monitor/
│   ├── inbox_checker.py     # 收件箱轮询核心逻辑
│   ├── sender_matcher.py    # 发件人规则匹配
│   ├── content_extractor.py # 邮件正文清洗
│   └── health_check.py      # 系统健康检查
├── ai/
│   ├── base.py              # AI 适配器基类 + 重试
│   ├── openai_adapter.py    # DeepSeek/OpenAI/Qwen 适配
│   ├── ollama_adapter.py    # Ollama 本地模型适配
│   └── adapter_factory.py   # 适配器工厂
├── db/
│   ├── connection.py        # 连接池管理
│   ├── models.py            # 数据操作层
│   └── init_db.sql          # 建表 SQL
├── utils/
│   ├── logger_setup.py      # 日志系统配置
│   └── exceptions.py        # 自定义异常
├── state/                   # 登录状态（gitignore）
├── logs/                    # 运行日志（gitignore）
└── tests/                   # 测试
```

## 配置说明

### config.yaml 关键配置

| 配置项 | 说明 |
|--------|------|
| `owa.url` | OWA 邮箱地址（默认: mail.hengtiansoft.com） |
| `owa.state_file` | 登录状态文件路径 |
| `owa.credentials.enabled` | 是否启用自动登录 |
| `owa.credentials.username` | 邮箱账号（建议用环境变量 OWA_USERNAME） |
| `owa.credentials.password` | 邮箱密码（建议用环境变量 OWA_PASSWORD） |
| `owa.credentials.mfa_fallback` | 检测到 MFA 时回退人工处理 |
| `ai.provider` | AI 模型（deepseek/openai/qwen/ollama） |
| `scheduler.interval_minutes` | 轮询间隔（分钟） |
| `browser.headless` | 是否无头模式（调试时建议 false） |

### 数据库表

| 表名 | 用途 |
|------|------|
| `mailbox` | 邮箱配置 |
| `rule` | 监控规则（发件人正则 + AI 提示词） |
| `email_record` | 邮件记录（含 mail_uid 唯一标识防重复） |
| `reply_record` | 回复记录（pending/sent/failed） |

## 运行流程

```
每分钟定时触发
    → 加载已保存的登录状态
    → 访问 OWA 收件箱
    → 遍历邮件列表
    → 检查 mail_uid 是否已处理
    → 匹配发件人规则
    → 提取邮件主题+正文
    → AI 生成回复
    → 点击回复 → 输入内容 → 发送
    → 写入 MySQL 日志
```

## 常见问题

### 登录态过期

系统支持自动登录时无需人工介入：
1. 启动时自动检测登录态，过期则自动重新登录
2. 运行中每 10 分钟主动校验一次登录态
3. 自动登录失败（凭据错误等）会暂停监控并告警，需人工处理

如未配置自动登录，运行日志出现 "登录态已过期" 时：
1. 重新运行 `python login.py`
2. 完成登录后系统会自动恢复监控

### 选择器失效

OWA 页面更新可能导致选择器失效。所有选择器集中在 `browser/selectors.py`，每个元素有多级回退。如全部失效，使用浏览器开发者工具检查新的 DOM 结构并更新选择器。

### 回复输入失败

OWA 回复框是 contenteditable div，不能使用 fill()。系统使用三级策略：keyboard.type → evaluate innerHTML → 逐字输入。如仍有问题，检查 `browser/reply_sender.py`。
