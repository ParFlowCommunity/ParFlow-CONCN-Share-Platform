# 网页前端

Vue 与 Element Plus 页面，包含顶部导航、登录表单和地图信息分栏。默认中文，支持英文切换。默认地图为地形，支持手动切换标准；配置密钥时使用天地图，SDK 失败明确报错并提供重试。见 [功能说明](../docs/需求规格说明书.md)。

地图密钥配置在本目录 `.env.local` 的 `VITE_TIANDITU_KEY` 中。修改后需重新构建。只有未配置密钥时才使用既有 Leaflet 模式；配置密钥后不因超时或失败自动切换。第三方瓦片仍由浏览器直接请求，其访问状态见测试报告。

在本目录执行：

```bash
npm ci
npm run dev
```

开发地址为 `http://127.0.0.1:5173`，接口代理由 `VITE_API_TARGET` 配置；开发时可设为 `http://127.0.0.1:8000`。需同时启动 [网站后端](../backend/README.md)。如需修改开发接口地址，可使用 `VITE_API_TARGET` 环境变量。

```bash
npm run build
```

构建产物为本目录下的 `dist/`，后端已按新目录读取它。`npm run preview` 只预览静态构建产物，未配置 API 代理；需要完整登录、申请和下载功能时，请使用开发服务或由后端提供构建页面。

## 代码分工

- `src/api`：请求和下载操作。
- `src/stores`：用户、平台配置、初始化与消息提示。
- `src/locales`：语言选择、错误和状态文案；页面自身的成对文案暂保留在页面内。
- `src/views`：已有用户和管理员页面。
- `src/components`：共享地图。
- `src/router`：页面导航与访问提示；实际权限由后端决定。
- `src/styles`、`src/utils`：样式和格式化工具。

使用 Prettier 整理前端格式的示例：

```bash
npm exec --yes --package=prettier@3.6.2 -- prettier --write "src/**/*.{js,vue,css}" vite.config.js index.html
```

地图默认显示地形。配置天地图密钥时，加载过程不再因 2.5 秒超时切换到备用地图；失败显示错误和重试按钮。未配置密钥时保留既有 Leaflet 模式。
