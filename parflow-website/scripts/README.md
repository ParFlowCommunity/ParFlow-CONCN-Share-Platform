# 已有操作命令索引

命令实现在 `backend/datahub/cli.py`，从 `backend` 目录使用对应 Python 环境执行。这里不复制命令实现。

| 命令 | 作用 |
| --- | --- |
| `python -m datahub.cli --help` | 查看帮助，不修改数据库 |
| `python -m datahub.cli bootstrap` | 全新本地环境初始化，交互输入 MySQL 管理密码 |
| `python -m datahub.cli admin` | 交互创建管理员 |
| `python -m datahub.cli import-catalog 文件路径` | 追加导入经过校验的 JSON 流域目录 |
| `python -m datahub.cli publish-local` | 校验本地源文件与七级目录，发布本地验证版本；仅限 development 和本地 MySQL，相同版本拒绝覆盖 |

`bootstrap` 仅用于空环境，会拒绝覆盖已有配置、数据库或应用用户。恢复业务库时不要执行。

单独的目录导入不会发布版本。`publish-local` 会同时接入经过校验的真实目录与本地版本；相同版本不可重复覆盖。

## Linux 启动入口

先 `conda activate concnshare`，在项目根目录执行：

| 命令 | 作用 |
| --- | --- |
| `bash scripts/run-linux.sh web` | 前台启动网站，读取 backend/.env |
| `bash scripts/run-linux.sh worker` | 前台运行裁切队列，需另开终端 |
| `bash scripts/run-linux.sh build` | 构建网页，需已有 Node 和 npm 依赖 |
| `bash scripts/run-linux.sh check` | 只读请求本机健康接口 |

`import_regions.py` 导入省市导航范围，已有目录无需重复导入。Linux 启动使用 run-linux.sh，系统防火墙与进程托管由部署方配置。
详细步骤见 [部署说明](../docs/部署说明-v1.0.md)。
