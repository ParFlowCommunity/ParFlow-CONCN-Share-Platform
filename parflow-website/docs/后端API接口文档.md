# ParFlow CONCN Share Platform 后端 API 接口文档

## 1. 通用约定

### 1.1 地址、格式与认证

本地示例基地址：`http://127.0.0.1:8000`。生产环境使用实际网站来源，以下路径均包含 `/api`。普通请求/响应为 UTF-8 JSON；边界接口返回 GeoJSON，文件接口返回 ZIP 字节流。

所有 POST、PUT 等写请求必须携带 `X-DataHub: 1`；发送 JSON 时携带 `Content-Type: application/json`。Origin 若存在，必须与配置 PUBLIC_URL 来源或当前请求网站来源一致。缺少防跨站头或来源不匹配返回 403 CSRF_REJECTED。请求体最大 1 MiB。

登录成功设置 `concn_session` Cookie：HttpOnly、SameSite=Lax、Path=/api、有效期 7 天；Secure 取决于部署配置。使用 Cookie 认证，没有 Bearer Token 登录接口。前端 fetch 应设置 `credentials: 'same-origin'`；独立客户端必须保存并回传 Cookie。跨域接入不在当前支持范围。

权限标记：**公开**不要求登录；**用户**要求 active 登录用户；**下载用户**额外检查配置启用时的邮箱验证；**管理员**要求 role=admin。停用、退出或会话到期后返回 401 LOGIN_REQUIRED。

服务端时间返回 ISO 8601 UTC 字符串，带 Z；日期字段为 YYYY-MM-DD；字节数为整数，数据库 Decimal 序列化为数字，二进制哈希在 JSON 中为十六进制字符串。业务 ID 应视为不透明字符串，流域编号始终是 14 位数字字符串，不可转整数。

### 1.2 幂等

POST /api/jobs 和 POST /api/applications 必须携带 `Idempotency-Key`，长度 8–64 个 ASCII 字符。同一账号同一键同一请求可重试；相同键不同请求返回 409 IDEMPOTENCY_CONFLICT。缺失或格式错误返回 400 IDEMPOTENCY_REQUIRED。一个新的逻辑操作使用新键。

任务还可能复用同账号、流域、版本、授权方式、包修订及用途信息一致的活动任务或有效结果。该规则不等价于记录每次按钮点击。

### 1.3 分页、错误和限流

分页接口：page 默认 1，范围归一至 1–100000；page_size 默认 20，范围归一至 1–100。不能解析为整数返回 INVALID_INPUT。列表通常返回 `{ "items": [], "total": 0 }`，但审计等接口没有 total，详见对应章节。

错误响应示例：

```json
{"error":"INVALID_FIELD","params":{"field":"download_purpose"}}
```

成功响应没有统一外层 data 包装。一般更新返回 `{ "ok": true }`。文件 Range 416 返回空体及 Content-Range，不能假设所有错误都是 JSON。

应用内 POST 限流按进程和来源 IP 计算：认证类 20 次/60 秒，其他写入类 60 次/60 秒；超限 429 RATE_LIMITED。这不是全局分布式限流，反向代理来源转发仍需部署核验。登录连续失败 5 次锁定约 15 分钟。

## 2. 账号与会话

