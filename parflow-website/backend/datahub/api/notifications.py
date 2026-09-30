"""Notifications derive from owned review/archive events; only read state is stored."""
from flask import Blueprint, g, jsonify
from ..security.sessions import require_user
from ..common import pagination
from ..repositories.db import transaction, all_rows, one

bp = Blueprint('notifications', __name__)
EVENTS = """SELECT CONCAT('review:',r.id) event_key,r.action kind,a.basin_code,r.comment,
 r.created_at,'/applications' link FROM application_reviews r
 JOIN large_basin_applications a ON a.id=r.application_id
 WHERE a.user_id=%s AND r.action IN ('approve','reject','revoke')
 UNION ALL SELECT CONCAT('archive:',a.id),'ready',j.basin_code,'',a.created_at,'/downloads'
 FROM result_archives a JOIN download_jobs j ON j.id=a.job_id WHERE j.user_id=%s"""


@bp.get('/api/notifications')
@require_user
def notifications():
    size, offset = pagination()
    user = g.user['id']
    with transaction() as c:
        rows = all_rows(c, f"SELECT e.*,n.read_at FROM ({EVENTS}) e LEFT JOIN notification_reads n ON n.user_id=%s AND n.event_key=e.event_key ORDER BY e.created_at DESC,e.event_key DESC LIMIT %s OFFSET %s", (user,user,user,size,offset))
        counts = one(c, f"SELECT COUNT(*) total,COALESCE(SUM(n.event_key IS NULL),0) unread FROM ({EVENTS}) e LEFT JOIN notification_reads n ON n.user_id=%s AND n.event_key=e.event_key", (user,user,user))
    return jsonify(items=rows, **counts)


@bp.post('/api/notifications/read')
@require_user
def mark_read():
    user = g.user['id']
    with transaction() as c:
        c.execute(f"INSERT INTO notification_reads(user_id,event_key) SELECT %s,e.event_key FROM ({EVENTS}) e ON DUPLICATE KEY UPDATE read_at=notification_reads.read_at", (user,user,user))
    return jsonify(ok=True)
