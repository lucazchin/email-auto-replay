-- ============================================
-- 迁移脚本：为 rule 表添加 system_prompt 字段
-- 允许每条规则自定义 System Prompt，覆盖默认值
-- ============================================

USE email_auto_reply;

-- -------------------------------------------
-- 1. rule 表新增 system_prompt 字段
-- -------------------------------------------
ALTER TABLE rule
    ADD COLUMN system_prompt TEXT DEFAULT NULL COMMENT '自定义 System Prompt（NULL=使用默认值）' AFTER prompt_template;

-- -------------------------------------------
-- 2. 示例：更新"抢简历"规则 —— 只回复姓名
-- （请根据实际 rule.id 修改 WHERE 条件）
-- -------------------------------------------
-- UPDATE rule
-- SET system_prompt = '你是一个简历收发助手。你的任务是从邮件中提取应聘者的姓名，然后只回复姓名本身——不要打招呼、不要标题、不要任何其他内容。'
-- WHERE rule_name = '抢简历';
--
-- -- 同时也更新 prompt_template，让 AI 专注提取姓名：
-- UPDATE rule
-- SET prompt_template = '请从以下邮件内容中提取应聘者的姓名，只输出姓名：\n\n---邮件内容---\n{email_content}\n---邮件内容结束---\n\n只输出姓名，不要其他任何内容。'
-- WHERE rule_name = '抢简历';
