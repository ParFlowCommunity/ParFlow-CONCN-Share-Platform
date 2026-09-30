-- ParFlow CONCN Share Platform schema v1, target: MySQL 8.4 / InnoDB.
-- Run once in a NEW, explicitly selected database. No DROP / TRUNCATE.
-- Application and migration connections must use UTC and strict SQL mode.
-- Status transitions, role checks and authorization expiry require service logic.
SET NAMES utf8mb4 COLLATE utf8mb4_0900_ai_ci;
SET time_zone = '+00:00';

CREATE TABLE users (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  username VARCHAR(64) NOT NULL,
  email VARCHAR(254) CHARACTER SET ascii COLLATE ascii_general_ci NOT NULL COMMENT 'Canonical ASCII email: trim, lowercase, IDNA domain in application',
  password_hash VARCHAR(255) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  role ENUM('user','admin') NOT NULL DEFAULT 'user',
  status ENUM('active','disabled') NOT NULL DEFAULT 'active',
  preferred_locale VARCHAR(5) CHARACTER SET ascii COLLATE ascii_bin NOT NULL DEFAULT 'zh-CN',
  email_verified_at DATETIME(6) NULL,
  failed_login_count SMALLINT UNSIGNED NOT NULL DEFAULT 0,
  locked_until DATETIME(6) NULL,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  PRIMARY KEY (id),
  UNIQUE KEY uq_users_username (username),
  UNIQUE KEY uq_users_email (email),
  CONSTRAINT ck_users_locale CHECK (preferred_locale IN ('zh-CN','en')),
  CONSTRAINT ck_users_email_trim CHECK (CHAR_LENGTH(email) = CHAR_LENGTH(TRIM(email)) AND CHAR_LENGTH(email) > 3)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE auth_sessions (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  user_id BIGINT UNSIGNED NOT NULL,
  token_hash BINARY(32) NOT NULL COMMENT 'SHA-256 of high-entropy bearer token; never raw token',
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  expires_at DATETIME(6) NOT NULL,
  revoked_at DATETIME(6) NULL,
  PRIMARY KEY (id), UNIQUE KEY uq_auth_token (token_hash),
  KEY ix_auth_user_expiry (user_id, expires_at), KEY ix_auth_expiry (expires_at),
  CONSTRAINT fk_auth_user FOREIGN KEY (user_id) REFERENCES users(id),
  CONSTRAINT ck_auth_expiry CHECK (expires_at > created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE email_actions (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  user_id BIGINT UNSIGNED NOT NULL,
  purpose ENUM('verify_email','change_email','reset_password') NOT NULL,
  target_email VARCHAR(254) CHARACTER SET ascii COLLATE ascii_general_ci NOT NULL,
  token_hash BINARY(32) NOT NULL,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  expires_at DATETIME(6) NOT NULL,
  consumed_at DATETIME(6) NULL,
  revoked_at DATETIME(6) NULL,
  PRIMARY KEY (id), UNIQUE KEY uq_email_action_token (token_hash),
  KEY ix_email_action_user (user_id,purpose,created_at), KEY ix_email_action_expiry (expires_at),
  CONSTRAINT fk_email_action_user FOREIGN KEY (user_id) REFERENCES users(id),
  CONSTRAINT ck_email_action_expiry CHECK (expires_at > created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE basin_levels (
  pfbas_level TINYINT UNSIGNED NOT NULL,
  hierarchy_level TINYINT UNSIGNED NOT NULL,
  label_zh VARCHAR(32) NOT NULL,
  label_en VARCHAR(64) NOT NULL,
  PRIMARY KEY (pfbas_level), UNIQUE KEY uq_basin_hierarchy (hierarchy_level),
  CONSTRAINT ck_basin_level_map CHECK (hierarchy_level BETWEEN 1 AND 7 AND pfbas_level = hierarchy_level * 2)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE access_policies (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  small_min_hierarchy_level TINYINT UNSIGNED NOT NULL,
  reason VARCHAR(1000) NOT NULL,
  created_by BIGINT UNSIGNED NULL COMMENT 'NULL only for bootstrap policy',
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  PRIMARY KEY (id),
  CONSTRAINT fk_policy_level FOREIGN KEY (small_min_hierarchy_level) REFERENCES basin_levels(hierarchy_level),
  CONSTRAINT fk_policy_creator FOREIGN KEY (created_by) REFERENCES users(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE platform_config (
  id TINYINT UNSIGNED NOT NULL,
  current_policy_id BIGINT UNSIGNED NOT NULL,
  result_retention_hours INT UNSIGNED NOT NULL DEFAULT 72 COMMENT 'Proposed, to confirm',
  approval_validity_hours INT UNSIGNED NOT NULL DEFAULT 168 COMMENT 'Proposed, to confirm',
  maintenance_mode BOOLEAN NOT NULL DEFAULT FALSE,
  updated_by BIGINT UNSIGNED NULL,
  updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  PRIMARY KEY (id),
  CONSTRAINT ck_config_singleton CHECK (id = 1),
  CONSTRAINT ck_config_retention CHECK (result_retention_hours > 0 AND approval_validity_hours > 0),
  CONSTRAINT ck_config_maintenance CHECK (maintenance_mode IN (0,1)),
  CONSTRAINT fk_config_policy FOREIGN KEY (current_policy_id) REFERENCES access_policies(id),
  CONSTRAINT fk_config_editor FOREIGN KEY (updated_by) REFERENCES users(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE watersheds (
  basin_code CHAR(14) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  pfbas_level TINYINT UNSIGNED NOT NULL,
  parent_code CHAR(14) CHARACTER SET ascii COLLATE ascii_bin NULL,
  name_zh VARCHAR(200) NULL, name_en VARCHAR(200) NULL,
  region_zh VARCHAR(100) NULL, region_en VARCHAR(100) NULL,
  area_km2 DECIMAL(18,6) NULL,
  center_lng DECIMAL(11,7) NULL, center_lat DECIMAL(10,7) NULL,
  bbox_wgs84 JSON NULL,
  status ENUM('available','unavailable') NOT NULL DEFAULT 'unavailable',
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  PRIMARY KEY (basin_code),
  KEY ix_watershed_level (pfbas_level,status,basin_code), KEY ix_watershed_parent (parent_code),
  KEY ix_watershed_name_zh (name_zh), KEY ix_watershed_name_en (name_en),
  CONSTRAINT fk_watershed_level FOREIGN KEY (pfbas_level) REFERENCES basin_levels(pfbas_level),
  CONSTRAINT fk_watershed_parent FOREIGN KEY (parent_code) REFERENCES watersheds(basin_code),
  CONSTRAINT ck_watershed_code CHECK (REGEXP_LIKE(basin_code,'^[0-9]{14}$','c')),
  CONSTRAINT ck_watershed_parent CHECK (parent_code IS NULL OR parent_code <> basin_code),
  CONSTRAINT ck_watershed_area CHECK (area_km2 IS NULL OR area_km2 >= 0),
  CONSTRAINT ck_watershed_lng CHECK (center_lng IS NULL OR center_lng BETWEEN -180 AND 180),
  CONSTRAINT ck_watershed_lat CHECK (center_lat IS NULL OR center_lat BETWEEN -90 AND 90)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE dataset_versions (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  version_code VARCHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  title_zh VARCHAR(200) NOT NULL, title_en VARCHAR(200) NOT NULL,
  description_zh TEXT NULL, description_en TEXT NULL,
  status ENUM('draft','published','withdrawn') NOT NULL DEFAULT 'draft',
  boundary_version VARCHAR(100) NOT NULL,
  clip_version VARCHAR(100) NOT NULL,
  manifest_sha256 BINARY(32) NULL COMMENT 'Frozen source/parameter manifest digest',
  grid_metadata JSON NOT NULL,
  citation TEXT NOT NULL,
  terms_version VARCHAR(64) NOT NULL,
  license_text_zh TEXT NOT NULL, license_text_en TEXT NOT NULL,
  published_at DATETIME(6) NULL,
  created_by BIGINT UNSIGNED NULL,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  PRIMARY KEY (id), UNIQUE KEY uq_dataset_version (version_code),
  CONSTRAINT fk_dataset_creator FOREIGN KEY (created_by) REFERENCES users(id),
  CONSTRAINT ck_dataset_publish CHECK (status <> 'published' OR (published_at IS NOT NULL AND manifest_sha256 IS NOT NULL))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE dataset_files (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  dataset_version_id BIGINT UNSIGNED NOT NULL,
  item_code VARCHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  title_zh VARCHAR(200) NOT NULL, title_en VARCHAR(200) NOT NULL,
  units VARCHAR(100) NULL,
  storage_key VARCHAR(1000) NOT NULL COMMENT 'Private logical source key or generated recipe key',
  file_kind ENUM('source','generated') NOT NULL,
  source_sha256 BINARY(32) NULL,
  output_name_template VARCHAR(255) NOT NULL,
  metadata JSON NULL,
  PRIMARY KEY (id), UNIQUE KEY uq_dataset_item (dataset_version_id,item_code),
  CONSTRAINT fk_dataset_file_version FOREIGN KEY (dataset_version_id) REFERENCES dataset_versions(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE watershed_datasets (
  basin_code CHAR(14) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  dataset_version_id BIGINT UNSIGNED NOT NULL,
  status ENUM('available','unavailable') NOT NULL DEFAULT 'unavailable',
  unavailable_reason_zh VARCHAR(1000) NULL, unavailable_reason_en VARCHAR(1000) NULL,
  estimated_zip_bytes BIGINT UNSIGNED NULL,
  estimated_peak_memory_bytes BIGINT UNSIGNED NULL,
  boundary_storage_key VARCHAR(1000) NULL,
  PRIMARY KEY (basin_code,dataset_version_id),
  KEY ix_availability_version (dataset_version_id,status,basin_code),
  CONSTRAINT fk_availability_basin FOREIGN KEY (basin_code) REFERENCES watersheds(basin_code),
  CONSTRAINT fk_availability_version FOREIGN KEY (dataset_version_id) REFERENCES dataset_versions(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE small_basin_slots (
  user_id BIGINT UNSIGNED NOT NULL,
  slot_no TINYINT UNSIGNED NOT NULL,
  basin_code CHAR(14) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  policy_id BIGINT UNSIGNED NOT NULL,
  state ENUM('reserved','active') NOT NULL DEFAULT 'reserved',
  reserved_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  activated_at DATETIME(6) NULL,
  PRIMARY KEY (user_id,slot_no),
  UNIQUE KEY uq_small_slot_basin (user_id,basin_code),
  KEY ix_small_reservations (state,reserved_at),
  CONSTRAINT ck_small_slot_two CHECK (slot_no IN (1,2)),
  CONSTRAINT ck_small_slot_activation CHECK ((state='reserved' AND activated_at IS NULL) OR (state='active' AND activated_at IS NOT NULL)),
  CONSTRAINT fk_small_slot_user FOREIGN KEY (user_id) REFERENCES users(id),
  CONSTRAINT fk_small_slot_basin FOREIGN KEY (basin_code) REFERENCES watersheds(basin_code),
  CONSTRAINT fk_small_slot_policy FOREIGN KEY (policy_id) REFERENCES access_policies(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE large_basin_applications (
  id CHAR(32) CHARACTER SET ascii COLLATE ascii_bin NOT NULL COMMENT 'Random UUID hex',
  user_id BIGINT UNSIGNED NOT NULL,
  basin_code CHAR(14) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  dataset_version_id BIGINT UNSIGNED NOT NULL,
  policy_id BIGINT UNSIGNED NOT NULL,
  package_mode VARCHAR(16) CHARACTER SET ascii COLLATE ascii_bin NOT NULL DEFAULT 'full',
  applicant_name VARCHAR(100) NOT NULL,
  affiliation VARCHAR(255) NOT NULL,
  contact_email VARCHAR(254) CHARACTER SET ascii COLLATE ascii_general_ci NOT NULL,
  purpose TEXT NOT NULL, large_basin_reason TEXT NOT NULL,
  project_url VARCHAR(2000) NULL,
  terms_version VARCHAR(64) NOT NULL, terms_accepted_at DATETIME(6) NOT NULL,
  request_snapshot JSON NOT NULL,
  idempotency_key VARCHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  request_hash BINARY(32) NOT NULL,
  status ENUM('pending','approved','rejected','withdrawn','revoked') NOT NULL DEFAULT 'pending',
  reviewed_by BIGINT UNSIGNED NULL, reviewed_at DATETIME(6) NULL,
  review_comment TEXT NULL,
  authorization_expires_at DATETIME(6) NULL,
  revoked_at DATETIME(6) NULL,
  submitted_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  PRIMARY KEY (id),
  UNIQUE KEY uq_application_idempotency (user_id,idempotency_key),
  UNIQUE KEY uq_application_scope (id,user_id,basin_code,dataset_version_id),
  KEY ix_application_inbox (status,submitted_at,id),
  KEY ix_application_history (user_id,submitted_at,id),
  CONSTRAINT fk_application_user FOREIGN KEY (user_id) REFERENCES users(id),
  CONSTRAINT fk_application_dataset FOREIGN KEY (basin_code,dataset_version_id) REFERENCES watershed_datasets(basin_code,dataset_version_id),
  CONSTRAINT fk_application_policy FOREIGN KEY (policy_id) REFERENCES access_policies(id),
  CONSTRAINT fk_application_reviewer FOREIGN KEY (reviewed_by) REFERENCES users(id),
  CONSTRAINT ck_application_full CHECK (package_mode='full'),
  CONSTRAINT ck_application_review CHECK (status NOT IN ('approved','rejected','revoked') OR (reviewed_by IS NOT NULL AND reviewed_at IS NOT NULL AND review_comment IS NOT NULL)),
  CONSTRAINT ck_application_grant CHECK (status NOT IN ('approved','revoked') OR (authorization_expires_at IS NOT NULL AND authorization_expires_at > reviewed_at)),
  CONSTRAINT ck_application_revoke CHECK (status <> 'revoked' OR revoked_at IS NOT NULL)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE application_reviews (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  application_id CHAR(32) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  actor_user_id BIGINT UNSIGNED NOT NULL,
  action ENUM('approve','reject','revoke','withdraw') NOT NULL,
  comment TEXT NOT NULL,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  PRIMARY KEY (id), KEY ix_review_application (application_id,created_at,id),
  CONSTRAINT fk_review_application FOREIGN KEY (application_id) REFERENCES large_basin_applications(id),
  CONSTRAINT fk_review_actor FOREIGN KEY (actor_user_id) REFERENCES users(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE download_jobs (
  id CHAR(32) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  user_id BIGINT UNSIGNED NOT NULL,
  basin_code CHAR(14) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  dataset_version_id BIGINT UNSIGNED NOT NULL,
  policy_id BIGINT UNSIGNED NOT NULL,
  access_mode ENUM('small','approved_large') NOT NULL,
  application_id CHAR(32) CHARACTER SET ascii COLLATE ascii_bin NULL,
  package_mode VARCHAR(16) CHARACTER SET ascii COLLATE ascii_bin NOT NULL DEFAULT 'full',
  request_snapshot JSON NOT NULL,
  idempotency_key VARCHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  request_hash BINARY(32) NOT NULL,
  terms_version VARCHAR(64) NOT NULL, terms_accepted_at DATETIME(6) NOT NULL,
  status ENUM('queued','running','packaging','succeeded','failed','cancel_requested','cancelled','expired') NOT NULL DEFAULT 'queued',
  stage_code VARCHAR(64) CHARACTER SET ascii COLLATE ascii_bin NULL,
  current_attempt INT UNSIGNED NOT NULL DEFAULT 0,
  heartbeat_at DATETIME(6) NULL,
  error_code VARCHAR(64) CHARACTER SET ascii COLLATE ascii_bin NULL,
  error_params JSON NULL,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  finished_at DATETIME(6) NULL,
  PRIMARY KEY (id), UNIQUE KEY uq_job_owner (id,user_id),
  UNIQUE KEY uq_job_idempotency (user_id,idempotency_key),
  KEY ix_job_history (user_id,created_at,id), KEY ix_job_queue (status,created_at,id),
  KEY ix_job_slot_refs (user_id,basin_code,access_mode,status),
  CONSTRAINT fk_job_user FOREIGN KEY (user_id) REFERENCES users(id),
  CONSTRAINT fk_job_dataset FOREIGN KEY (basin_code,dataset_version_id) REFERENCES watershed_datasets(basin_code,dataset_version_id),
  CONSTRAINT fk_job_policy FOREIGN KEY (policy_id) REFERENCES access_policies(id),
  CONSTRAINT fk_job_application_scope FOREIGN KEY (application_id,user_id,basin_code,dataset_version_id) REFERENCES large_basin_applications(id,user_id,basin_code,dataset_version_id),
  CONSTRAINT ck_job_access CHECK ((access_mode='small' AND application_id IS NULL) OR (access_mode='approved_large' AND application_id IS NOT NULL)),
  CONSTRAINT ck_job_full CHECK (package_mode='full')
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE job_attempts (
  job_id CHAR(32) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  attempt_no INT UNSIGNED NOT NULL,
  worker_id VARCHAR(128) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  state ENUM('running','succeeded','failed','cancelled','lost') NOT NULL DEFAULT 'running',
  lease_expires_at DATETIME(6) NOT NULL,
  work_storage_key VARCHAR(1000) NOT NULL,
  error_code VARCHAR(64) CHARACTER SET ascii COLLATE ascii_bin NULL,
  started_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  finished_at DATETIME(6) NULL,
  PRIMARY KEY (job_id,attempt_no), KEY ix_attempt_leases (state,lease_expires_at),
  CONSTRAINT fk_attempt_job FOREIGN KEY (job_id) REFERENCES download_jobs(id),
  CONSTRAINT ck_attempt_number CHECK (attempt_no > 0)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE result_archives (
  id CHAR(32) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  job_id CHAR(32) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  attempt_no INT UNSIGNED NOT NULL,
  storage_key VARCHAR(1000) NOT NULL,
  byte_size BIGINT UNSIGNED NOT NULL,
  sha256 BINARY(32) NOT NULL,
  file_manifest JSON NOT NULL,
  state ENUM('available','deleting','deleted','revoked') NOT NULL DEFAULT 'available',
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  expires_at DATETIME(6) NOT NULL, deleted_at DATETIME(6) NULL,
  PRIMARY KEY (id), UNIQUE KEY uq_archive_job (job_id), UNIQUE KEY uq_archive_scope (id,job_id),
  KEY ix_archive_cleanup (state,expires_at),
  CONSTRAINT fk_archive_attempt FOREIGN KEY (job_id,attempt_no) REFERENCES job_attempts(job_id,attempt_no),
  CONSTRAINT ck_archive_size CHECK (byte_size > 0),
  CONSTRAINT ck_archive_expiry CHECK (expires_at > created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE download_sessions (
  id CHAR(32) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  user_id BIGINT UNSIGNED NOT NULL,
  job_id CHAR(32) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  archive_id CHAR(32) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  token_hash BINARY(32) NOT NULL,
  authorized_bytes BIGINT UNSIGNED NOT NULL,
  transferred_bytes BIGINT UNSIGNED NOT NULL DEFAULT 0 COMMENT 'Actual transport logs, may exceed file size due to retries',
  status ENUM('active','revoked','expired') NOT NULL DEFAULT 'active',
  transfer_lease_until DATETIME(6) NULL COMMENT 'File service renews while transmitting; cleanup must honor this lease',
  usage_date DATE NOT NULL COMMENT 'Asia/Shanghai accounting date, computed by service',
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  expires_at DATETIME(6) NOT NULL,
  PRIMARY KEY (id), UNIQUE KEY uq_download_token (token_hash),
  KEY ix_download_history (user_id,created_at,id),
  KEY ix_download_active (archive_id,status,expires_at),
  CONSTRAINT fk_download_owner FOREIGN KEY (job_id,user_id) REFERENCES download_jobs(id,user_id),
  CONSTRAINT fk_download_archive FOREIGN KEY (archive_id,job_id) REFERENCES result_archives(id,job_id),
  CONSTRAINT ck_download_expiry CHECK (expires_at > created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE usage_daily (
  user_id BIGINT UNSIGNED NOT NULL,
  usage_date DATE NOT NULL,
  accepted_jobs INT UNSIGNED NOT NULL DEFAULT 0,
  authorized_bytes BIGINT UNSIGNED NOT NULL DEFAULT 0,
  transferred_bytes BIGINT UNSIGNED NOT NULL DEFAULT 0,
  PRIMARY KEY (user_id,usage_date),
  CONSTRAINT fk_usage_user FOREIGN KEY (user_id) REFERENCES users(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE task_outbox (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  job_id CHAR(32) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  dispatch_no INT UNSIGNED NOT NULL DEFAULT 1,
  state ENUM('pending','publishing','published') NOT NULL DEFAULT 'pending',
  next_attempt_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  lease_expires_at DATETIME(6) NULL,
  publish_attempts INT UNSIGNED NOT NULL DEFAULT 0,
  published_at DATETIME(6) NULL,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  PRIMARY KEY (id), UNIQUE KEY uq_outbox_dispatch (job_id,dispatch_no),
  KEY ix_outbox_due (state,next_attempt_at),
  CONSTRAINT fk_outbox_job FOREIGN KEY (job_id) REFERENCES download_jobs(id),
  CONSTRAINT ck_outbox_dispatch CHECK (dispatch_no > 0)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE content_pages (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  slug VARCHAR(128) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  kind ENUM('home','help','notice','terms','privacy') NOT NULL,
  title_zh VARCHAR(200) NOT NULL, title_en VARCHAR(200) NOT NULL,
  body_zh MEDIUMTEXT NOT NULL, body_en MEDIUMTEXT NOT NULL,
  status ENUM('draft','published','archived') NOT NULL DEFAULT 'draft',
  content_version INT UNSIGNED NOT NULL DEFAULT 1,
  published_at DATETIME(6) NULL,
  updated_by BIGINT UNSIGNED NULL,
  updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  PRIMARY KEY (id), UNIQUE KEY uq_content_slug (slug), KEY ix_content_public (kind,status,published_at),
  CONSTRAINT fk_content_editor FOREIGN KEY (updated_by) REFERENCES users(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE audit_logs (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  actor_user_id BIGINT UNSIGNED NULL COMMENT 'NULL for system events',
  action_code VARCHAR(100) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  object_type VARCHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  object_id VARCHAR(128) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  trace_id CHAR(32) CHARACTER SET ascii COLLATE ascii_bin NULL,
  details JSON NOT NULL COMMENT 'Redacted before/after/reason; never passwords or raw tokens',
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  PRIMARY KEY (id), KEY ix_audit_object (object_type,object_id,created_at),
  KEY ix_audit_actor (actor_user_id,created_at),
  CONSTRAINT fk_audit_actor FOREIGN KEY (actor_user_id) REFERENCES users(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
