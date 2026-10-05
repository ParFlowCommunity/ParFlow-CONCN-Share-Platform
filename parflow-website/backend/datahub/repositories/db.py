from contextlib import contextmanager
from datetime import date, datetime
from decimal import Decimal
import json
import os
import pymysql
from .. import config  # noqa: F401 -- Load backend/.env before opening a connection.


def connect(database=None, **overrides):
    options = dict(
        host=os.getenv("MYSQL_HOST", "127.0.0.1"),
        port=int(os.getenv("MYSQL_PORT", "3306")),
        user=os.getenv("MYSQL_USER", "concn_app"),
        password=os.getenv("MYSQL_PASSWORD", ""),
        database=database or os.getenv("MYSQL_DATABASE", "concn_datahub"),
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=False,
        connect_timeout=5,
        read_timeout=30,
        write_timeout=30,
        init_command="SET time_zone='+00:00', SESSION sql_mode='STRICT_TRANS_TABLES,NO_ZERO_IN_DATE,NO_ZERO_DATE,ERROR_FOR_DIVISION_BY_ZERO,NO_ENGINE_SUBSTITUTION'",
    )
    options.update(overrides)
    return pymysql.connect(**options)


@contextmanager
def transaction():
    conn = connect()
    try:
        with conn.cursor() as cursor:
            yield cursor
        conn.commit()
    except BaseException:
        conn.rollback()
        raise
    finally:
        conn.close()


def one(c, sql, args=()):
    c.execute(sql, args)
    return c.fetchone()


def all_rows(c, sql, args=()):
    c.execute(sql, args)
    return c.fetchall()


def json_default(value):
    if isinstance(value, (date, datetime)):
        return value.isoformat() + ("Z" if isinstance(value, datetime) else "")
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, bytes):
        return value.hex()
    raise TypeError(type(value).__name__)


def dump(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, default=json_default)


def decoded(value):
    return json.loads(value) if isinstance(value, str) else value


def audit(c, actor, action, kind, key, details):
    c.execute(
        "INSERT INTO audit_logs(actor_user_id,action_code,object_type,object_id,details) VALUES(%s,%s,%s,%s,%s)",
        (actor, action, kind, str(key), dump(details)),
    )
