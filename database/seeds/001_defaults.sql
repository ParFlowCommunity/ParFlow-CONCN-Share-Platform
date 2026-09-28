-- Run once after 001_schema.sql in the SAME NEW database.
-- No example users, passwords, basin data or published datasets are created.
SET NAMES utf8mb4 COLLATE utf8mb4_0900_ai_ci;
SET time_zone = '+00:00';
START TRANSACTION;
INSERT INTO basin_levels (pfbas_level,hierarchy_level,label_zh,label_en) VALUES
  (2,1,'一级（PFBAS2）','Level 1 (PFBAS2)'),
  (4,2,'二级（PFBAS4）','Level 2 (PFBAS4)'),
  (6,3,'三级（PFBAS6）','Level 3 (PFBAS6)'),
  (8,4,'四级（PFBAS8）','Level 4 (PFBAS8)'),
  (10,5,'五级（PFBAS10）','Level 5 (PFBAS10)'),
  (12,6,'六级（PFBAS12）','Level 6 (PFBAS12)'),
  (14,7,'七级（PFBAS14）','Level 7 (PFBAS14)');
INSERT INTO access_policies (id,small_min_hierarchy_level,reason)
VALUES (1,5,'初始规则：五至七级为小流域；每账号累计两个不同编码。');
INSERT INTO platform_config (id,current_policy_id) VALUES (1,1);
COMMIT;
