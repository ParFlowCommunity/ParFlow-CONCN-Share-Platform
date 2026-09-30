# 网站后端

安装依赖并激活 Conda 环境，从项目根目录运行：

```bash
conda activate concnshare
bash scripts/run-linux.sh web
```

另一个终端同样激活环境，运行 `bash scripts/run-linux.sh worker`。前者启动 Waitress/Flask，提供 `frontend/dist` 和 API；后者领取 MySQL 下载任务并裁切。`backend/.env` 自动加载，已有数据库不要再次 bootstrap。

新环境依赖安装：`python -m pip install -r backend/requirements/worker.txt`；其中包含网站依赖。只运行 API 可安装 `web.txt`。

本机默认访问示例为 `http://127.0.0.1:8000`。配置、MySQL、数据位置和停止/重启见 [Linux 部署说明](../docs/部署说明-v1.0.md)。

worker 直接调用当前科学工具，不比较代码与转换器的历史摘要；原始数据摘要和包完整性检查保留。`--once` 会执行真实任务，不能作为健康探针；只读检查使用 `bash scripts/run-linux.sh check`。
