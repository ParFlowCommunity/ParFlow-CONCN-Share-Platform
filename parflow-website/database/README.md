# MySQL 脚本

- `migrations/001_schema.sql`：21 张表的初始结构。
- `migrations/002_regions.sql`：行政区域导航表。
- `migrations/003_notification_reads.sql`：通知已读记录表。
- `migrations/004_application_usage.sql`：申请表用途字段（用途类别、项目名称/论文题目、负责人/论文类型），并把旧的申请原因列置为可空。
- `seeds/001_defaults.sql`：七级流域映射与默认平台规则。

初始化需按 CLI 的流程执行迁移和默认数据脚本，当前共 23 张表。仅用于全新空数据库；不要在已初始化的业务库中重复执行。

后续结构变更应新增编号 SQL，不改写已执行的初始脚本。当前没有自动增量迁移执行器。MySQL 存储账号、目录、权限与任务记录，源数据及 ZIP 存在文件目录中。

详细字段和约束见 [数据库设计](../docs/数据库说明.md)。
