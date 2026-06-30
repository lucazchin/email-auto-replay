-- 将简历规则的提取模式从 HTML 表格改为纯文本垂列表
-- 因为实际邮件是纯文本格式，不是 HTML <table>

UPDATE rule
SET reply_pattern = 'text:姓名'
WHERE reply_pattern = 'table:姓名'
  AND reply_mode = 'regex';

-- 验证更新结果
SELECT id, rule_name, reply_mode, reply_pattern, reply_template
FROM rule
WHERE reply_mode = 'regex';