| 方法与路径 | 权限 | 请求 JSON | 成功返回 |
|---|---|---|---|
| POST /api/register | 公开 | username 4–64；email 合法邮箱；password 8–128 且含字母和数字 | 201 `{ok:true}`，不创建会话 |
| POST /api/login | 公开 | email、password | 200 User 对象；设置登录 Cookie |
| POST /api/logout | 公开 | 可传 `{}` | 200 `{ok:true}`；撤销当前会话、删除 Cookie |
| GET /api/me | 用户 | 无 | 200 User + slots + remaining_slots |
| PUT /api/me/username | 用户 | username 4–64 | 200 `{ok:true}` |
| PUT /api/me/locale | 用户 | locale：zh-CN 或 en | 200 `{ok:true}` |
| PUT /api/me/password | 用户 | old_password、new_password（同密码规则） | 200 `{ok:true}`；撤销全部登录会话和未消费邮箱操作，清 Cookie |
| POST /api/me/verify-email | 用户 | `{}` | 202 `{ok:true}`；向当前邮箱发送操作链接 |
| POST /api/me/change-email | 用户 | email 新邮箱、password 当前密码 | 202 `{ok:true}`；发送确认链接，尚未立即修改邮箱 |
| POST /api/forgot-password | 公开 | email | 202 `{ok:true}`；不暴露账号是否存在 |
| POST /api/email-action | 公开 | token 20–128；重置密码时另传 new_password | 200 `{ok:true}`；消费令牌并撤销该账号会话 |

User 字段：id、username、email、role（user/admin）、status（active/disabled）、preferred_locale、email_verified_at（可空）、created_at。不返回密码哈希。

slots 为 `{slot_no,basin_code,state,name_zh,name_en,pfbas_level}` 数组，state 包含 reserved/active。remaining_slots=2−当前名额记录数，预留名额也计入。此处 pfbas_level 为 2/4/6/8/10/12/14。

邮箱发送需要 SMTP_HOST、SMTP_FROM 等可用配置，失败可返回 EMAIL_SERVICE_UNAVAILABLE；找回密码仅对已验证且启用账号发信，但对其他邮箱同样返回通用成功响应。操作令牌单次使用、不可过期或撤销。

## 3. 配置、行政区、流域和数据目录

| 方法与路径 | 权限 | 查询参数 | 成功结果 |
|---|---|---|---|
| GET /api/health | 公开 | 无 | `{status:"ok",database:"mysql"}`；含数据库连通检查，不代表工作进程或数据完备 |
| GET /api/config | 公开 | 无 | 当前规则、级别和平台计数，见下文 |
| GET /api/regions | 公开 | province 可选，6 位行政区编码 | `{items:[Region]}`；不传查省份，传入查其城市 |
| GET /api/watersheds | 公开 | q 可选但出现时必须为完整14位编号；level 可选1–7；parent 可选；分页 | `{items:[Watershed],total}` |
| GET /api/watersheds/<code> | 公开 | 无 | Watershed + versions；不存在404 |
| GET /api/watersheds/<code>/download-access | 下载用户 | version 必填数字版本ID | `{direct:boolean,application_id:string或null}` |
| GET /api/datasets | 公开 | 无 | `{items:[Dataset]}`，仅已发布版本 |
| GET /api/boundaries | 公开 | basin_code 或 level，见下文 | GeoJSON 或缓存层响应 |

Config：current_policy_id、small_min_hierarchy_level、result_retention_hours、approval_validity_hours、maintenance_mode、levels、basin_count、release_count、small_basin_limit（2）、package_mode（full）、email_available、require_verified_email。email_available 仅反映 SMTP_HOST 是否配置，不是完整发信测试。

Region：code、name_zh、kind（province/city）、parent_code、center_lng、center_lat、view_bounds。view_bounds 为解码后的 JSON；字段意义用于前端定位。

Watershed 返回流域表记录，包括 basin_code、pfbas_level、名称、父级、面积、bbox_wgs84、状态等；准确字段定义见数据库逐字段说明。详情 versions 包括 id、version_code、title_zh/en、status、estimated_zip_bytes、unavailable_reason_zh/en。

Dataset：id、version_code、title_zh/en、description_zh/en、boundary_version、clip_version、citation、terms_version、license_text_zh/en、published_at，及 files 数组。files 每项为 item_code、title_zh/en、units、output_name_template。清单中的 README.txt、SHA256SUMS.txt 不会进入 ZIP；CITATION.txt 由平台按 citation 字段生成后随包发布，因此不能以本接口 files 数量推断实际 ZIP 文件数。

