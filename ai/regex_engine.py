"""
正则规则回复引擎：不依赖 AI，直接从邮件内容中提取信息，按模板拼回复。
用于抢简历等只需提取关键信息（姓名）的场景，实现毫秒级回复。

支持三种提取模式：
  1. 正则匹配（通用）— 对 subject+body 做 re.search + expand
  2. HTML 表格解析（table:姓名）— 从 <table> 中定位列
  3. 纯文本提取（text:姓名）— 从纯文本垂列表中按行定位姓名列
"""
import re
from html.parser import HTMLParser
from loguru import logger


# ---------------------------------------------------------------------------
# 轻量 HTML 表格解析器（不依赖 BeautifulSoup）
# ---------------------------------------------------------------------------
class _TableParser(HTMLParser):
    """将 HTML <table> 解析为二维列表 rows[row][col] = 单元格文本。"""

    def __init__(self):
        super().__init__()
        self.rows: list[list[str]] = []
        self._current_row: list[str] = []
        self._in_td = False
        self._td_text: str = ""

    def handle_starttag(self, tag, attrs):
        if tag in ("td", "th"):
            self._in_td = True
            self._td_text = ""
        elif tag == "tr":
            self._current_row = []

    def handle_endtag(self, tag):
        if tag in ("td", "th"):
            self._in_td = False
            self._current_row.append(self._td_text.strip())
        elif tag == "tr" and self._current_row:
            self.rows.append(self._current_row)

    def handle_data(self, data):
        if self._in_td:
            self._td_text += data


def _parse_tables(html: str) -> list[list[list[str]]]:
    """
    从 HTML 中提取所有表格，返回 [table[row][col]]。
    """
    parser = _TableParser()
    parser.feed(html)
    # 把连续的 rows 按 thead/tbody 分组（简单策略：第一行当 header，后续当 data）
    # 这里返回原始全部 rows，由调用方判断
    return [parser.rows] if parser.rows else []


def _extract_column_by_header(
    rows: list[list[str]], header_keyword: str,
) -> list[str] | None:
    """
    根据表头关键字定位列索引，返回该列所有数据行值。

    :param rows: 表格二维数组（rows[0] 为表头）
    :param header_keyword: 表头关键字（如"姓名"、"姓名 "），模糊包含匹配
    :return: 该列数据行的值列表；未找到返回 None
    """
    if not rows or len(rows) < 2:
        return None

    headers = rows[0]
    col_idx = None
    for i, h in enumerate(headers):
        if header_keyword.strip() in h.strip():
            col_idx = i
            break

    if col_idx is None:
        return None

    values = []
    for row in rows[1:]:
        if col_idx < len(row) and row[col_idx].strip():
            values.append(row[col_idx].strip())
    return values if values else None


