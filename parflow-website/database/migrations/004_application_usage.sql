-- 申请表把原“使用目的”与“申请原因”两栏合并为“用途 + 申请理由”。
-- 用途分项目与论文两类，各自带一组描述字段；申请理由沿用 purpose 列。
-- 适用于已执行过 003 的库；可重复执行。
SET @sql = IF(
  (SELECT COUNT(*) FROM information_schema.columns
    WHERE table_schema = DATABASE() AND table_name = 'large_basin_applications'
      AND column_name = 'usage_type') = 0,
  'ALTER TABLE large_basin_applications
     ADD COLUMN usage_type ENUM(''project'',''thesis'') NOT NULL DEFAULT ''project'' COMMENT ''用途类别: 项目/论文'' AFTER contact_email,
     ADD COLUMN usage_title VARCHAR(255) NOT NULL DEFAULT '''' COMMENT ''项目名称或论文题目'' AFTER usage_type,
     ADD COLUMN usage_owner VARCHAR(255) NOT NULL DEFAULT '''' COMMENT ''项目负责人或论文类型'' AFTER usage_title',
  'SELECT ''usage columns already present'' AS skipped');
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- 旧的“申请原因”正是被合并掉的那一栏，历史行保留原值，新申请不再写入。
ALTER TABLE large_basin_applications MODIFY COLUMN large_basin_reason TEXT NULL;
