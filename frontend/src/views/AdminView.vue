<script setup>
import "../styles/management.css";
import {useRoute} from "vue-router";
import { ref, reactive, onMounted, watch } from "vue";
import { tr, text } from "../locales/index";
import { state } from "../stores/state";
import { api } from "../api/client";
import { attempt, notify } from "../stores/notifications";
import { refreshConfig } from "../stores/session";
import { statusText } from "../locales/statuses";
import { dateText, sizeText } from "../utils/format";
const route = useRoute();
const tab = ref(["reviews","users","jobs","audit","content","datasets","config"].includes(route.query.tab)?route.query.tab:"reviews"),
  overview = ref({}),
  items = ref([]),
  filter = ref("pending"),
  page = ref(1),
  total = ref(0),
  busy = ref(false),
  comments = reactive({}),
  cfg = reactive({
    small_min_hierarchy_level: 5,
    result_retention_hours: 72,
    approval_validity_hours: 168,
    maintenance_mode: false,
    reason: "",
  }),
  confirm = ref(false);
const editingContentId = ref(null);
const content = reactive({
  slug: "",
  kind: "notice",
  title_zh: "",
  title_en: "",
  body_zh: "",
  body_en: "",
  status: "published",
});
const userQuery=ref('');
const appliedUserQuery=ref('');
let loadSerial=0;
async function searchUsers(){appliedUserQuery.value=userQuery.value.trim();page.value=1;await load();}
async function load() {
  const ticket=++loadSerial;
  await attempt(async () => {
    overview.value = await api("/admin/overview");
    if(ticket!==loadSerial)return;
    const path = {
      reviews: "/admin/applications?status=" + filter.value,
      users: "/admin/users?q="+encodeURIComponent(appliedUserQuery.value),
      jobs: "/admin/jobs?",
      audit: "/admin/audit?",
      content: "/admin/content?",
      datasets: "/admin/datasets?",
    }[tab.value];
    if (path) {
      const r = await api(path + `&page=${page.value}`);
      if(ticket!==loadSerial)return;
      items.value = r.items;
      total.value = r.total || 0;
    } else {
      await refreshConfig();
      Object.assign(cfg, state.config, {
        maintenance_mode: !!state.config.maintenance_mode,
        reason: "",
      });
      confirm.value = false;
    }
  });
}
watch(()=>route.query.tab, value=>{if(["reviews","users","jobs","audit","content","datasets","config"].includes(value))switchTab(value);});
async function switchTab(value) {
  tab.value = value;
  page.value = 1;
  items.value = [];
  await load();
}
async function decision(a, action) {
  busy.value = true;
  await attempt(async () => {
    await api(`/admin/applications/${a.id}/decision`, {
      method: "POST",
      body: { action, comment: comments[a.id] || "" },
    });
    notify(tr("审核记录已保存。", "Review saved."));
    await load();
  });
  busy.value = false;
}
async function saveConfig() {
  busy.value = true;
  await attempt(async () => {
    await api("/admin/config", { method: "PUT", body: cfg });
    notify(
      tr(
        "新规则已发布，已取得的小流域资格保留。",
        "New policy published. Acquired small-basin access is retained.",
      ),
    );
    await load();
  });
  busy.value = false;
}
async function userStatus(u) {
  await attempt(async () => {
    await api(`/admin/users/${u.id}/status`, {
      method: "PUT",
      body: { status: u.status === "active" ? "disabled" : "active" },
    });
    await load();
  });
}
async function cancel(j) {
  await attempt(async () => {
    await api(`/admin/jobs/${j.id}/cancel`, { method: "POST", body: {} });
    await load();
  });
}
async function publishContent() {
  await attempt(async () => {
    await api(editingContentId.value ? `/admin/content/${editingContentId.value}` : "/admin/content", { method: editingContentId.value ? "PUT" : "POST", body: content });
    editingContentId.value = null;
    Object.assign(content, {
      slug: "",
      title_zh: "",
      title_en: "",
      body_zh: "",
      body_en: "",
    });
    notify(tr("双语内容已保存。", "Bilingual content saved."));
    await load();
  });
}
function editContent(item) {
  editingContentId.value = item.id;
  for (const key of Object.keys(content)) content[key] = item[key];
  window.scrollTo({ top: 0, behavior: 'smooth' });
}
function cancelContentEdit() {
  editingContentId.value = null;
  Object.assign(content, { slug: '', kind: 'help', title_zh: '', title_en: '', body_zh: '', body_en: '', status: 'published' });
}
async function withdraw(v) {
  await attempt(async () => {
    await api(`/admin/datasets/${v.id}/withdraw`, { method: "POST", body: {} });
    await load();
  });
}
onMounted(load);
</script>
<template>
<div class="management-container">
  <div class="page-heading heading-row">
    <div>
      <h1>{{ tr("管理工作台", "Administration") }}</h1>
      <p>
        {{
          tr(
            "审核研究申请，管理共享规则与平台运行。",
            "Review applications, manage access policies and monitor the platform.",
          )
        }}
      </p>
    </div>
    <button class="button" @click="load">↻ {{ tr("刷新", "Refresh") }}</button>
  </div>
  <div class="stats-grid">
    <div class="stat">
      <span>{{ tr("注册账号", "Accounts") }}</span
      ><strong>{{ overview.users ?? "—" }}</strong>
    </div>
    <div class="stat">
      <span>{{ tr("待审核申请", "Pending applications") }}</span
      ><strong>{{ overview.pending ?? "—" }}</strong>
    </div>
    <div class="stat">
      <span>{{ tr("排队任务", "Queued jobs") }}</span
      ><strong>{{ overview.queued ?? "—" }}</strong>
    </div>
    <div class="stat">
      <span>{{ tr("可用存储", "Free storage") }}</span
      ><strong class="smaller-stat">{{
        sizeText(overview.free_disk_bytes)
      }}</strong>
    </div>
  </div>
  <div class="tab-buttons admin-tabs">
    <button
      v-for="[value, zh, en] in [
        ['reviews', '申请审核', 'Reviews'],
        ['config', '共享规则', 'Access policy'],
        ['users', '账号管理', 'Accounts'],
        ['jobs', '处理任务', 'Jobs'],
        ['datasets', '数据版本', 'Releases'],
        ['content', '双语内容', 'Content'],
        ['audit', '操作审计', 'Audit'],
      ]"
      :key="value"
      :class="{ active: tab === value }"
      @click="switchTab(value)"
    >
      {{ tr(zh, en) }}
    </button>
  </div>
  <section v-if="tab === 'reviews'" class="panel form-panel">
    <div class="heading-row">
      <h3>{{ tr("流域数据申请", "Basin data applications") }}</h3>
      <select
        v-model="filter"
        @change="
          page = 1;
          load();
        "
      >
        <option value="">{{ tr("全部状态", "All statuses") }}</option>
        <option
          v-for="s in [
            'pending',
            'approved',
            'rejected',
            'withdrawn',
            'revoked',
          ]"
          :value="s"
          :key="s"
        >
          {{ statusText(s) }}
        </option>
      </select>
    </div>
    <div v-if="!items.length" class="empty">
      {{ tr("当前没有对应申请。", "No applications in this view.") }}
    </div>
    <article v-for="a in items" :key="a.id" class="application-card">
      <div class="heading-row">
        <h3 class="code">
          {{ a.basin_code }} <small>{{ a.version_code }}</small>
        </h3>
        <span class="pill amber">{{ statusText(a.status) }}</span>
      </div>
      <p>
        <strong>{{ a.applicant_name }}</strong> · {{ a.affiliation }} ·
        {{ a.contact_email }}
      </p>
      <dl>
        <dt>{{ tr("用途", "Purpose") }}</dt>
        <dd>{{ a.purpose }}</dd>
        <dt>{{ tr("大流域需求", "Why this basin") }}</dt>
        <dd>{{ a.large_basin_reason }}</dd>
        <dt>{{ tr("提交时间", "Submitted") }}</dt>
        <dd>{{ dateText(a.submitted_at) }}</dd>
      </dl>
      <a
        v-if="a.project_url"
        :href="a.project_url"
        target="_blank"
        rel="noopener noreferrer"
        >{{ tr("查看项目链接", "Open project URL") }} ↗</a
      >
      <p v-if="a.review_comment" class="review-note">{{ a.review_comment }}</p>
      <template v-if="['pending', 'approved'].includes(a.status)"
        ><label
          >{{
            tr(
              "审核意见 / 撤销原因（必填）",
              "Review comment / revocation reason (required)",
            )
          }}<textarea
            v-model="comments[a.id]"
            maxlength="5000"
            rows="2"
          ></textarea>
        </label>
        <div class="button-row">
          <button
            v-if="a.status === 'pending'"
            class="button primary"
            :disabled="busy || !comments[a.id]?.trim()"
            @click="decision(a, 'approve')"
          >
            {{ tr("审核通过", "Approve") }}</button
          ><button
            class="button danger"
            :disabled="busy || !comments[a.id]?.trim()"
            @click="decision(a, a.status === 'pending' ? 'reject' : 'revoke')"
          >
            {{
              a.status === "pending"
                ? tr("驳回申请", "Reject")
                : tr("撤销授权", "Revoke access")
            }}
          </button>
        </div></template
      >
    </article>
  </section>
  <form
    v-else-if="tab === 'config'"
    class="panel form-panel"
    @submit.prevent="saveConfig"
  >
    <h2>{{ tr("流域共享规则", "Basin access policy") }}</h2>
    <p class="muted">
      {{
        tr(
          "流域级别为 1–7，阈值包含选中的起始级别。",
          "Basin levels are 1–7. The threshold is inclusive.",
        )
      }}
    </p>
    <div class="form-grid">
      <label
        >{{ tr("小流域起始级别", "Small basins start at")
        }}<select v-model.number="cfg.small_min_hierarchy_level">
          <option v-for="n in 7" :value="n" :key="n">
            {{ tr("第 " + n + " 级", "Level " + n) }}
          </option>
        </select></label
      ><label
        >{{ tr("结果文件保留时间（小时）", "Result retention (hours)")
        }}<input
          type="number"
          v-model.number="cfg.result_retention_hours"
          min="1"
          max="720"
          required /></label
      ><label
        >{{ tr("大流域授权有效期（小时）", "Approval validity (hours)")
        }}<input
          type="number"
          v-model.number="cfg.approval_validity_hours"
          min="1"
          max="8760"
          required /></label
      ><label class="checkbox"
        ><input type="checkbox" v-model="cfg.maintenance_mode" />{{
          tr("维护模式：暂停新请求", "Maintenance: pause new requests")
        }}</label
      >
    </div>
    <div class="review-note">
      {{ tr("调整后可直接获取：", "Direct access after this change: ")
      }}{{
        Array.from(
          { length: 8 - cfg.small_min_hierarchy_level },
          (_, i) => tr("第 " + (i + cfg.small_min_hierarchy_level) + " 级流域", "Level " + (i + cfg.small_min_hierarchy_level)),
        ).join("、")
      }}<br />{{
        tr(
          "账号仍累计两个不同编码；已经取得的编码资格保留。",
          "Accounts retain two distinct-code slots. Previously acquired access is retained.",
        )
      }}
    </div>
    <label
      >{{ tr("变更原因", "Reason for change")
      }}<textarea
        v-model="cfg.reason"
        required
        minlength="3"
        maxlength="1000"
        rows="2"
      ></textarea></label
    ><label class="checkbox"
      ><input type="checkbox" v-model="confirm" required />{{
        tr(
          "我已检查新规则及其影响。",
          "I have reviewed the new policy and its effects.",
        )
      }}</label
    ><button class="button primary" :disabled="busy || !confirm">
      {{ tr("发布新规则", "Publish new policy") }}
    </button>
  </form>
  <section v-else-if="tab === 'users'" class="panel table-scroll">
    <form class="user-search" @submit.prevent="searchUsers">
      <el-input v-model="userQuery" clearable maxlength="254" :placeholder="tr('搜索用户名或邮箱','Search username or email')" :aria-label="tr('搜索用户名或邮箱','Search username or email')" style="max-width:320px" @clear="searchUsers"/>
      <el-button type="primary" native-type="submit">{{tr('搜索','Search')}}</el-button>
      <el-button @click="userQuery='';searchUsers()">{{tr('重置','Reset')}}</el-button>
    </form>
    <el-empty v-if="!items.length" :description="tr('没有匹配的账号','No matching accounts')"/>
    <table>
      <thead>
        <tr>
          <th>{{ tr("账号", "Account") }}</th>
          <th>{{ tr("邮箱", "Email") }}</th>
          <th>{{ tr("角色", "Role") }}</th>
          <th>{{ tr("状态", "Status") }}</th>
          <th></th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="u in items" :key="u.id">
          <td>{{ u.username }}</td>
          <td>{{ u.email }}</td>
          <td>
            {{
              u.role === "admin" ? tr("管理员", "Admin") : tr("用户", "User")
            }}
          </td>
          <td>
            {{
              u.status === "active"
                ? tr("正常", "Active")
                : tr("停用", "Disabled")
            }}
          </td>
          <td>
            <button
              v-if="u.role !== 'admin'"
              class="text-button"
              @click="userStatus(u)"
            >
              {{
                u.status === "active"
                  ? tr("停用账号", "Disable")
                  : tr("启用账号", "Enable")
              }}
            </button>
          </td>
        </tr>
      </tbody>
    </table>
  </section>
  <section v-else-if="tab === 'jobs'" class="panel table-scroll">
    <div class="panel-heading">
      <span
        >{{ tr("最近处理时间", "Last processing heartbeat") }}:
        {{ dateText(overview.last_worker_heartbeat) }}</span
      ><span
        >{{ tr("传输字节", "Transferred") }}:
        {{ sizeText(overview.transfer_bytes) }}</span
      >
    </div>
    <div v-if="!items.length" class="empty">
      {{ tr("暂无处理任务。", "No processing tasks yet.") }}
    </div>
    <table v-else>
      <thead>
        <tr>
          <th>{{ tr("流域", "Basin") }}</th>
          <th>{{ tr("状态", "Status") }}</th>
          <th>{{ tr("提交时间", "Submitted") }}</th>
          <th></th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="j in items" :key="j.id">
          <td class="code">{{ j.basin_code }}</td>
          <td>
            {{ statusText(j.status)
            }}<small class="block">{{ j.error_code }}</small>
          </td>
          <td>{{ dateText(j.created_at) }}</td>
          <td>
            <button
              v-if="['queued', 'running', 'packaging'].includes(j.status)"
              class="text-button"
              @click="cancel(j)"
            >
              {{ tr("取消任务", "Cancel task") }}
            </button>
          </td>
        </tr>
      </tbody>
    </table>
  </section>
  <section v-else-if="tab === 'datasets'" class="panel form-panel">
    <h3>{{ tr("数据版本与发布", "Data releases") }}</h3>
    <p class="muted">
      {{
        tr(
          "源数据版本通过服务端导入命令校验后发布。此处可查看版本并停止共享。",
          "Source releases are validated and published through the server import command. View releases and withdraw sharing here.",
        )
      }}
    </p>
    <div v-if="!items.length" class="empty">
      {{ tr("尚未导入正式数据版本。", "No data releases have been imported.") }}
    </div>
    <div v-for="v in items" :key="v.id" class="application-card heading-row">
      <span
        ><strong>{{ v.version_code }}</strong> · {{ text(v, "title") }}
        <span class="pill">{{ statusText(v.status) }}</span></span
      ><button
        v-if="v.status === 'published'"
        class="button danger"
        @click="withdraw(v)"
      >
        {{ tr("停止共享", "Withdraw") }}
      </button>
    </div>
  </section>
  <section v-else-if="tab === 'content'" class="panel form-panel">
    <h3>{{ editingContentId ? tr('编辑双语内容', 'Edit bilingual content') : tr("发布双语内容", "Publish bilingual content") }}</h3>
    <form @submit.prevent="publishContent">
      <div class="form-grid">
        <label
          >{{ tr("唯一标识", "Unique slug")
          }}<input
            v-model="content.slug"
            required
            pattern="[a-z0-9-]+"
            placeholder="notice-2026-09" /></label
        ><label
          >{{ tr("类型", "Type")
          }}<select v-model="content.kind">
            <option value="notice">{{ tr("公告", "Notice") }}</option>
            <option value="help">{{ tr("帮助", "Help") }}</option>
            <option value="home">{{ tr("首页", "Home") }}</option>
            <option value="terms">{{ tr("使用条款", "Terms") }}</option>
            <option value="privacy">{{ tr("隐私政策", "Privacy") }}</option>
          </select></label
        ><label
          >{{ tr("中文标题", "Chinese title")
          }}<input v-model="content.title_zh" required maxlength="200" /></label
        ><label
          >{{ tr("英文标题", "English title")
          }}<input v-model="content.title_en" required maxlength="200" /></label
        ><label
          >{{ tr("中文正文", "Chinese body")
          }}<textarea
            v-model="content.body_zh"
            required
            rows="5"
          ></textarea></label
        ><label
          >{{ tr("英文正文", "English body")
          }}<textarea v-model="content.body_en" required rows="5"></textarea>
        </label>
      </div>
      <label>{{ tr('状态', 'Status') }} <select v-model="content.status"><option value="published">{{ tr('已发布', 'Published') }}</option><option value="draft">{{ tr('草稿', 'Draft') }}</option></select></label>
      <button class="button primary">
        {{ editingContentId ? tr('保存修改', 'Save changes') : tr("发布内容", "Publish content") }}
      </button>
      <button v-if="editingContentId" type="button" class="button" @click="cancelContentEdit">{{ tr('取消编辑', 'Cancel edit') }}</button>
    </form>
    <hr />
    <article v-for="p in items" :key="p.id" class="heading-row content-row">
      <strong>{{ text(p, "title") }}</strong
      ><span class="pill">{{ statusText(p.status) }}</span>
      <button type="button" class="button" @click="editContent(p)">{{ tr('编辑', 'Edit') }}</button>
    </article>
  </section>
  <section v-else class="panel table-scroll">
    <div v-if="!items.length" class="empty">
      {{ tr("暂无审计记录。", "No audit records yet.") }}
    </div>
    <table v-else>
      <thead>
        <tr>
          <th>{{ tr("时间", "Time") }}</th>
          <th>{{ tr("操作者", "Actor") }}</th>
          <th>{{ tr("动作", "Action") }}</th>
          <th>{{ tr("对象", "Object") }}</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="a in items" :key="a.id">
          <td>{{ dateText(a.created_at) }}</td>
          <td>{{ a.actor_user_id || tr("系统", "System") }}</td>
          <td class="code">{{ a.action_code }}</td>
          <td class="code">{{ a.object_id }}</td>
        </tr>
      </tbody>
    </table>
  </section>
  <div
    v-if="total > 20 && ['reviews', 'users', 'jobs'].includes(tab)"
    class="pagination"
  >
    <button
      class="button"
      :disabled="page === 1"
      @click="
        page--;
        load();
      "
    >
      ←</button
    ><span>{{ page }} / {{ Math.ceil(total / 20) }}</span
    ><button
      class="button"
      :disabled="page * 20 >= total"
      @click="
        page++;
        load();
      "
    >
      →
    </button>
  </div>
</div>
</template>

<style scoped>.user-search{display:flex;gap:10px;align-items:center;flex-wrap:wrap;margin-bottom:20px}</style>
