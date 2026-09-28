from flask import request
from ..common import ApiError


def idempotency():
    value = request.headers.get("Idempotency-Key", "")
    if not 8 <= len(value) <= 64 or not value.isascii():
        raise ApiError("IDEMPOTENCY_REQUIRED")
    return value