# ---------------------------------------------------------------------------
# 主引擎
# ---------------------------------------------------------------------------
class RegexReplyEngine:
    """基于正则 / 表格模板的轻量回复生成器。"""

    @staticmethod
    def generate(
        reply_pattern: str,
        reply_template: str,
        sender: str,
        subject: str,
        body: str,
        *,
        raw_body: str | None = None,
    ) -> str | None:
        """
        生成回复。自动尝试 table / text 双模式提升命中率。

        :param reply_pattern: 正则表达式 或 特殊模式前缀：
                              'table:<header>' — HTML 表格列提取（自动回退 text）
                              'text:<header>'  — 纯文本垂列表提取（自动回退 table）
                              其他              — 标准 re.search 正则
        :param reply_template: 模板，\\1 \\2 引用捕获组
        :param body: 清洗后的纯文本正文
        :param raw_body: 原始内容（HTML 表格模式需要），默认取 body
        :return: 生成的回复文本，未匹配返回 None
        """
        if not reply_pattern or not reply_template:
            logger.debug("RegexReplyEngine: reply_pattern 或 reply_template 为空，跳过")
            return None

        html_src = raw_body or body

        # ---- 模式 A：table / text 双模式自动切换 ----
        has_html = bool(raw_body) and bool(re.search(r'<(table|td|tr)\b', html_src, re.IGNORECASE))

        if reply_pattern.startswith("table:"):
            keyword = reply_pattern.split(":", 1)[1].strip()
            alt_pattern = f"text:{keyword}" if keyword else None

            # 仅在源内容包含 HTML 表格时尝试
            result = None
            if has_html:
                result = RegexReplyEngine._extract_from_table(
                    reply_pattern, reply_template, html_src,
                )
            if result:
                return result

            # 表格失败或非 HTML → 尝试纯文本
            if alt_pattern:
                if has_html:
                    logger.info("RegexReplyEngine: 表格提取失败，自动尝试纯文本模式")
                else:
                    logger.info("RegexReplyEngine: 源内容无 HTML 表格，直接走纯文本模式")
                result = RegexReplyEngine._extract_from_plain_text(
                    alt_pattern, reply_template, body,
                )
                if result:
                    return result
            return None

        if reply_pattern.startswith("text:"):
            keyword = reply_pattern.split(":", 1)[1].strip()
            alt_pattern = f"table:{keyword}" if keyword else None

            # 先纯文本
            result = RegexReplyEngine._extract_from_plain_text(
                reply_pattern, reply_template, body,
            )
            if result:
                return result

            # 纯文本失败 → 仅当有 HTML 时才回退表格
            if alt_pattern and has_html:
                logger.info("RegexReplyEngine: 纯文本提取失败，自动尝试表格模式")
                result = RegexReplyEngine._extract_from_table(
                    alt_pattern, reply_template, html_src,
                )
                if result:
                    return result

            return None

        # ---- 模式 B：标准正则匹配 ----
        text = f"{subject}\n{body}"
        try:
            match = re.search(reply_pattern, text, re.DOTALL)
        except re.error as exc:
            logger.error(f"RegexReplyEngine: reply_pattern 非法 → {exc}")
            return None

        if not match:
            logger.info("RegexReplyEngine: 未匹配")
            return None

        try:
            reply = match.expand(reply_template)
        except Exception as exc:
            logger.error(f"RegexReplyEngine: 模板展开失败 → {exc}")
            return None

        reply = reply.strip()
        if not reply:
            logger.warning("RegexReplyEngine: 模板展开结果为空")
            return None

        logger.info(f"RegexReplyEngine: 正则命中 → {reply}")
        return reply

    @staticmethod
    def _extract_from_table(
        reply_pattern: str,
        reply_template: str,
        raw_body: str,
    ) -> str | None:
        """
        从 HTML 表格中按表头列名提取值。

        reply_pattern 格式: 'table:姓名' （冒号后为表头关键字）
        """
        header_keyword = reply_pattern.split(":", 1)[1].strip()
        if not header_keyword:
            logger.warning("RegexReplyEngine: table 模式缺少表头关键字")
            return None

        tables = _parse_tables(raw_body)
        for rows in tables:
            values = _extract_column_by_header(rows, header_keyword)
            if values:
                # 用第一个非空值填充模板中的 \1
                name = values[0]
                try:
                    reply = re.sub(r"\\1", name, reply_template)
                except Exception:
                    reply = name
                reply = reply.strip()
                if reply:
                    logger.info(
                        f"RegexReplyEngine: 表格提取命中 "
                        f"(header={header_keyword!r}, 共 {len(values)} 行) → {reply}"
                    )
                    return reply

        logger.info(f"RegexReplyEngine: 表格中未找到 '{header_keyword}' 列")
        return None

    @staticmethod
    def _extract_from_plain_text(
        reply_pattern: str,
        reply_template: str,
        body: str,
    ) -> str | None:
        """
        从纯文本垂列表中提取姓名列。

        简历邮件的纯文本格式：每行一个字段，N 个字段构成一个候选人。
        姓名出现在固定偏移位置。
        策略：找到 "姓名" 表头 → 扫描数据区按块提取。
        如果块对齐失败，回退到按中文字符模式兜底提取。
        """
        header_keyword = reply_pattern.split(":", 1)[1].strip()
        if not header_keyword:
            return None

        lines = [l.strip() for l in body.split("\n") if l.strip()]
        if not lines:
            return None

        header_kw = {
            "姓名", "岗位", "毕业时间", "院校", "专业", "工作经验",
            "年限", "综合评价", "薪资", "期望薪资", "目前薪资",
            "面试", "电话", "Owner", "日期", "备注", "职位",
            "目前薪", "期望薪", "入职时间",
        }

        # 1. 定位 "姓名" 在全部 lines 中的位置
        name_header_idx = -1
        for i, line in enumerate(lines):
            if header_keyword in line:
                name_header_idx = i
                break
        if name_header_idx < 0:
            # 无 "姓名" 表头 → 兜底：全文单行正则提取
            logger.info("RegexReplyEngine: 未找到表头关键字，尝试全文正则兜底")
            return _extract_names_singleline(body, header_keyword, header_kw, reply_template)

        # 2. 向前后扫描确定表头范围和数据起始
        # 向后找到表头的最后一个字段
        header_end = name_header_idx
        for i in range(name_header_idx + 1, len(lines)):
            if any(kw in lines[i] for kw in header_kw):
                header_end = i
            else:
                break

        # 姓名在表头中的列偏移（从表头起始到数据起始之间的位置）
        col_offset = name_header_idx - name_header_idx  # = 0, 姓名在表头首列的情况
        # 但如果表头首列是空/日期相关的，需要调整
        # 先尝试简单策略：姓名列索引 = 0（表头首列）

        # 3. 找到实际数据块大小
        # 策略：从 data_start 开始扫描，找到第 2 个周期中 name_position 的 "姓名" 行偏移
        data_start = header_end + 1
        if data_start >= len(lines):
            return None

        # 表头中没有日期的列，但数据中有——数据比表头多一列（日期列在表头外）
        # 计算表头列数
        header_fields = header_end - name_header_idx + 1

        # 尝试多个可能的 block_size（表头列数 或 表头列数+日期列）
        possible_sizes = [header_fields, header_fields + 1]
        found_block_size = None
        found_col_index = None

        for bs in possible_sizes:
            # 姓名列索引：如果 block_size = header_fields，姓名在 col=0
            # 如果 block_size = header_fields+1，日期在 col=0，姓名在 col=1
            ci = bs - header_fields  # 0 或 1
            if ci < 0 or ci >= bs:
                continue

            # 验证：尝试提取3个周期的姓名，检查是否有2个以上有效
            valid_count = 0
            for offset in range(data_start, min(data_start + bs * 3, len(lines)), bs):
                ni = offset + ci
                if ni < len(lines):
                    name = lines[ni]
                    if re.match(r'^[\u4e00-\u9fff]{2,3}$', name) and name not in header_kw:
                        valid_count += 1
            if valid_count >= 2:
                found_block_size = bs
                found_col_index = ci
                break

        # 4. 兜底：按"日期行 → 下一行 = 姓名"的模式提取
        # 简历邮件格式：每行的第一个字段是日期（如 6/26、2026/6/29），紧接的下一行是姓名
        if found_block_size is None:
            logger.info("RegexReplyEngine: 块对齐失败，按日期-姓名模式提取")
            names = []
            prev_is_date = False
            for line in lines[name_header_idx + 1:]:
                # 日期行：M/DD 或 YYYY/M/DD 格式
                if re.match(r'^\d{1,4}[/.]\d{1,2}(?:[/.]\d{1,2})?$', line):
                    prev_is_date = True
                    continue
                if prev_is_date:
                    # 日期行的下一行是姓名
                    if re.match(r'^[\u4e00-\u9fff]{2,3}$', line) and line not in header_kw:
                        names.append(line)
                    prev_is_date = False
            if names:
                reply = _build_reply(names, reply_template)
                logger.info(
                    f"RegexReplyEngine: 日期-姓名模式命中 "
                    f"(共 {len(names)} 人) → {reply[:50]}..."
                )
                return reply
            # 5. 最终兜底：单行文本正则提取
            # html2text 转换 HTML 表格时可能把所有内容合并为一行
            return _extract_names_singleline(body, header_keyword, header_kw, reply_template)

        # 5. 按确定的 block_size + col_index 提取
        names = []
        for offset in range(data_start, len(lines), found_block_size):
            ni = offset + found_col_index
            if ni >= len(lines):
                break
            name = lines[ni]
            if re.match(r'^[\u4e00-\u9fff]{2,3}$', name) and name not in header_kw:
                names.append(name)

        if not names:
            return None

        reply = _build_reply(names, reply_template)
        logger.info(
            f"RegexReplyEngine: 纯文本提取命中 "
            f"(header={header_keyword!r}, 共 {len(names)} 人) → {reply[:50]}..."
        )
        return reply


