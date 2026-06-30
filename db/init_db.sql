-- ============================================
-- 邮箱自动回复系统 - 建表脚本
-- 数据库: email_auto_reply
-- ============================================

CREATE DATABASE IF NOT EXISTS email_auto_reply
    DEFAULT CHARACTER SET utf8mb4
    DEFAULT COLLATE utf8mb4_unicode_ci;

USE email_auto_reply;

-- -------------------------------------------
-- 邮箱配置表
-- -------------------------------------------
CREATE TABLE IF NOT EXISTS mailbox (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    email       VARCHAR(255) NOT NULL COMMENT '邮箱地址',
    state_file  VARCHAR(512) NOT NULL COMMENT 'Playwright 登录状态文件路径',
    status      TINYINT DEFAULT 1 COMMENT '是否启用：1=启用，0=禁用',
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at  DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='邮箱配置';

-- -------------------------------------------
-- 监控规则表（V2：多条件匹配）
-- -------------------------------------------
CREATE TABLE IF NOT EXISTS rule (
    id               INT AUTO_INCREMENT PRIMARY KEY,
    mailbox_id       INT          NOT NULL COMMENT '关联邮箱ID',
    rule_name        VARCHAR(100) DEFAULT NULL COMMENT '规则名称（便于管理）',
    sender_pattern   VARCHAR(255) DEFAULT NULL COMMENT '发件人匹配规则（正则，NULL=不限制）',
    subject_pattern  VARCHAR(512) DEFAULT NULL COMMENT '主题匹配规则（正则，NULL=不限制）',
    content_pattern  VARCHAR(512) DEFAULT NULL COMMENT '正文关键词匹配（正则，NULL=不限制）',
    match_logic      VARCHAR(10)  DEFAULT 'AND' COMMENT '多条件组合逻辑：AND=全部满足，OR=任一满足',
    priority         INT          DEFAULT 100 COMMENT '优先级，数字小的先匹配',
    prompt_template  TEXT         NOT NULL COMMENT 'AI 提示词模板，{email_content} 为占位符',
    system_prompt    TEXT         DEFAULT NULL COMMENT '自定义 System Prompt（NULL=使用默认值）',
    reply_mode       VARCHAR(10)  DEFAULT 'regex' COMMENT '回复模式：regex=正则规则，ai=AI生成',
    reply_pattern    TEXT         DEFAULT NULL COMMENT '正则提取模式（reply_mode=regex 时，匹配主题+正文）',
    reply_template   TEXT         DEFAULT NULL COMMENT '正则回复模板，\\1 \\2 引用捕获组（仅限96字符）',
    auto_send        TINYINT DEFAULT 1 COMMENT '是否自动发送：1=自动，0=人工审核',
    enabled          TINYINT DEFAULT 1 COMMENT '是否启用：1=启用，0=禁用',
    created_at       DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (mailbox_id) REFERENCES mailbox(id) ON DELETE CASCADE,
    INDEX idx_mailbox_enabled_priority (mailbox_id, enabled, priority)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='监控规则';

-- -------------------------------------------
-- 邮件记录表
-- -------------------------------------------
CREATE TABLE IF NOT EXISTS email_record (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    mailbox_id  INT          NOT NULL,
    mail_uid    VARCHAR(255) NOT NULL UNIQUE COMMENT '邮件唯一标识（防重复处理）',
    sender      VARCHAR(255) NOT NULL COMMENT '发件人地址',
    subject     VARCHAR(500) COMMENT '邮件主题',
    content     LONGTEXT     COMMENT '邮件正文',
    processed   TINYINT DEFAULT 0 COMMENT '是否已处理：1=已处理，0=未处理',
    received_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (mailbox_id) REFERENCES mailbox(id) ON DELETE CASCADE,
    INDEX idx_mailbox_processed (mailbox_id, processed),
    INDEX idx_received_at (received_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='邮件记录';

-- -------------------------------------------
-- 回复记录表
-- -------------------------------------------
CREATE TABLE IF NOT EXISTS reply_record (
    id            INT AUTO_INCREMENT PRIMARY KEY,
    email_id      INT          NOT NULL COMMENT '关联邮件记录ID',
    reply_content TEXT         NOT NULL COMMENT 'AI 生成的回复内容',
    status        VARCHAR(50)  DEFAULT 'pending' COMMENT 'pending / sent / failed',
    sent_at       DATETIME     COMMENT '实际发送时间',
    error_msg     TEXT         COMMENT '失败时的错误信息',
    created_at    DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (email_id) REFERENCES email_record(id) ON DELETE CASCADE,
    INDEX idx_email_id (email_id),
    INDEX idx_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='回复记录';

-- -------------------------------------------
-- 初始化数据示例（按需修改）
-- -------------------------------------------
-- 插入邮箱配置
INSERT INTO mailbox (email, state_file, status) VALUES
    ('your-email@hengtiansoft.com', 'state/owa_state.json', 1);

-- 插入监控规则示例（多条件匹配）
INSERT INTO rule (mailbox_id, rule_name, sender_pattern, subject_pattern, content_pattern,
                   match_logic, priority, prompt_template, reply_mode, reply_pattern, reply_template, auto_send, enabled) VALUES
    -- 规则1：公司内部邮件，通用 AI 回复
    (1, '公司内部邮件-通用', '.*@hengtiansoft\\.com', NULL, NULL,
     'AND', 100,
     '你收到一封公司内部邮件，请根据以下邮件内容生成一封专业、简洁的回复：\n\n---邮件内容---\n{email_content}\n---邮件内容结束---\n\n请直接输出回复正文，不要包含主题行。',
     'ai', NULL, NULL,
     1, 1),

    -- 规则2：抢简历-从 HTML 表格"姓名"列提取，毫秒级回复（无需 AI）
    (1, '抢简历', '.*', '(?:应聘|简历|求职|申请)', NULL,
     'AND', 1,
     '',
     'regex', 'table:姓名',
     '\\1',
     1, 1);
