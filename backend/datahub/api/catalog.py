import os
import re
from flask import Blueprint, jsonify, request, g
from ..security.sessions import require_user
from ..common import ApiError, pagination
from ..repositories.db import transaction, one, all_rows, decoded

bp = Blueprint("catalog", __name__)


@bp.get('/api/watersheds/<code>/download-access')
@require_user(download=True)
def download_access(code):
    from ..services.access import dataset, lock_context
    value = request.args.get('version', '')
    if not re.fullmatch('[0-9]{14}', code) or not value.isascii() or not value.isdigit():
        raise ApiError('INVALID_INPUT')
    with transaction() as c:
        cfg = lock_context(c, g.user['id'])
        v = dataset(c, code, int(value))
        slots = all_rows(c, 'SELECT basin_code FROM small_basin_slots WHERE user_id=%s', (g.user['id'],))
        direct = any(s['basin_code'] == code for s in slots) or (len(slots) < 2 and v['pfbas_level']//2 >= cfg['small_min_hierarchy_level'])
        approved = one(c, "SELECT id FROM large_basin_applications WHERE user_id=%s AND basin_code=%s AND dataset_version_id=%s AND status='approved' AND authorization_expires_at>UTC_TIMESTAMP(6) ORDER BY authorization_expires_at DESC LIMIT 1", (g.user['id'], code, int(value)))
    return jsonify(direct=direct, application_id=approved['id'] if approved and not direct else None)


@bp.get("/api/regions")
def regions():
    parent = request.args.get("province", "")
    if parent and (len(parent) != 6 or not parent.isascii() or not parent.isdigit()):
        raise ApiError("INVALID_INPUT")
    with transaction() as c:
        rows = all_rows(c,
            "SELECT code,name_zh,kind,parent_code,center_lng,center_lat,view_bounds FROM administrative_regions WHERE kind=%s AND (parent_code=%s OR (%s='' AND parent_code IS NULL)) ORDER BY code",
            ('city' if parent else 'province', parent, parent))
    for row in rows:
        row['view_bounds'] = decoded(row['view_bounds'])
    return jsonify(items=rows)


@bp.get("/api/health")
def health():
    with transaction() as c:
        one(c, "SELECT 1")
    return jsonify(status="ok", database="mysql")


@bp.get("/api/config")
def config():
    with transaction() as c:
        cfg = one(
            c,
            "SELECT c.current_policy_id,c.result_retention_hours,c.approval_validity_hours,c.maintenance_mode,p.small_min_hierarchy_level FROM platform_config c JOIN access_policies p ON c.current_policy_id=p.id WHERE c.id=1",
        )
        cfg["levels"] = all_rows(
            c, "SELECT * FROM basin_levels ORDER BY hierarchy_level"
        )
        cfg["basin_count"] = one(c, "SELECT COUNT(*) n FROM watersheds")["n"]
        cfg["release_count"] = one(
            c, "SELECT COUNT(*) n FROM dataset_versions WHERE status='published'"
        )["n"]
        cfg.update(
            small_basin_limit=2,
            package_mode="full",
            email_available=bool(os.getenv("SMTP_HOST")),
            require_verified_email=os.getenv("CONCN_REQUIRE_VERIFIED_EMAIL", "0")
            == "1",
        )
    return jsonify(cfg)


@bp.get("/api/watersheds")
def watersheds():
    size, offset = pagination()
    where = ["1=1"]
    args = []
    q = request.args.get("q", "")
    level = request.args.get("level", "")
    if "q" in request.args:
        if not re.fullmatch(r"[0-9]{14}", q):
            raise ApiError("INVALID_INPUT")
        where.append("basin_code=%s")
        args.append(q)
    if level:
        if level not in [str(i) for i in range(1, 8)]:
            raise ApiError("INVALID_INPUT")
        where.append("pfbas_level=%s")
        args.append(int(level) * 2)
    parent = request.args.get("parent", "")
    if parent:
        where.append("parent_code=%s")
        args.append(parent)
    clause = " AND ".join(where)
    with transaction() as c:
        total = one(c, "SELECT COUNT(*) n FROM watersheds WHERE " + clause, args)["n"]
        rows = all_rows(
            c,
            "SELECT * FROM watersheds WHERE "
            + clause
            + " ORDER BY basin_code LIMIT %s OFFSET %s",
            [*args, size, offset],
        )
    for r in rows:
        r["bbox_wgs84"] = decoded(r["bbox_wgs84"])
    return jsonify(items=rows, total=total)


@bp.get("/api/watersheds/<code>")
def watershed(code):
    with transaction() as c:
        row = one(c, "SELECT * FROM watersheds WHERE basin_code=%s", (code,))
        if not row:
            raise ApiError("NOT_FOUND", 404)
        row["versions"] = all_rows(
            c,
            "SELECT v.id,v.version_code,v.title_zh,v.title_en,d.status,d.estimated_zip_bytes,d.unavailable_reason_zh,d.unavailable_reason_en FROM watershed_datasets d JOIN dataset_versions v ON d.dataset_version_id=v.id WHERE d.basin_code=%s AND v.status='published' ORDER BY v.published_at DESC",
            (code,),
        )
    row["bbox_wgs84"] = decoded(row["bbox_wgs84"])
    return jsonify(row)


@bp.get("/api/datasets")
def datasets():
    with transaction() as c:
        rows = all_rows(
            c,
            "SELECT id,version_code,title_zh,title_en,description_zh,description_en,boundary_version,clip_version,citation,terms_version,license_text_zh,license_text_en,published_at FROM dataset_versions WHERE status='published' ORDER BY published_at DESC",
        )
        for row in rows:
            row["files"] = all_rows(
                c,
                "SELECT item_code,title_zh,title_en,units,output_name_template FROM dataset_files WHERE dataset_version_id=%s ORDER BY item_code",
                (row["id"],),
            )
    return jsonify(items=rows)


@bp.get("/api/boundaries")
def boundaries():
    from ..integrations.boundaries import get_boundary

    code = request.args.get("basin_code", "")
    if not code and "level" in request.args:
        from ..integrations.boundary_layers import layer_response

        value = request.args.get("level", "")
        if value not in {str(n) for n in range(2, 15, 2)}:
            raise ApiError("INVALID_INPUT")
        return layer_response(int(value))
    with transaction() as c:
        w = one(c, "SELECT pfbas_level FROM watersheds WHERE basin_code=%s", (code,))
    if not w:
        raise ApiError("NOT_FOUND", 404)
    return jsonify(get_boundary(code, w["pfbas_level"]))
