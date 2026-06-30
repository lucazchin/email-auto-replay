-- ============================================
-- 迁移脚本：为 rule 表增加正则回复引擎字段
-- 支持不依赖 AI 的毫秒级正则/表格规则回复
-- 适用场景：抢简历（表格提取姓名）等只需提取关键信息的规则
-- ============================================

USE email_auto_reply;

-- -------------------------------------------
-- 1. rule 表新增正则回复字段
-- -------------------------------------------
ALTER TABLE rule
    ADD COLUMN reply_mode     VARCHAR(10) DEFAULT 'regex' COMMENT '回复模式：regex=正则/表格规则，ai=AI生成' AFTER system_prompt,
    ADD COLUMN reply_pattern  TEXT        DEFAULT NULL     COMMENT '提取模式：table:<表头列名>=从HTML表格指定列提取；其他=标准re.search正则' AFTER reply_mode,
    ADD COLUMN reply_template TEXT        DEFAULT NULL     COMMENT '回复模板：\\1 引用第一个提取值，\\2 第二个（re.Match.expand 语法）' AFTER reply_pattern;

-- -------------------------------------------
-- 2. 更新已有规则：将现有 AI 规则标记为 reply_mode='ai'，保持行为不变
-- -------------------------------------------
UPDATE rule SET reply_mode = 'ai' WHERE reply_mode IS NULL;

-- -------------------------------------------
-- 3. 示例：抢简历规则（从 HTML 表格"姓名"列提取，毫秒级回复，无需 AI）
--    请根据实际 rule_name 或 id 修改 WHERE 条件
-- -------------------------------------------
UPDATE rule
SET reply_mode      = 'regex',
    reply_pattern   = 'table:姓名',           -- 从 HTML 表格中找"姓名"表头，取该列每行值
    reply_template  = '\\1',                  -- 输出第一行的姓名值
    prompt_template = ''                      -- 正则/表格模式不需要 AI prompt
WHERE rule_name = '抢简历';
--
-- 说明：
--   reply_pattern 以 "table:" 开头时，引擎会：
--     1. 用 HTMLParser 解析原始邮件正文中的 <table>
--     2. 在 <th> 行中查找包含 "姓名" 的列
--     3. 提取该列所有数据行（跳过空单元格）
--     4. 用第一个非空值填充模板中的 \1
--   若邮件不是表格格式，会自动回退到标准正则或 AI 回复。
