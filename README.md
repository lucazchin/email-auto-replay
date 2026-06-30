# 邮箱自动监控与 AI 自动回复系统

基于 **EWS (exchangelib)** 纯 API 操作 Exchange 邮箱，支持 AI 智能回复与正则规则引擎双模式。

## 核心特性

- **纯 API 操作**：通过 EWS 协议收发邮件，无需浏览器，延迟 10 秒内
- **双引擎回复**：AI 模式（DeepSeek/OpenAI/Qwen/Ollama）和正则引擎模式（毫秒级，零成本）
- **智能简历提取**：支持 HTML 表格 (`table:姓名`) 和纯文本垂列表 (`text:姓名`) 两种格式自动识别
- **多条件规则匹配**：可按发件人、主题、正文正则组合匹配（AND/OR 逻辑），带优先级排序
- **三重去重**：mail_uid 唯一索引 + 幂等检查 + 发件人+主题二次去重
- **敏感信息保护**：所有凭据通过 `.env` 环境变量注入，代码中无明文密码

## 快速开始

### 1. 安装依赖

```bash
python -m venv .venv
source .venv/bin/activate   # Linux/Mac
# .venv\Scripts\activate    # Windows

pip install -r requirements.txt
```

### 2. 配置

```bash
# 环境变量（必须：所有敏感凭据）
cp .env.example .env
# 编辑 .env，填写数据库密码、AI Key、邮箱凭据

# 主配置（非敏感参数：轮询间隔、日志级别等）
cp config.yaml.example config.yaml
# 编辑 config.yaml，按需调整
```

### 3. 初始化数据库

```bash
mysql -u root -p < db/init_db.sql
```

`init_db.sql` 会自动创建 `email_auto_reply` 库和 4 张表，并插入示例规则。

### 4. 启动监控

```bash
python main.py
```

启动后系统自动连接 Exchange、定时轮询收件箱，匹配规则后执行回复。

## 项目结构

```
email-auto-replay/
├── main.py                    # 入口：EWS 连接 + 定时调度
├── config.yaml                # 主配置（非敏感参数）
├── .env                       # 环境变量（敏感凭据，gitignore）
├── .env.example               # 环境变量模板
├── config.yaml.example        # 配置模板
├── requirements.txt
│
├── config/
│   └── loader.py              # 配置加载器（YAML + .env 合并，必填校验）
│
├── ewser/                     # EWS 模块
│   ├── connection.py          # EWS 连接管理器（单例）
│   └── reply.py               # 回复发送器
│
├── monitor/                   # 监控核心
│   ├── inbox_checker.py       # 收件箱轮询 + 完整处理管道
│   ├── rule_matcher.py        # 多条件规则匹配引擎
│   ├── sender_matcher.py      # 遗留（已委托到 RuleMatcher）
│   └── content_extractor.py   # 正文清洗（去引用、去签名）
│
├── ai/                        # AI 模块
│   ├── base.py                # AI 适配器抽象基类
│   ├── openai_adapter.py      # DeepSeek / OpenAI / Qwen
│   ├── ollama_adapter.py      # Ollama 本地模型
│   ├── adapter_factory.py     # 适配器工厂
│   └── regex_engine.py        # 正则规则回复引擎（无 AI 依赖）
│
├── db/                        # 数据库
│   ├── connection.py          # 连接池（DBUtils + PyMySQL）
│   ├── models.py              # 数据操作层（Mailbox / Rule / EmailRecord / ReplyRecord）
│   ├── init_db.sql            # 建表 + 示例数据
│   ├── migrate_rule_v2.sql    # V2 多条件规则迁移
│   ├── migrate_add_system_prompt.sql
│   ├── migrate_add_regex_reply.sql
│   └── migrate_text_extraction.sql
│
├── utils/
│   ├── logger_setup.py        # 日志系统（loguru）
│   └── exceptions.py          # 自定义异常体系
│
├── logs/                      # 运行日志（gitignore）
├── state/                     # 登录状态（gitignore，EWS 版不使用）
├── tests/                     # 测试
│
└── browser/                   # 遗留：Playwright/OWA 代码（不再被 main.py 引用）
```

## 配置说明

### 环境变量（`.env`）

| 变量 | 说明 | 必填 |
|------|------|:---:|
| `DB_PASSWORD` | MySQL 密码 | ✅ |
| `AI_API_KEY` | DeepSeek / OpenAI API Key | ✅ |
| `EWS_EMAIL` | 邮箱账号 | ✅ |
| `EWS_PASSWORD` | 邮箱密码 | ✅ |
| `EWS_SERVER` | Exchange 服务器地址 | ✅ |

环境变量优先级高于 `config.yaml` 中的同名字段。

### config.yaml

| 配置段 | 关键参数 | 说明 |
|--------|---------|------|
| `database` | host, port, user, database, pool_size | MySQL 连接（密码通过 DB_PASSWORD 环境变量） |
| `ai` | provider, model, max_tokens, temperature | AI 模型参数（API Key 通过 AI_API_KEY 环境变量） |
| `ews` | max_emails_per_run | 单次轮询最大处理数（凭据通过环境变量） |
| `scheduler` | interval_seconds | 轮询间隔（秒），默认 1 |
| `logging` | level, dir, rotation, retention | 日志配置 |
| `alert` | enabled, webhook_url | 告警通知（可选） |

## 数据库

### 表结构

