from collections import defaultdict, deque
from threading import Lock
from urllib.parse import urlsplit
import os
import time
from flask import Flask, jsonify, request, send_from_directory
from flask.json.provider import DefaultJSONProvider
from werkzeug.exceptions import HTTPException
import pymysql
from .config import FRONTEND_DIST
from .repositories.db import json_default
from .common import ApiError, uid


class JSONProvider(DefaultJSONProvider):
    @staticmethod
    def default(obj):
        try:
            return json_default(obj)
        except TypeError:
            return DefaultJSONProvider.default(obj)


def create_app(testing=False):
    app = Flask(__name__, static_folder=None)
    app.json = JSONProvider(app)
    app.json.ensure_ascii = False
    app.config.update(
        TESTING=testing,
        MAX_CONTENT_LENGTH=1024 * 1024,
        COOKIE_SECURE=os.getenv("CONCN_COOKIE_SECURE", "0") == "1",
        REQUIRE_VERIFIED=os.getenv("CONCN_REQUIRE_VERIFIED_EMAIL", "0") == "1",
        PUBLIC_URL=os.getenv("CONCN_PUBLIC_URL", "http://localhost:5173").rstrip("/"),
    )
    if os.getenv("CONCN_ENV", "development") == "production":
        if not app.config["COOKIE_SECURE"] or not app.config["PUBLIC_URL"].startswith(
            "https://"
        ):
            raise RuntimeError(
                "Production requires HTTPS public URL and secure cookies"
            )
    from .api import auth, catalog, applications, content, admin, jobs, downloads, notifications

    for module in (auth, catalog, applications, content, admin, jobs, downloads, notifications):
        app.register_blueprint(module.bp)
    attempts = defaultdict(deque)
    limiter_lock = Lock()

    @app.before_request
    def guard():
        if not request.path.startswith("/api/"):
            return
        if request.method not in ("GET", "HEAD", "OPTIONS"):
            if request.headers.get("X-DataHub") != "1":
                raise ApiError("CSRF_REJECTED", 403)
            origin = request.headers.get("Origin")
            expected = urlsplit(app.config["PUBLIC_URL"])
            if origin and origin not in (
                expected.scheme + "://" + expected.netloc,
                request.host_url.rstrip("/"),
            ):
                raise ApiError("CSRF_REJECTED", 403)
        if not testing and request.method == "POST":
            # Per-process local defense. Deployment nginx also applies a shared IP limit.
            category = (
                "auth"
                if request.path
                in (
                    "/api/register",
                    "/api/login",
                    "/api/forgot-password",
                    "/api/email-action",
                )
                else "write"
            )
            key = (request.remote_addr, category)
            stamp = time.monotonic()
            with limiter_lock:
                queue = attempts[key]
                while queue and queue[0] < stamp - 60:
                    queue.popleft()
                if len(queue) >= (20 if category == "auth" else 60):
                    raise ApiError("RATE_LIMITED", 429)
                queue.append(stamp)
                if len(attempts) > 10000:
                    for k in list(attempts):
                        if not attempts[k] or attempts[k][-1] < stamp - 60:
                            del attempts[k]

    @app.after_request
    def headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "same-origin"
        if request.path.startswith("/api/"):
            response.headers.setdefault("Cache-Control", "no-store")
        if app.config["COOKIE_SECURE"]:
            response.headers["Strict-Transport-Security"] = "max-age=31536000"
        return response

    @app.errorhandler(ApiError)
    def api_error(error):
        return jsonify(error=error.code, params=error.params), error.status

    @app.errorhandler(pymysql.IntegrityError)
    def integrity(error):
        if error.args[0] == 1062:
            return jsonify(error="ACCOUNT_OR_RECORD_EXISTS", params={}), 409
        app.logger.error("Database integrity failure type=%s", error.args[0])
        return jsonify(error="INVALID_INPUT", params={}), 400

    @app.errorhandler(pymysql.OperationalError)
    def unavailable(error):
        app.logger.error("Database unavailable code=%s", error.args[0])
        return jsonify(error="SERVICE_UNAVAILABLE", params={}), 503

    @app.errorhandler(Exception)
    def unexpected(error):
        if isinstance(error, HTTPException):
            return jsonify(
                error="NOT_FOUND" if error.code == 404 else "INVALID_INPUT", params={}
            ), error.code
        trace = uid()
        app.logger.exception("Request failure trace=%s", trace)
        return jsonify(error="INTERNAL_ERROR", params={"trace": trace}), 500

    @app.route("/", defaults={"path": ""})
    @app.route("/<path:path>")
    def frontend(path):
        if path.startswith("api/"):
            raise ApiError("NOT_FOUND", 404)
        dist = FRONTEND_DIST
        resolved = (dist / path).resolve()
        if not resolved.is_relative_to(dist.resolve()):
            raise ApiError("NOT_FOUND", 404)
        return send_from_directory(
            dist, path if path and resolved.is_file() else "index.html"
        )

    return app
