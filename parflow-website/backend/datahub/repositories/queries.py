"""Shared read projections; excludes secrets and internal file paths."""

PUBLIC_USER = (
    "id,username,email,role,status,preferred_locale,email_verified_at,created_at"
)


JOB_SELECT = """SELECT j.id,j.basin_code,w.pfbas_level,j.dataset_version_id,v.version_code,j.application_id,j.access_mode,
 j.package_mode,j.status,j.stage_code,j.error_code,j.created_at,j.updated_at,j.finished_at,
 a.byte_size,a.expires_at,a.state AS archive_state FROM download_jobs j JOIN dataset_versions v ON v.id=j.dataset_version_id
 JOIN watersheds w ON w.basin_code=j.basin_code LEFT JOIN result_archives a ON a.job_id=j.id"""


APP_SELECT = """SELECT a.id,a.user_id,a.basin_code,a.dataset_version_id,v.version_code,a.applicant_name,a.affiliation,
 a.contact_email,a.usage_type,a.usage_title,a.usage_owner,a.purpose,a.project_url,a.status,a.review_comment,
 a.submitted_at,a.reviewed_at,a.authorization_expires_at,a.revoked_at FROM large_basin_applications a
 JOIN dataset_versions v ON v.id=a.dataset_version_id"""
