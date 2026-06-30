"""发件人匹配测试。"""
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
        rules = [{"id": 1, "sender_pattern": r"["}]
        assert SenderMatcher.match("test@example.com", rules) is None

    def test_multiple_rules_first_match(self):
        rules = [
            {"id": 1, "sender_pattern": r".*@gmail\.com"},
            {"id": 2, "sender_pattern": r".*@hengtiansoft\.com"},
        ]
        result = SenderMatcher.match("user@hengtiansoft.com", rules)
        assert result["id"] == 2
