CREATE TABLE IF NOT EXISTS administrative_regions (
  code CHAR(6) CHARACTER SET ascii NOT NULL,
  kind ENUM('province','city') NOT NULL,
  parent_code CHAR(6) CHARACTER SET ascii NULL,
  name_zh VARCHAR(100) NOT NULL,
  center_lng DOUBLE NOT NULL,
  center_lat DOUBLE NOT NULL,
  view_bounds JSON NOT NULL,
  source_url VARCHAR(255) NOT NULL,
  imported_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY(code,kind),
  KEY ix_region_parent(kind,parent_code,code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
