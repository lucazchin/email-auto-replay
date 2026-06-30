-- ============================================
-- 规则表升级脚本：从仅匹配发件人 → 多条件匹配
-- 支持发件人 + 主题 + 正文关键词，AND/OR 逻辑组合，优先级排序
-- ============================================

USE email_auto_reply;

-- -------------------------------------------
-- 1. rule 表新增字段
-- -------------------------------------------
ALTER TABLE rule
    ADD COLUMN subject_pattern  VARCHAR(512) DEFAULT NULL COMMENT '主题匹配规则（正则，NULL 表示不限制）' AFTER sender_pattern,
    ADD COLUMN content_pattern  VARCHAR(512) DEFAULT NULL COMMENT '正文关键词匹配（正则，NULL 表示不限制）' AFTER subject_pattern,
    ADD COLUMN match_logic      VARCHAR(10)  DEFAULT 'AND' COMMENT '多条件组合逻辑：AND=全部满足，OR=任一满足' AFTER content_pattern,
    ADD COLUMN priority         INT          DEFAULT 100 COMMENT '优先级，数字小的先匹配（同优先级按 id）' AFTER match_logic,
    ADD COLUMN enabled          TINYINT      DEFAULT 1 COMMENT '是否启用：1=启用，0=禁用' AFTER priority,
    ADD COLUMN rule_name        VARCHAR(100) DEFAULT NULL COMMENT '规则名称（便于管理）' AFTER mailbox_id;

-- -------------------------------------------
-- 2. 调整字段注释和默认值
-- -------------------------------------------
ALTER TABLE rule
    MODIFY COLUMN sender_pattern VARCHAR(255) DEFAULT NULL COMMENT '发件人匹配规则（正则，NULL 表示不限制）';

-- -------------------------------------------
-- 3. 增加索引
-- -------------------------------------------
ALTER TABLE rule
    ADD INDEX idx_mailbox_enabled_priority (mailbox_id, enabled, priority);

-- -------------------------------------------
-- 4. 迁移已有规则：把默认规则改为新格式
-- -------------------------------------------
UPDATE rule
SET rule_name    = '默认规则-公司内部邮件',
    subject_pattern = NULL,           -- 不限制主题
    content_pattern = NULL,           -- 不限制正文
    match_logic  = 'AND',
    priority     = 100,
    enabled      = 1
WHERE rule_name IS NULL;

-- -------------------------------------------
-- 5. 示例：插入多条新规则（按需启用，先注释掉以免影响现有数据）
-- -------------------------------------------
-- 规则1：老板的邮件，优先级最高，人工审核
-- INSERT INTO rule (mailbox_id, rule_name, sender_pattern, subject_pattern, content_pattern,
--                   match_logic, priority, prompt_template, auto_send, enabled)
-- VALUES (1, '领导邮件-人工审核',
--         'boss@hengtiansoft\\.com', NULL, NULL,
--         'AND', 1,
--         '这是来自领导的邮件，请生成一封正式、恭敬的回复：\n{email_content}',
--         0, 1);

-- 规则2：主题含"紧急"，任何发件人，优先级高
-- INSERT INTO rule (mailbox_id, rule_name, sender_pattern, subject_pattern, content_pattern,
--                   match_logic, priority, prompt_template, auto_send, enabled)
-- VALUES (1, '紧急邮件-快速响应',
--         NULL, '紧急|urgent|ASAP', NULL,
--         'AND', 10,
--         '这是一封紧急邮件，请生成简短、直接的回复，优先提供解决方案：\n{email_content}',
--         1, 1);

-- 规则3：正文提到"会议"+主题提到"邀请"（AND 逻辑）
-- INSERT INTO rule (mailbox_id, rule_name, sender_pattern, subject_pattern, content_pattern,
--                   match_logic, priority, prompt_template, auto_send, enabled)
-- VALUES (1, '会议邀请-确认参加',
--         NULL, '邀请|invite', '会议|meeting|schedule',
--         'AND', 20,
--         '收到会议邀请邮件，请生成一封确认参加的回复：\n{email_content}\n请确认时间地点，并表示会准时参加。',
--         1, 1);

-- 规则4：外部客户邮件（Gmail/163/Outlook），主题或正文含"咨询"
-- INSERT INTO rule (mailbox_id, rule_name, sender_pattern, subject_pattern, content_pattern,
--                   match_logic, priority, prompt_template, auto_send, enabled)
-- VALUES (1, '外部客户咨询',
--         '.*@(gmail|163|outlook)\\.com', '咨询|问|question', NULL,
--         'AND', 30,
--         '收到外部客户咨询，请生成专业、礼貌的中文回复：\n{email_content}',
--         1, 1);

-- 规则5：兜底规则，匹配所有邮件（优先级最低）
-- INSERT INTO rule (mailbox_id, rule_name, sender_pattern, subject_pattern, content_pattern,
--                   match_logic, priority, prompt_template, auto_send, enabled)
-- VALUES (1, '兜底-通用回复',
--         '.*', NULL, NULL,
--         'AND', 999,
--         '请根据以下邮件生成一封专业、简洁的回复：\n{email_content}',
--         1, 1);
