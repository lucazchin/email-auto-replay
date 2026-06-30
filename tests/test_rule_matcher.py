"""
RuleMatcher 多条件规则匹配引擎测试。
覆盖：单条件、多条件 AND/OR、优先级、禁用规则、正则错误、向后兼容。
"""
import pytest
from monitor.rule_matcher import RuleMatcher, SenderMatcher


def make_rule(rule_id=1, sender_pattern=None, subject_pattern=None,
              content_pattern=None, match_logic="AND", priority=100,
              enabled=1, rule_name="test_rule", prompt_template="reply {email_content}",
              auto_send=1):
    """构造测试用规则 dict。"""
    return {
        "id": rule_id,
        "rule_name": rule_name,
        "sender_pattern": sender_pattern,
        "subject_pattern": subject_pattern,
        "content_pattern": content_pattern,
        "match_logic": match_logic,
        "priority": priority,
        "enabled": enabled,
        "prompt_template": prompt_template,
        "auto_send": auto_send,
    }


class TestNoConditions:
    """没有任何条件的规则应该匹配所有邮件。"""

    def test_no_conditions_matches_all(self):
        rule = make_rule(sender_pattern=None, subject_pattern=None, content_pattern=None)
        assert RuleMatcher.match("anyone@x.com", "any subject", "any body", [rule]) is not None

    def test_empty_rules_list(self):
        assert RuleMatcher.match("a@b.com", "s", "b", []) is None


class TestSenderOnly:
    """仅配置发件人条件。"""

    def test_sender_match(self):
        rule = make_rule(sender_pattern=r".*@hengtiansoft\.com")
        assert RuleMatcher.match("alice@hengtiansoft.com", "hi", "body", [rule]) is not None

    def test_sender_no_match(self):
        rule = make_rule(sender_pattern=r".*@hengtiansoft\.com")
        assert RuleMatcher.match("alice@gmail.com", "hi", "body", [rule]) is None

    def test_sender_exact(self):
        rule = make_rule(sender_pattern=r"^boss@hengtiansoft\.com$")
        assert RuleMatcher.match("boss@hengtiansoft.com", "", "", [rule]) is not None
        assert RuleMatcher.match("alice@hengtiansoft.com", "", "", [rule]) is None

    def test_case_insensitive(self):
        rule = make_rule(sender_pattern=r"alice")
        assert RuleMatcher.match("ALICE@example.com", "", "", [rule]) is not None
        assert RuleMatcher.match("Alice@example.com", "", "", [rule]) is not None


class TestSubjectOnly:
    """仅配置主题条件。"""

    def test_subject_match(self):
        rule = make_rule(subject_pattern=r"紧急|urgent")
        assert RuleMatcher.match("a@b.com", "紧急通知", "body", [rule]) is not None

    def test_subject_no_match(self):
        rule = make_rule(subject_pattern=r"紧急")
        assert RuleMatcher.match("a@b.com", "普通通知", "body", [rule]) is None

    def test_subject_partial_match(self):
        rule = make_rule(subject_pattern=r"报价")
        assert RuleMatcher.match("a@b.com", "关于产品报价单的咨询", "body", [rule]) is not None


class TestContentOnly:
    """仅配置正文条件。"""

    def test_content_match(self):
        rule = make_rule(content_pattern=r"会议|meeting")
        assert RuleMatcher.match("a@b.com", "sub", "明天开会讨论会议安排", [rule]) is not None

    def test_content_no_match(self):
        rule = make_rule(content_pattern=r"会议")
        assert RuleMatcher.match("a@b.com", "sub", "今天天气不错", [rule]) is None


class TestAndLogic:
    """AND 逻辑：所有非 NULL 条件都满足才命中。"""

    def test_and_all_match(self):
        rule = make_rule(
            sender_pattern=r".*@company\.com",
            subject_pattern=r"报价",
            content_pattern=r"产品",
            match_logic="AND",
        )
        assert RuleMatcher.match("a@company.com", "报价单", "我们的产品A", [rule]) is not None

    def test_and_partial_match_sender_fail(self):
        rule = make_rule(
            sender_pattern=r".*@company\.com",
            subject_pattern=r"报价",
            match_logic="AND",
        )
        # 发件人不匹配
        assert RuleMatcher.match("a@gmail.com", "报价单", "body", [rule]) is None

    def test_and_partial_match_subject_fail(self):
        rule = make_rule(
            sender_pattern=r".*@company\.com",
            subject_pattern=r"报价",
            match_logic="AND",
        )
        # 主题不匹配
        assert RuleMatcher.match("a@company.com", "普通邮件", "body", [rule]) is None

    def test_and_with_null_condition_ignored(self):
        """AND 逻辑下，NULL 的条件应被忽略（视为通过）。"""
        rule = make_rule(
            sender_pattern=r".*@company\.com",
            subject_pattern=None,  # 不限制主题
            content_pattern=None,  # 不限制正文
            match_logic="AND",
        )
        assert RuleMatcher.match("a@company.com", "anything", "anything", [rule]) is not None

    def test_and_three_conditions_one_fail(self):
        rule = make_rule(
            sender_pattern=r"a@b\.com",
            subject_pattern=r"urgent",
            content_pattern=r"invoice",
            match_logic="AND",
        )
        # 正文不含 invoice（注意不能用 "no invoice here"，因为含 "invoice" 这个词）
        assert RuleMatcher.match("a@b.com", "urgent", "nothing relevant here", [rule]) is None


