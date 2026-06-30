"""
数据库连接池管理。
使用 dbutils.PooledDB 实现连接复用。
"""
import pymysql
from dbutils.pooled_db import PooledDB
from config.loader import Config


class DBPool:
    _pool = None

    @classmethod
    def get_pool(cls) -> PooledDB:
        if cls._pool is None:
            cfg = Config().get("database")
            cls._pool = PooledDB(
                creator=pymysql,
                maxconnections=cfg.get("pool_size", 5),
                mincached=1,
                maxcached=cfg.get("pool_size", 5),
                host=cfg["host"],
                port=cfg["port"],
                user=cfg["user"],
                password=cfg["password"],
                database=cfg["database"],
                charset="utf8mb4",
                cursorclass=pymysql.cursors.DictCursor,
                autocommit=False,
            )
        return cls._pool

    @classmethod
    def get_conn(cls):
        """获取一个连接，使用完毕后必须 close()。"""
        return cls.get_pool().connection()

    @classmethod
    def close_pool(cls):
        """关闭连接池（程序退出时调用）。"""
        if cls._pool:
            cls._pool.close()
            cls._pool = None