Application：id、basin_code、dataset_version_id、version_code、applicant_name、affiliation、contact_email、usage_type（project/thesis）、usage_title、usage_owner、purpose（申请理由）、project_url、status、review_comment、submitted_at、reviewed_at、authorization_expires_at、revoked_at。提交时 usage_type 必填；论文用途的 usage_owner 只接受 master/doctor/journal，项目用途为自由文本。已停用的 large_basin_reason 不再返回。

**级别区别必须注意：** watersheds 的查询 level 使用显示级别 1–7；boundaries 的查询 level 使用 PFBAS 原始值 2/4/6/8/10/12/14；流域和任务响应中的 pfbas_level 同样是原始值，网页除以 2。ZIP metadata.json 的 pfbas_level 已转为 1–7。

boundaries 同时传 basin_code 和 level 时，以 basin_code 查询单流域；无 basin_code 且有 level 时返回该级别图层。全级图层支持 gzip、ETag 和条件请求缓存，可能返回 304；单流域不存在返回404。

download-access 仅提供提示；提交任务、领取下载会话、传输文件时会重新检查，不能将其作为永久授权。

## 4. 申请及审核

### 4.1 提交申请

`POST /api/applications`，下载用户；要求幂等键。仅接受以下字段，多余字段或 terms_accepted 不为 true 返回 INVALID_INPUT。

| 字段 | 类型 | 约束 |
|---|---|---|
| basin_code | string | 14字符，必须对应可用流域；调用方传14位数字 |
| dataset_version_id | integer | 正整数、已发布且该流域可用 |
| applicant_name | string | 1–100，去首尾空白 |
| affiliation | string | 1–255 |
| usage_type | string | 必填，只接受 project 或 thesis |
| usage_title | string | 1–255；项目用途为项目名称，论文用途为论文题目 |
| usage_owner | string | 1–255；项目用途为项目负责人自由文本，论文用途只接受 master/doctor/journal |
| purpose | string | 10–5000，申请理由 |
| project_url | string | 可选默认空，最多2000，非空以 http:// 或 https:// 开头 |
| terms_accepted | boolean | 必须true |

邮箱从当前用户读取，不接收 contact_email。新建返回201 `{id:"…"}`；幂等重试返回200 `{id:"…",reused:true}`。

### 4.2 列表及状态操作

| 方法与路径 | 权限 | 参数 | 成功返回 |
|---|---|---|---|
| GET /api/applications | 用户 | 分页 | 自己的 `{items:[Application],total}` |
| POST /api/applications/<app_id>/withdraw | 用户 | `{}` | 200 `{ok:true}`；只可撤回自己的 pending |
| GET /api/admin/applications | 管理员 | 分页；status 默认pending，空字符串表示全部 | `{items:[Application],total}` |
| POST /api/admin/applications/<app_id>/decision | 管理员 | action：approve/reject/revoke；comment 1–5000 | 200 `{ok:true}` |

Application：id、user_id、basin_code、dataset_version_id、version_code、applicant_name、affiliation、contact_email、usage_type、usage_title、usage_owner、purpose、project_url、status、review_comment、submitted_at、reviewed_at、authorization_expires_at、revoked_at。

approve/reject 只可对 pending 执行；revoke 只可对 approved 执行。批准时按当前配置计算有效期；撤销时撤销下载会话并取消/请求取消相应活动任务。错误状态409 INVALID_STATE，跨账号用户查询/操作记录404 NOT_FOUND。

## 5. 裁切任务

### 5.1 创建任务

`POST /api/jobs`，下载用户；要求幂等键。