class TestOrLogic:
    """OR 逻辑：任一非 NULL 条件满足即命中。"""

    def test_or_first_match(self):
        rule = make_rule(
            sender_pattern=r"boss@company\.com",
            subject_pattern=r"urgent",
            match_logic="OR",
        )
        # 发件人匹配
        assert RuleMatcher.match("boss@company.com", "normal", "body", [rule]) is not None

    def test_or_second_match(self):
        rule = make_rule(
            sender_pattern=r"boss@company\.com",
            subject_pattern=r"urgent",
            match_logic="OR",
        )
        # 主题匹配
        assert RuleMatcher.match("anyone@x.com", "urgent matter", "body", [rule]) is not None

    def test_or_none_match(self):
        rule = make_rule(
            sender_pattern=r"boss@company\.com",
            subject_pattern=r"urgent",
            match_logic="OR",
        )
        assert RuleMatcher.match("alice@x.com", "normal", "body", [rule]) is None

    def test_or_three_conditions(self):
        rule = make_rule(
            sender_pattern=r"a@x\.com",
            subject_pattern=r"urgent",
            content_pattern=r"invoice",
            match_logic="OR",
        )
        assert RuleMatcher.match("a@x.com", "x", "x", [rule]) is not None
        assert RuleMatcher.match("b@x.com", "urgent", "x", [rule]) is not None
        assert RuleMatcher.match("b@x.com", "x", "has invoice", [rule]) is not None
        assert RuleMatcher.match("b@x.com", "x", "no match", [rule]) is None


class TestPriority:
    """多规则按优先级匹配。
    注意：RuleMatcher 本身按传入顺序匹配，排序由 DB 层 Rule.get_active_rules 完成。
    这里模拟 DB 已排序后的列表（priority 升序）。
    """

    def test_lower_priority_number_matched_first(self):
        # DB 已按 priority 升序排序：boss(1) 在前，default(100) 在后
        rules = [
            make_rule(rule_id=2, sender_pattern=r"boss@x\.com", priority=1, rule_name="boss"),
            make_rule(rule_id=1, sender_pattern=r".*", priority=100, rule_name="default"),
        ]
        # 两条都匹配，但 boss 在前
        matched = RuleMatcher.match("boss@x.com", "sub", "body", rules)
        assert matched is not None
        assert matched["id"] == 2

    def test_same_priority_by_id_order(self):
        # DB 已按 priority, id 升序排序：rule 5 在前
        rules = [
            make_rule(rule_id=5, sender_pattern=r"a@x\.com", priority=50),
            make_rule(rule_id=10, sender_pattern=r"a@x\.com", priority=50),
        ]
        matched = RuleMatcher.match("a@x.com", "sub", "body", rules)
        # 同优先级按 id 升序，rule 5 先匹配
        assert matched["id"] == 5

    def test_first_match_wins(self):
        # catch-all 优先级更高(1)，在列表前面
        rules = [
            make_rule(rule_id=1, sender_pattern=r".*", priority=1, rule_name="catch-all"),
            make_rule(rule_id=2, sender_pattern=r"specific@x\.com", priority=2, rule_name="specific"),
        ]
        # catch-all 优先级更高，匹配后直接返回，不再检查 specific
        matched = RuleMatcher.match("specific@x.com", "sub", "body", rules)
        assert matched["id"] == 1


class TestDisabledRule:
    """禁用的规则应被跳过。"""

    def test_disabled_rule_skipped(self):
        rules = [
            make_rule(rule_id=1, sender_pattern=r".*", priority=1, enabled=0),  # 禁用
            make_rule(rule_id=2, sender_pattern=r".*", priority=2, enabled=1),  # 启用
        ]
        matched = RuleMatcher.match("a@x.com", "sub", "body", rules)
        assert matched["id"] == 2

    def test_all_disabled_returns_none(self):
        rules = [
            make_rule(rule_id=1, sender_pattern=r".*", enabled=0),
        ]
        assert RuleMatcher.match("a@x.com", "sub", "body", rules) is None


