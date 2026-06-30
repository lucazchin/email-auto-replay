"""正文清洗测试。"""
import pytest
from monitor.content_extractor import ContentExtractor


class TestContentExtractor:
    def setup_method(self):
        self.extractor = ContentExtractor()

    def test_html_to_text(self):
        html = "<p>Hello <b>World</b></p>"
        result = self.extractor.clean(html)
        assert "Hello" in result
        assert "World" in result

    def test_plain_text_passthrough(self):
        text = "This is a plain text email."
        result = self.extractor.clean(text)
        assert "plain text email" in result

    def test_strip_quoted_reply_english(self):
        text = (
            "Original message here.\n\n"
            "On Mon, Jan 1, 2024 at 10:00 AM John wrote:\n> Quoted text"
        )
        result = self.extractor.clean(text)
        assert "Original message here" in result
        assert "Quoted text" not in result

    def test_strip_quoted_reply_chinese(self):
        text = "原始内容\n\n在 2024年1月1日，张三 写道：\n> 引用内容"
        result = self.extractor.clean(text)
        assert "原始内容" in result
        assert "引用内容" not in result

    def test_strip_signature(self):
        text = "Email body here.\n\n--\nJohn Doe\nSoftware Engineer"
        result = self.extractor.clean(text)
        assert "Email body here" in result
        assert "John Doe" not in result

    def test_compress_whitespace(self):
        text = "Line1\n\n\n\n\nLine2"
        result = self.extractor.clean(text)
        assert "\n\n\n" not in result

    def test_empty_input(self):
        assert self.extractor.clean("") == ""