| 字段 | 类型 | 约束 |
|---|---|---|
| basin_code | string | 必填，严格14位ASCII数字 |
| dataset_version_id | integer | 必填正整数 |
| application_id | string/null | 可选，32位小写十六进制申请ID；传入必须属于本人、同流域同版本且授权有效 |
| terms_accepted | boolean | 必须true |
| package_mode | string | 可省略，唯一允许full |
| download_affiliation | string | 地图新表单必填，1–100 |
| download_purpose | string | 地图新表单必填，1–200 |

后两个字段为兼容旧调用允许同时省略；传任一个则两个均须合法非空。保存到 request_snapshot，当前 GET 任务及管理员列表不返回这两个字段。用途不同可能创建新任务而不复用旧任务。除表中字段外的字段返回 FULL_PACKAGE_ONLY。

新任务202 `{id:"…",reused:false}`，复用200 `{id:"…",reused:true}`。当无资格、数据不可用、维护、免费额度满或队列限制时拒绝创建，不返回ZIP内容。

### 5.2 查询和取消

| 方法与路径 | 权限 | 参数 | 返回 |
|---|---|---|---|
| GET /api/jobs | 用户 | 分页 | 自己的 `{items:[Job],total}` |
| GET /api/jobs/<job_id> | 用户 | 无 | 本人的 Job；不存在或非本人404 |
| POST /api/jobs/<job_id>/cancel | 用户 | `{}` | `{ok:true}`；取消自己的活动任务 |
| GET /api/admin/jobs | 管理员 | 分页 | 全部 `{items:[Job],total}` |
| POST /api/admin/jobs/<job_id>/cancel | 管理员 | `{}` | `{ok:true}`；取消活动任务 |

Job：id、basin_code、pfbas_level、dataset_version_id、version_code、application_id、access_mode、package_mode、status、stage_code、error_code、created_at、updated_at、finished_at、byte_size、expires_at、archive_state。无归档时相关字段可空。

access_mode：small 或 approved_large（含获批小流域）。任务状态见需求文档。queued 取消立即成为 cancelled；已运行任务变为 cancel_requested，由工作进程实际终止。取消已终结任务返回409。

轮询建议沿用现有前端约3秒，仅活动任务持续轮询，关闭页面停止轮询，避免整体页面刷新。服务端未提供实时WebSocket或进度百分比接口。

## 6. ZIP 下载会话及断点续传

### 6.1 领取会话

`POST /api/jobs/<job_id>/download-session`，下载用户，JSON `{}`。

需要任务属于本人且 succeeded、文件仍可用、数据版本仍共享、相关授权仍有效。成功200：

```json
{"url":"/api/files/0123456789abcdef0123456789abcdef","expires_at":"2030-01-01T00:00:00Z"}
```

同时设置 HttpOnly Cookie `download_<session_id>`，Path 为返回文件路径。有效期最多1小时，并受归档及申请有效期上限约束。URL不含秘密令牌；不能仅复制URL到别人的浏览器下载。签发会话时小流域预留资格成为 active。

### 6.2 获取文件

`GET /api/files/<session_id>` 或 `HEAD /api/files/<session_id>`；下载用户，要求登录Cookie及匹配下载Cookie。

完整GET返回200 application/zip；HEAD无正文但提供文件头。支持单段 Range：`bytes=0-1023`、`bytes=1024-`、`bytes=-1024`。有效范围返回206及Content-Range；无效或多段请求返回416及`Content-Range: bytes */文件大小`。If-Range匹配ETag才使用范围，否则返回完整内容。

响应头：Content-Length、Accept-Ranges: bytes、ETag、Cache-Control: private, no-store、Content-Disposition。文件名格式为 `ParFlow_CONCN_Share_Platform_编号_YYYYMMDD.zip`，北京时间日期取本次请求。归档或会话过期返回410 FILE_UNAVAILABLE。

传输开始与传输期间会检查授权/账号等状态；管理员撤销可能中断传输。已收到部分内容后不能期待一个完整JSON错误响应，客户端应按连接中断处理。

### 6.3 浏览器调用示例

