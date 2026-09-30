from flask import Blueprint, g, jsonify, request
from ..security.sessions import require_user
from ..common import ApiError, body, field, now
from ..repositories.db import transaction, all_rows, one, audit

bp = Blueprint("content", __name__)


@bp.get("/api/content")
def content():
    kind = request.args.get("kind", "help")
    with transaction() as c:
        rows = all_rows(
            c,
            "SELECT slug,title_zh,title_en,body_zh,body_en,published_at FROM content_pages WHERE kind=%s AND status='published' ORDER BY published_at DESC,id DESC LIMIT 50",
            (kind,),
        )
    return jsonify(items=rows)


@bp.get("/api/admin/content")
@require_user(admin=True)
def admin_content():
    with transaction() as c:
        rows = all_rows(c, "SELECT * FROM content_pages ORDER BY id DESC LIMIT 100")
    return jsonify(items=rows)


@bp.post("/api/admin/content")
@bp.put("/api/admin/content/<int:content_id>")
@require_user(admin=True)
def content_create(content_id=None):
    data = body()
    kind = data.get("kind")
    status = data.get("status", "draft")
    if kind not in ("help", "notice", "home", "terms", "privacy") or status not in (
        "draft",
        "published",
    ):
        raise ApiError("INVALID_INPUT")
    vals = [
        field(data, key, 1, limit)
        for key, limit in [
            ("slug", 128),
            ("title_zh", 200),
            ("title_en", 200),
            ("body_zh", 100000),
            ("body_en", 100000),
        ]
    ]
    with transaction() as c:
        if content_id is not None:
            existing = one(c, "SELECT id,published_at FROM content_pages WHERE id=%s FOR UPDATE", (content_id,))
            if not existing:
                raise ApiError("NOT_FOUND", 404)
            c.execute(
                "UPDATE content_pages SET slug=%s,title_zh=%s,title_en=%s,body_zh=%s,body_en=%s,kind=%s,status=%s,published_at=%s,updated_by=%s WHERE id=%s",
                (*vals, kind, status, (existing["published_at"] or now()) if status == "published" else None, g.user["id"], content_id),
            )
            audit(c, g.user["id"], "content.update", "content", content_id, {"slug": vals[0]})
            return jsonify(ok=True)
        c.execute(
            "INSERT INTO content_pages(slug,title_zh,title_en,body_zh,body_en,kind,status,published_at,updated_by) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            (
                *vals,
                kind,
                status,
                now() if status == "published" else None,
                g.user["id"],
            ),
        )
        audit(
            c, g.user["id"], "content.create", "content", c.lastrowid, {"slug": vals[0]}
        )
    return jsonify(ok=True), 201
