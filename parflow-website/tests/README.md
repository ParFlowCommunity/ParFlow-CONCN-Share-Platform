# 回归测试

在项目根目录激活 `concnshare` 后运行。临时文件留在项目目录内，后端测试限定 60 秒：

```bash
conda activate concnshare
mkdir -p .local/test-tmp
TMPDIR="$PWD/.local/test-tmp" timeout 60s python -B -m unittest discover -s tests -v
node --test frontend/tests/*.test.js
```

`backend/` 覆盖 MySQL 业务、权限、任务、边界、包内容和发布完整性；`clipping/` 覆盖科学参数、网格和裁切编排；前端测试位于 `frontend/tests/`。

后端集成测试清空并重建专用 **concn_datahub_test** 中的测试记录，不使用正式 concn_datahub 数据库。连接参数从 backend/.env 读取，测试覆盖数据库名。不要将真实数据放进测试库。

自动化单元/集成测试中的合成数据不能替代真实科学输出验证。真实裁切和浏览器验收方法见 [测试与验证](../docs/测试与验证.md)。