以下变量应来自当前界面，示例不含真实凭据。先注册（如需要）再独立登录，不能把注册成功当作登录成功。

```javascript
const call = async (path, method = 'GET', body, key) => {
  const response = await fetch('/api' + path, {
    method, credentials: 'same-origin',
    headers: { 'Content-Type': 'application/json', 'X-DataHub': '1',
      ...(key ? { 'Idempotency-Key': key } : {}) },
    ...(body === undefined ? {} : { body: JSON.stringify(body) })
  });
  const data = await response.json();
  if (!response.ok) throw data;
  return data;
};
await call('/login', 'POST', { email: loginEmail, password: loginPassword });
const access = await call(`/watersheds/${basinCode}/download-access?version=${versionId}`);
// 没有直接资格和有效申请时，应走申请流程，不绕过资格校验。
const task = await call('/jobs', 'POST', {
  basin_code: basinCode, dataset_version_id: versionId,
  terms_accepted: true, // 仅在用户明确勾选同意后提交
  download_affiliation: affiliation, download_purpose: purpose,
  ...(access.application_id ? { application_id: access.application_id } : {})
}, requestKey); // 为当前逻辑操作生成并在重试时保留的8–64字符ASCII键
// 轮询 GET /jobs/<id>，直到 succeeded 后：
const session = await call(`/jobs/${task.id}/download-session`, 'POST', {});
window.location.assign(session.url);
```

内网HTTP环境不能假定 crypto.randomUUID 可用，应使用项目已有 requestKey 工具。

## 7. 管理配置、账号及数据版本

| 方法与路径 | 权限 | 参数 | 成功返回 |
|---|---|---|---|
| GET /api/admin/overview | 管理员 | 无 | users、pending、queued、failed、jobs状态计数、last_worker_heartbeat、transfer_bytes、free_disk_bytes |
| PUT /api/admin/config | 管理员 | 见下表 | `{ok:true}`，创建新策略记录并更新当前指针 |
| GET /api/admin/users | 管理员 | q可选，trim后最多254；分页 | `{items:[User],total}` |
| PUT /api/admin/users/<user_id>/status | 管理员 | status：active/disabled | `{ok:true}`；不可修改本人或管理员状态 |
| GET /api/admin/datasets | 管理员 | 无 | `{items:[{id,version_code,title_zh,title_en,status,published_at}]}` |
| POST /api/admin/datasets/<version>/withdraw | 管理员 | `{}` | `{ok:true}`；仅published可撤回，并撤销相关下载会话 |
| GET /api/admin/audit | 管理员 | 分页 | `{items:[Audit]}`，无total |

用户搜索为用户名或邮箱的字面子串匹配，%和_不是通配符，大小写由数据库排序规则决定（当前不区分大小写）。停用普通账号会撤销其登录与下载会话。无网页创建管理员、删除账号或提升角色接口。

配置JSON：

| 字段 | 约束 |
|---|---|
| small_min_hierarchy_level | 必填整数1–7 |
| reason | 必填3–1000字 |
| result_retention_hours | 整数1–720，省略用72 |
| approval_validity_hours | 整数1–8760，省略用168 |
| maintenance_mode | boolean，省略false |

调用更新时应提交完整配置，省略字段会应用默认值，并非保留原值。维护模式阻止新申请和新任务，不等于关闭全部网站接口。

Audit 为审计表记录，含操作者、action_code、object_type、object_id、details（已解码JSON）及时间；不同动作 details 字段不同。

## 8. 双语内容

| 方法与路径 | 权限 | 参数 | 返回 |
|---|---|---|---|
| GET /api/content | 公开 | kind默认help | `{items:[Content]}`，仅published，最多50条 |
| GET /api/admin/content | 管理员 | 无 | `{items:[内容表记录]}`，最近100条 |
| POST /api/admin/content | 管理员 | 完整内容JSON | 201 `{ok:true}` |
| PUT /api/admin/content/<content_id> | 管理员 | 完整内容JSON | 200 `{ok:true}`；不存在404 |

