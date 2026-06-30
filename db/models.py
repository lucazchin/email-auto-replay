"""
数据操作层：封装所有数据库 CRUD。
每个类对应一张表。
"""
from datetime import datetime
from loguru import logger
from db.connection import DBPool


class Mailbox:
    """邮箱配置表操作。"""

    @staticmethod
    def get_active():
        """获取所有启用的邮箱配置。"""
        conn = DBPool.get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM mailbox WHERE status = 1")
                return cur.fetchall()
        finally:
            conn.close()

    @staticmethod
    def get_by_id(mailbox_id: int):
        conn = DBPool.get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM mailbox WHERE id = %s", (mailbox_id,))
                return cur.fetchone()
        finally:
            conn.close()


class Rule:
    """监控规则表操作。"""

    @staticmethod
    def get_active_rules(mailbox_id: int):
        """
        获取指定邮箱的所有启用规则，按 priority 升序排序。
        优先级相同的按 id 升序（先创建的先匹配）。
        """
        conn = DBPool.get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT * FROM rule
                    WHERE mailbox_id = %s
                      AND (enabled = 1 OR enabled IS NULL)
                    ORDER BY
                        COALESCE(priority, 100) ASC,
                        id ASC
                    """,
                    (mailbox_id,),
                )
                return cur.fetchall()
        finally:
            conn.close()

    @staticmethod
    def get_all_rules(mailbox_id: int):
        """获取指定邮箱的所有规则（含禁用的），便于管理后台展示。"""
        conn = DBPool.get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT * FROM rule
                    WHERE mailbox_id = %s
                    ORDER BY COALESCE(priority, 100) ASC, id ASC
                    """,
                    (mailbox_id,),
                )
                return cur.fetchall()
        finally:
            conn.close()


class EmailRecord:
    """邮件记录表操作。"""

    @staticmethod
    def is_processed(mail_uid: str) -> bool:
        """检查邮件是否已处理（幂等性核心）。"""
        conn = DBPool.get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id FROM email_record WHERE mail_uid = %s AND processed = 1",
                    (mail_uid,),
                )
                return cur.fetchone() is not None
        finally:
            conn.close()

    @staticmethod
    def insert_or_get(mail_uid: str, mailbox_id: int, sender: str,
                      subject: str, content: str):
        """
        插入邮件记录，若已存在则返回已有 ID。
        使用 INSERT IGNORE + UNIQUE 索引保证幂等。
        :return: (email_id, already_processed)
        """
        conn = DBPool.get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT IGNORE INTO email_record
                        (mailbox_id, mail_uid, sender, subject, content)
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (mailbox_id, mail_uid, sender, subject, content),
                )
                conn.commit()

                cur.execute(
                    "SELECT id, processed FROM email_record WHERE mail_uid = %s",
                    (mail_uid,),
                )
                row = cur.fetchone()
                if row:
                    return row["id"], row["processed"] == 1
                return None, False
        except Exception as e:
            conn.rollback()
            logger.error(f"插入邮件记录失败: {e}")
            raise
        finally:
            conn.close()

    @staticmethod
    def mark_processed(email_id: int):
        """标记邮件为已处理。"""
        conn = DBPool.get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE email_record SET processed = 1 WHERE id = %s",
                    (email_id,),
                )
                conn.commit()
        finally:
            conn.close()

    @staticmethod
    def has_replied_same_subject_sender(
        mailbox_id: int, sender: str, subject: str,
    ) -> bool:
        """
        二次去重：检查相同发件人 + 相同主题是否已有发送成功的回复。
        防 changekey 变化导致 mail_uid 不同而绕过主键去重。
        """
        conn = DBPool.get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT 1 FROM email_record e
                    JOIN reply_record r ON r.email_id = e.id
                    WHERE e.mailbox_id = %s
                      AND e.sender = %s
                      AND e.subject = %s
                      AND r.status = 'sent'
                    LIMIT 1
                    """,
                    (mailbox_id, sender, subject),
                )
                return cur.fetchone() is not None
        finally:
            conn.close()


class ReplyRecord:
    """回复记录表操作。"""

    @staticmethod
    def create(email_id: int, reply_content: str, status: str = "pending") -> int:
        conn = DBPool.get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO reply_record (email_id, reply_content, status)
                    VALUES (%s, %s, %s)
                    """,
                    (email_id, reply_content, status),
                )
                conn.commit()
                return cur.lastrowid
        finally:
            conn.close()

    @staticmethod
    def update_status(reply_id: int, status: str, error_msg: str = None):
        conn = DBPool.get_conn()
        try:
            with conn.cursor() as cur:
                sent_at = datetime.now() if status == "sent" else None
                cur.execute(
                    """
                    UPDATE reply_record
                    SET status = %s, sent_at = %s, error_msg = %s
                    WHERE id = %s
                    """,
                    (status, sent_at, error_msg, reply_id),
                )
                conn.commit()
        finally:
            conn.close()