class TestInvalidRegex:
    """无效正则应被安全处理。"""

    def test_invalid_regex_no_crash(self):
        rule = make_rule(sender_pattern=r"[")  # 无效正则
        assert RuleMatcher.match("a@x.com", "sub", "body", [rule]) is None

    def test_invalid_regex_in_one_condition(self):
        """一个条件正则无效，其他条件正常时不应崩溃。"""
        rule = make_rule(
            sender_pattern=r"[",  # 无效
            subject_pattern=r"urgent",  # 有效
            match_logic="OR",
        )
        # subject 匹配，OR 逻辑下应命中
        # 但 sender 正则无效返回 False，OR 下 subject=True → 命中
        matched = RuleMatcher.match("a@x.com", "urgent task", "body", [rule])
        assert matched is not None


class TestEmptyInputs:
    """空输入的处理。"""

    def test_empty_sender_with_sender_pattern(self):
        rule = make_rule(sender_pattern=r".*@x\.com")
        assert RuleMatcher.match("", "sub", "body", [rule]) is None

    def test_empty_subject_with_subject_pattern(self):
        rule = make_rule(subject_pattern=r"urgent")
        assert RuleMatcher.match("a@x.com", "", "body", [rule]) is None

    def test_empty_body_with_content_pattern(self):
        rule = make_rule(content_pattern=r"invoice")
        assert RuleMatcher.match("a@x.com", "sub", "", [rule]) is None

    def test_no_condition_with_empty_inputs(self):
        """无条件的规则即使输入为空也应命中。"""
        rule = make_rule()
        assert RuleMatcher.match("", "", "", [rule]) is not None


class TestBackwardCompatibility:
    """向后兼容：旧代码使用 SenderMatcher 应仍能工作。"""

    def test_sender_matcher_legacy_api(self):
        rules = [
            make_rule(rule_id=1, sender_pattern=r".*@hengtiansoft\.com"),
        ]
        # 旧接口只传 sender 和 rules
        matched = SenderMatcher.match("alice@hengtiansoft.com", rules)
        assert matched is not None
        assert matched["id"] == 1

    def test_sender_matcher_legacy_no_match(self):
        rules = [
            make_rule(rule_id=1, sender_pattern=r".*@hengtiansoft\.com"),
        ]
        matched = SenderMatcher.match("alice@gmail.com", rules)
        assert matched is None


class TestRealWorldScenarios:
    """真实业务场景测试。"""

    def test_scenario_boss_email_high_priority(self):
        """场景：老板邮件优先级最高，人工审核"""
        # DB 已按 priority 排序：老板(1) 在前，通用(100) 在后
        rules = [
            make_rule(rule_id=2, rule_name="老板", sender_pattern=r"boss@company\.com",
                      priority=1, auto_send=0, prompt_template="正式回复 {email_content}"),
            make_rule(rule_id=1, rule_name="通用", sender_pattern=r".*", priority=100,
                      prompt_template="通用回复 {email_content}"),
        ]
        matched = RuleMatcher.match("boss@company.com", "关于季度汇报", "请准备汇报材料", rules)
        assert matched["id"] == 2
        assert matched["rule_name"] == "老板"

    def test_scenario_urgent_subject_any_sender(self):
        """场景：主题含'紧急'，任何发件人，优先响应"""
        # DB 已按 priority 排序：紧急(10) 在前，普通(50) 在后
        rules = [
            make_rule(rule_id=2, rule_name="紧急", sender_pattern=None,
                      subject_pattern=r"紧急|urgent", priority=10),
            make_rule(rule_id=1, rule_name="普通", sender_pattern=r".*@company\.com",
                      subject_pattern=None, priority=50),
        ]
        # 外部发件人 + 紧急主题 → 命中紧急规则
        matched = RuleMatcher.match("external@gmail.com", "紧急：服务器宕机", "body", rules)
        assert matched["id"] == 2

    def test_scenario_meeting_invite_and_logic(self):
        """场景：主题含'邀请' 且 正文含'会议'（AND）"""
        rules = [
            make_rule(rule_id=1, rule_name="会议确认",
                      subject_pattern=r"邀请|invite",
                      content_pattern=r"会议|meeting",
                      match_logic="AND", priority=20),
        ]
        # 主题和正文都匹配
        assert RuleMatcher.match("a@b.com", "会议邀请", "明天有会议", [rules[0]]) is not None
        # 只有主题匹配
        assert RuleMatcher.match("a@b.com", "邀请函", "只是一般邀请", [rules[0]]) is None
        # 只有正文匹配
        assert RuleMatcher.match("a@b.com", "通知", "明天有会议", [rules[0]]) is None

    def test_scenario_fallback_catch_all(self):
        """场景：兜底规则匹配所有邮件"""
        # DB 已按 priority 排序：特定(10) 在前，兜底(999) 在后
        rules = [
            make_rule(rule_id=1, rule_name="特定", sender_pattern=r"specific@x\.com", priority=10),
            make_rule(rule_id=99, rule_name="兜底", sender_pattern=r".*", priority=999),
        ]
        # 不匹配特定规则的邮件 → 命中兜底
        matched = RuleMatcher.match("unknown@y.com", "sub", "body", rules)
        assert matched["id"] == 99
        assert matched["rule_name"] == "兜底"