| 表名 | 用途 | 关键字段 |
|------|------|---------|
| `mailbox` | 邮箱配置 | email, status |
| `rule` | 监控规则 | sender_pattern, subject_pattern, content_pattern, match_logic, priority, reply_mode, reply_pattern, reply_template, system_prompt, auto_send |
| `email_record` | 邮件记录 | mail_uid (UNIQUE), sender, subject |
| `reply_record` | 回复记录 | reply_content, status (pending/sent/failed) |

### 规则字段说明

| 字段 | 说明 |
|------|------|
| `sender_pattern` | 发件人正则（匹配 "显示名 \<邮箱\>"、纯邮箱、纯显示名） |
| `subject_pattern` | 主题正则 |
| `content_pattern` | 正文正则 |
| `match_logic` | 匹配逻辑：`AND`（全部满足）或 `OR`（任一满足） |
| `priority` | 优先级（越小越高），命中后不再继续匹配 |
| `reply_mode` | 回复模式：`regex`（正则引擎）或 `ai`（AI 生成） |
| `reply_pattern` | 正则提取模式：`table:<表头>` / `text:<表头>` / 普通正则 |
| `reply_template` | 回复模板，`\1` 为匹配结果占位符 |
| `system_prompt` | 自定义 AI System Prompt（仅 AI 模式，NULL 使用默认值） |
| `auto_send` | 是否自动发送（0=仅记录不发送） |

## 运行流程

```
定时触发 (interval_seconds)
  │
  ├─ 查询启用邮箱 (mailbox.status=1)
  │
  ├─ 遍历未读邮件 (filter is_read=False, limit max_emails)
  │
  ├─ 仅处理最新一封（抢简历场景：抢最新到达）
  │
  ├─ 三重去重检查
  │   ├── mail_uid 唯一索引
  │   ├── is_processed() 幂等判断
  │   └── 发件人+主题二次去重（剥离 Re:/Fwd: 前缀）
  │
  ├─ 规则匹配 (按 priority 升序，第一条命中即停止)
  │
  ├─ 正文清洗 (HTML→文本 → 去引用 → 去签名 → 压缩空白)
  │
  ├─ 回复生成
  │   ├── reply_mode=regex → RegexReplyEngine
  │   │   ├── table:<表头> → HTML 表格列提取 → 失败回退 text 模式
  │   │   ├── text:<表头>  → 纯文本垂列表提取 → 失败回退 table 模式
  │   │   └── 普通正则     → re.search + match.expand
  │   │   └── 全部失败     → 静默跳过，不回复
  │   │
  │   └── reply_mode=ai → AI Adapter
  │       ├── 替换 {email_content} 占位符
  │       ├── 超过 12000 字符自动截断
  │       └── 最多重试 retry_times 次
  │
  ├─ 入库 (INSERT IGNORE email_record + INSERT reply_record)
  │
  ├─ 发送回复 (auto_send=1 → EWSReplySender)
  │
  └─ 标记已读 (message.is_read = True)
```

## 回复引擎

### AI 模式

支持四种后端：`deepseek` / `openai` / `qwen`（共用 OpenAIAdapter）和 `ollama`（本地模型）。

AI 模式下规则可自定义 `system_prompt`，不设置则使用默认 System Prompt。

### 正则引擎（毫秒级，零 API 成本）

无需调用 AI，通过正则从邮件中提取结构化信息后按模板生成回复。

内置三种提取模式：

**1. HTML 表格模式 (`table:<表头>`)**
```
reply_pattern: "table:姓名"
```
解析 HTML `<table>` 标签，按表头关键字定位列，提取该列所有数据行。适用于标准表格简历。

**2. 纯文本模式 (`text:<表头>`)**
```
reply_pattern: "text:姓名"
```
解析纯文本垂列表格式，多策略提取（块对齐 → 日期-姓名模式 → 单行兜底）。适用于无 HTML 表格的简历。

**3. 标准正则模式**
```
reply_pattern: "(\d{1,2}/\d{1,2}[\s\S]*?)(?=\d{1,2}/\d{1,2}|$)"
reply_template: "\1"
```
使用 Python `re` 模块的标准正则匹配和模板展开。

> 注：`table` 和 `text` 模式会自动互相回退——当一种模式提取失败时，引擎自动尝试另一种，无需手动切换。

## 常见问题

### Exchange 连接失败

确认 `.env` 中的 `EWS_EMAIL`、`EWS_PASSWORD`、`EWS_SERVER` 正确。可使用工作区中的 `verify_ews.py` 验证连接：
```bash
python verify_ews.py
```

### 规则不生效

1. 检查规则 `enabled` 是否为 1
2. 检查 `sender_pattern` 是否匹配实际发件人格式（"显示名 \<邮箱\>"）
3. 多个规则时，被高优先级规则（priority 值小）拦截

### 正则引擎未提取到内容

1. 确认邮件正文包含表格或垂列表
2. `table` 模式需要邮件为 HTML 格式；`text` 模式需要换行保留（`text_body` 存在）
3. 查看日志确认引擎走到了哪个分支

### 同一封邮件被重复处理

三种去重机制会自动拦截：
- `mail_uid` 基于 Exchange `message_id`，全局唯一
- 相同发件人+主题（去除 `Re: ` 前缀）生成过回复不再重复处理
- 如仍有问题，检查 `email_record` 表 `mail_uid` 是否正确写入
