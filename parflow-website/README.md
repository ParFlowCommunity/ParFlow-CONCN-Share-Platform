# ParFlow CONCN Share Platform

[快速开始](#快速开始) · [科学裁切](docs/科学裁切工具说明.md) · [部署指南](docs/部署说明-v1.0.md) · [文档目录](docs/README.md)

**本平台用于共享中国大陆尺度ParFlow-CONCN模型。**

ParFlow-CONCN 1.0模型是约1公里水平分辨率，纵深492m的地表水-地下水集成水文模型。1.1版本正在建设中，可与CLM或CoLM耦合运行，用于探究地下水与陆面过程的双向交互作用。

用户可通过本平台裁剪用于目标流域ParFlow模拟的所有基础输入文件，如：流域mask文件、初始压力场分布、水平x、y方向坡度文件、manning粗糙系数、含水介质水力参数、基岩深度、用于不规则流域模拟的solid文件等。

**若使用本工具及生成文件开展研究，请引用：**

Yang C, Jia ZT, Xu WJ, Wei ZW, Zhang XL, Zou YG, Mcdonnell JJ, Condon LE, Dai YJ, Maxwell RM, 2025. CONCN: a high-resolution, integrated surface water-groundwater ParFlow modeling platform of continental China. Hydrology and Earth System Sciences, 29(9): 2201-2218.

## CONCN 流域分级

CONCN流域分级使用 14 位固定编码体系来表示，每升一级增加 2 位有效数字，剩余位数以 0 填充。

需注意的是，当前 CONCN 流域分级边界与实际自然流域边界存在一定差异（如长江流域、淮河流域）。这是因为分级过程中使用了 HydroBASINS 和 MERIT Basins 等外部流域数据进行辅助划分，而这些数据集在流域边界刻画和河网汇流关系表达上与实际情况存在差异。

![PFBAS2 basins](Fig/pfbas2_basins.png)

| 级别 | 有效位数 | 流域数量 | 说明 |
|------|----------|----------|------|
| PFBAS2 | 2 位 | 10 个 | 一级流域 |
| PFBAS4 | 4 位 | 127 个 | 二级子流域 |
| PFBAS6 | 6 位 | 367 个 | 三级子流域 |
| PFBAS8 | 8 位 | 1,215 个 | 四级子流域 |
| PFBAS10 | 10 位 | 3,988 个 | 五级子流域 |
| PFBAS12 | 12 位 | 12,118 个 | 六级子流域 |
| PFBAS14 | 14 位 | 53,040 个 | 七级子流域  |

| 级别 | 有效位数 | 编码示例 | 说明 |
|------|---------|---------|------|
| PFBAS2 | 2位 | `01000000000000` | 第1个一级流域 |
| PFBAS4 | 4位 | `01020000000000` | 01流域的第2个子流域 |
| PFBAS6 | 6位 | `01020300000000` | 0102流域的第3个子流域 |
| PFBAS8 | 8位 | `01020301000000` | 010203流域的第1个子流域 |
| PFBAS10 | 10位 | `01020301040000` | 01020301流域的第4个子流域 |
| PFBAS12 | 12位 | `01020301040500` | 0102030104流域的第5个子流域 |
| PFBAS14 | 14位 | `01020301040506` | 010203010405流域的第6个子流域 |

## 平台功能

- **流域浏览**：七级流域地图、14 位编码精确搜索、省市定位、流域高亮和属性查看。
- **地图显示**：默认地形底图，可切换标准地图，支持中英文界面。
- **科学裁切**：生成流域掩膜，裁切五类 PFB，调用 pfmask-to-pfsol 生成计算域文件。
- **异步下载**：独立 worker 处理任务，提供状态查询、取消、授权下载和过期管理。
- **账号与审核**：注册登录、下载用途填写、申请审批、通知、用户及内容管理。

默认共享规则允许每个账号免审核获取两个不同的小流域编码；大流域和额外小流域通过申请审核获取。阈值及规则以部署实例配置为准，详见 [网站功能使用说明](docs/网站功能使用说明.md)。

## 快速开始

源码仓库不包含科学源数据、业务数据库、账号凭据或地图密钥。运行科学裁切需另行准备 PFB、流域边界、模板栅格和 Linux pfmask-to-pfsol；部署完整网站还需 MySQL、Node.js 和前端配置。

### 准备 Python 环境

在项目根目录执行：

```bash
conda env create -f environment.yaml
conda activate concnshare
```

environment.yaml 创建 Python 3.12 环境并安装科学依赖和 concnshare 包。若只使用独立裁切工具，无需启动 MySQL 或网页服务。

### 使用独立裁切工具

先将以下示例路径替换为实际文件位置：

```bash
export CONCN_SHP_DIR=/path/to/data/PFBAS/shp
export CONCN_TIF_DIR=/path/to/data/PFBAS/geotiff
export CONCN_INPUT_PFB_DIR=/path/to/data/inputs
export PARFLOW_PFMASK_CMD=/path/to/parflow/bin/pfmask-to-pfsol

python -m concnshare.run_two 03030109050100 --output-dir ./outputs
```

编号需存在于源边界数据中。结果写入 outputs/流域编号/；独立 CLI 生成科学文件，不创建网站任务或 ZIP。已有同名输出目录时默认拒绝覆盖。参数、掩膜处理和元信息说明见 [科学裁切工具说明](docs/科学裁切工具说明.md)。集群环境中的任务应按其调度规范运行。

### 部署完整网站

网站由 Vue 前端、Flask/Waitress 后端、MySQL 与独立 worker 组成。

1. 安装网站及 worker 依赖：`python -m pip install -r backend/requirements/worker.txt`。
2. 准备 MySQL 和符合 [frontend/package.json](frontend/package.json) 要求的 Node.js。
3. 按 [部署指南](docs/部署说明-v1.0.md) 初始化全新业务库并配置 backend/.env；继承已有站点则按 [交接指南](docs/数据库继承与部署交接.md) 恢复数据库与文件，不重复 bootstrap。
4. 配置科学路径和 frontend/.env.local，完成流域目录与数据版本发布。
5. 安装前端依赖并构建网页：

```bash
npm --prefix frontend ci
bash scripts/run-linux.sh build
```

在已激活 concnshare 的两个终端，从项目根目录分别启动网站和 worker：

```bash
# 终端一：网站与 API
bash scripts/run-linux.sh web
```

```bash
# 终端二：裁切任务处理
bash scripts/run-linux.sh worker
```

网站默认本机入口为 http://127.0.0.1:8000，实际监听与访问地址由配置决定。使用 `bash scripts/run-linux.sh check` 检查健康状态。后台运行、停止、HTTPS、邮件和网络访问见 [部署指南](docs/部署说明-v1.0.md)。



## 项目结构

| 路径 | 职责 |
| --- | --- |
| `concnshare/` | 独立科学裁切工具与参数配置 |
| `frontend/` | Vue 网页、地图、账号与管理界面 |
| `backend/` | Flask API、权限、数据库访问和任务 worker |
| `database/` | 数据库结构迁移及默认数据脚本 |
| `scripts/` | Linux 启动、健康检查和目录导入 |
| `tests/` | Python 后端与科学工具测试；前端测试位于 frontend/tests |
| `docs/` | 部署、使用、接口、数据库及维护说明 |
| `deploy/` | 部署文档入口 |
| `Fig/` | 科学说明图片 |

逐文件说明见 [项目结构与文件说明](docs/项目结构与文件说明.md)。

## 文档

| 目标 | 文档 |
| --- | --- |
| 使用网页查询和下载 | [网站功能使用说明](docs/网站功能使用说明.md) |
| 运行科学裁切 | [科学裁切工具说明](docs/科学裁切工具说明.md) |
| 部署或交接网站 | [部署说明](docs/部署说明-v1.0.md)、[数据库继承与部署交接](docs/数据库继承与部署交接.md) |
| 理解业务和接口 | [需求规格](docs/需求规格说明书.md)、[后端 API](docs/后端API接口文档.md)、[数据库说明](docs/数据库说明.md) |
| 测试及维护 | [测试与验证](docs/测试与验证.md)、[维护与优化](docs/维护与优化文档-v1.0.md) |
| 准备源码发布 | [源码发布说明](docs/源码发布说明.md) |

更多说明见 [文档目录](docs/README.md)。

## 问题反馈与贡献

欢迎通过仓库 Issues 反馈问题，通过 Pull Request 提交修复或文档改进。

## 来源

项目仓库：[ParFlowCommunity/ParFlow-CONCN-Share-Platform](https://github.com/ParFlowCommunity/ParFlow-CONCN-Share-Platform)。底层模型与工具参见 [ParFlow](https://github.com/parflow/parflow)。