class TestSenderDisplayNameMatching:
    """发件人显示名匹配（OWA 常见场景）。

    OWA 列表通常只显示发件人名字（如"简历0624"），不显示邮箱。
    sender_pattern 应该能同时匹配显示名、邮箱、或组合文本。
    """

    def test_match_display_name_only(self):
        """sender 只有显示名时，pattern 匹配显示名"""
        rule = make_rule(sender_pattern=r"简历")
        # sender 是纯显示名
        assert RuleMatcher.match("简历0624", "主题", "正文", [rule]) is not None

    def test_match_email_when_display_name_returned(self):
        """sender 是显示名但 rule 匹配邮箱格式 → 不应匹配"""
        rule = make_rule(sender_pattern=r".*@hengtiansoft\.com")
        # sender 只有显示名"简历0624"，不包含邮箱
        assert RuleMatcher.match("简历0624", "主题", "正文", [rule]) is None

    def test_match_email_in_combined_format(self):
        """sender 是 "显示名 <邮箱>" 格式，rule 匹配邮箱"""
        rule = make_rule(sender_pattern=r".*@hengtiansoft\.com")
        sender = "简历0624 <resume@hengtiansoft.com>"
        assert RuleMatcher.match(sender, "主题", "正文", [rule]) is not None

    def test_match_display_name_in_combined_format(self):
        """sender 是 "显示名 <邮箱>" 格式，rule 匹配显示名"""
        rule = make_rule(sender_pattern=r"简历")
        sender = "简历0624 <resume@hengtiansoft.com>"
        assert RuleMatcher.match(sender, "主题", "正文", [rule]) is not None

    def test_match_catch_all_with_display_name(self):
        """兜底规则 .* 匹配任何 sender（含纯显示名）"""
        rule = make_rule(sender_pattern=r".*")
        assert RuleMatcher.match("简历0624", "主题", "正文", [rule]) is not None
        assert RuleMatcher.match("resume@hengtiansoft.com", "主题", "正文", [rule]) is not None
        assert RuleMatcher.match("简历0624 <resume@hengtiansoft.com>", "主题", "正文", [rule]) is not None

    def test_real_world_scenario_resume_email(self):
        """真实场景：收到简历邮件，发件人显示名"简历0624"

        用户配置规则：
        - 规则1: sender_pattern = .*@hengtiansoft\.com （匹配公司邮箱）
        - 规则2: 兜底 sender_pattern = .* （匹配所有）
        """
        rules = [
            make_rule(rule_id=1, rule_name="公司邮箱",
                      sender_pattern=r".*@hengtiansoft\.com", priority=10),
            make_rule(rule_id=2, rule_name="兜底",
                      sender_pattern=r".*", priority=999),
        ]
        # sender 只有显示名 → 规则1 不命中 → 命中兜底规则2
        matched = RuleMatcher.match("简历0624", "简历0624", "正文内容", rules)
        assert matched is not None
        assert matched["id"] == 2

    def test_match_subject_when_sender_not_matched(self):
        """sender 不匹配但 subject 匹配（OR 逻辑）"""
        rule = make_rule(
            sender_pattern=r".*@hengtiansoft\.com",
            subject_pattern=r"简历",
            match_logic="OR",
        )
        # sender 是显示名不匹配邮箱规则，但主题匹配
        assert RuleMatcher.match("简历0624", "简历投递", "正文", [rule]) is not None

    def test_no_sender_pattern_matches_any_sender(self):
        """sender_pattern = NULL → 不限制发件人，任何 sender 都通过"""
        rule = make_rule(sender_pattern=None, subject_pattern=r"简历")
        assert RuleMatcher.match("简历0624", "简历投递", "正文", [rule]) is not None
        assert RuleMatcher.match("anyone@anywhere.com", "简历投递", "正文", [rule]) is not None
        assert RuleMatcher.match("简历0624", "普通邮件", "正文", [rule]) is None
