from datetime import datetime
import hashlib
import re
import uuid
from flask import request


class ApiError(Exception):
    def __init__(self, code, status=400, **params):
        self.code, self.status, self.params = code, status, params


def now():
    return datetime.utcnow()


def uid():
    return uuid.uuid4().hex


def digest(value):
    return hashlib.sha256(value.encode()).digest()


def body():
    value = request.get_json(silent=True)
    if not isinstance(value, dict):
        raise ApiError("INVALID_INPUT")
    return value


def field(data, key, minimum=1, maximum=255):
    value = data.get(key)
    if not isinstance(value, str) or not minimum <= len(value.strip()) <= maximum:
        raise ApiError("INVALID_FIELD", field=key)
    return value.strip()


def email(value):
    if not isinstance(value, str):
        raise ApiError("INVALID_EMAIL")
    value = value.strip().lower()
    try:
        local, domain = value.rsplit("@", 1)
        value = local + "@" + domain.encode("idna").decode("ascii")
        value.encode("ascii")
    except (ValueError, UnicodeError):
        raise ApiError("INVALID_EMAIL")
    if len(value) > 254 or not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", value):
        raise ApiError("INVALID_EMAIL")
    return value


def password(value):
    if (
        not isinstance(value, str)
        or not 8 <= len(value) <= 128
        or not re.search("[A-Za-z]", value)
        or not re.search("[0-9]", value)
    ):
        raise ApiError("INVALID_PASSWORD")
    return value


def pagination():
    try:
        page = max(1, min(int(request.args.get("page", 1)), 100000))
        size = max(1, min(int(request.args.get("page_size", 20)), 100))
    except ValueError:
        raise ApiError("INVALID_INPUT")
    return size, (page - 1) * size