def _build_reply(names: list[str], template: str) -> str:
    """按模板合成回复。"""
    if "\\1" in template:
        return "\n".join(template.replace("\\1", n) for n in names)
    return "\n".join(names)


def _extract_names_singleline(
    text: str, header_keyword: str, header_kw: set, template: str,
) -> str | None:
    """
    单行文本兜底提取：html2text 转换 HTML 表格后可能把所有字段合并为一行。
    用 \"日期 姓名\" 的相邻模式提取姓名。
    例如: \"...6/29 周添龙 2022 湖南科技学院...6/29 刘涛 2024...\"
    也用作无表头邮件的兜底。
    """
    # 日期后紧跟中文姓名: 6/29 周添龙, 2026/6/29 郑霞
    # \s+ 匹配换行和空格，兼容多行和单行两种格式
    pattern = re.compile(
        r'\b\d{1,4}[/.]\d{1,2}(?:[/.]\d{1,2})?\s+([\u4e00-\u9fff]{2,3})'
    )
    names = []
    seen = set()
    for m in pattern.finditer(text):
        name = m.group(1)
        if name not in header_kw and name not in seen:
            names.append(name)
            seen.add(name)

    # 至少匹配到 1 个姓名；无表头时需命中 >= 3 个降低误判
    has_header = header_keyword in text
    if not names:
        return None
    if not has_header and len(names) < 3:
        return None

    reply = _build_reply(names, template)
    logger.info(
        f"RegexReplyEngine: 单行正则命中 (共 {len(names)} 人) → {reply[:50]}..."
    )
    return reply