内容JSON字段：slug（1–128）、title_zh/title_en（各1–200）、body_zh/body_en（各1–100000）、kind（help/notice/home/terms/privacy）、status（draft/published，省略draft）。当前为完整更新，不是PATCH。公开Content返回slug、双语标题/正文、published_at，不返回内部编辑人信息。

## 9. 站内通知

| 方法与路径 | 权限 | 参数 | 返回 |
|---|---|---|---|
| GET /api/notifications | 用户 | 分页 | `{items:[Notification],total,unread}` |
| POST /api/notifications/read | 用户 | `{}` | `{ok:true}`，当前用户所有现有通知标为已读 |

Notification：event_key、kind（approve/reject/revoke/ready）、basin_code、comment、created_at、link（/applications或/downloads）、read_at（未读为空）。只查询本人事件。没有单条标已读、删除通知或任意发送通知接口；事件由审核记录和结果归档生成。

## 10. 常见错误处理

| HTTP | error | 调用方处理 |
|---|---|---|
| 400 | INVALID_INPUT / INVALID_FIELD / INVALID_EMAIL / INVALID_PASSWORD | 检查字段及params.field |
| 400 | FULL_PACKAGE_ONLY | 删除不支持字段，使用完整包 |
| 400 | TERMS_REQUIRED | 等待用户明确同意条款 |
| 400 | IDEMPOTENCY_REQUIRED / INVALID_TOKEN | 修正请求键或重新申请有效邮箱链接 |
| 401 | LOGIN_REQUIRED / INVALID_CREDENTIALS | 登录或检查密码 |
| 403 | FORBIDDEN / CSRF_REJECTED | 检查权限、请求头及来源 |
| 403 | EMAIL_VERIFICATION_REQUIRED | 完成邮箱验证 |
| 403 | APPROVAL_REQUIRED / SMALL_BASIN_QUOTA_EXCEEDED | 提交申请或使用有效授权 |
| 404 | NOT_FOUND | 记录不存在或不属于当前用户 |
| 409 | ACCOUNT_EXISTS / ACCOUNT_OR_RECORD_EXISTS | 更换冲突账号信息或检查唯一约束 |
| 409 | IDEMPOTENCY_CONFLICT / INVALID_STATE / DATA_UNAVAILABLE | 检查请求键、刷新状态、检查发布与流域可用性 |
| 410 | FILE_UNAVAILABLE | 重新领取会话、生成结果或申请授权 |
| 429 | LOGIN_LOCKED / RATE_LIMITED / ACTIVE_JOB_LIMIT / QUEUE_FULL | 等待或减少并发，不紧密循环重试 |
| 503 | MAINTENANCE / EMAIL_SERVICE_UNAVAILABLE / SERVICE_UNAVAILABLE | 检查维护状态及依赖服务 |
| 500 | INTERNAL_ERROR | 保存params.trace供维护人员定位，不向用户展示内部日志 |

以上是常见业务错误，不保证囊括所有执行期任务失败码。裁切失败原因通过Job.error_code返回；HTTP请求成功不代表异步任务必然成功。

## 11. 兼容性与维护边界

- 目前没有API版本路径、自动生成OpenAPI或对第三方SDK的兼容性承诺。增加/修改接口需同步更新本文和相关测试。
- 历史PFBAS字段与显示级别转换、approved_large命名、历史数据文件清单属于兼容现状，不应直接按英文名称推断业务限制。
- download_affiliation/download_purpose 已保存但不在公开任务投影中；管理员读取用途和所有入口统一采集尚待完善。
- 没有在线发布源数据、自定义流域裁切、变量子集下载、任意文件路径下载、角色提升API。
- 本文不包含密码、令牌、真实邮箱操作链接或数据库连接字符串。部署地址由环境确定。
