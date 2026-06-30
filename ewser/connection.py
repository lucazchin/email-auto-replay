"""
EWS 连接管理器。
使用 exchangelib 通过 EWS 协议连接 Exchange Server。
"""
from exchangelib import Account, Credentials, Configuration, DELEGATE
from loguru import logger


class EWSConnection:
    """单例 EWS 连接管理器。"""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._account = None
            cls._instance._config = None
        return cls._instance

    def connect(self, email: str, password: str, server: str):
        """
        建立 EWS 连接。
        :param email: 邮箱地址，如 kangliu1@hengtiansoft.com
        :param password: 邮箱密码
        :param server: Exchange 服务器，如 mail.hengtiansoft.com
        """
        creds = Credentials(email, password)
        config = Configuration(server=server, credentials=creds)

        self._account = Account(
            primary_smtp_address=email,
            config=config,
            autodiscover=False,
            access_type=DELEGATE,
        )

        version = self._account.version
        logger.info(
            f"EWS 连接成功: {email} | "
            f"Exchange {version.fullname} (build {version.build})"
        )
        return self._account

    @property
    def account(self) -> Account:
        if self._account is None:
            raise RuntimeError("EWS 未连接，请先调用 connect()")
        return self._account

    @property
    def connected(self) -> bool:
        return self._account is not None

    def disconnect(self):
        """断开连接（exchangelib 无状态，主要是清理引用）。"""
        self._account = None
        logger.info("EWS 连接已断开")
