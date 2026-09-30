<script setup>
import "../styles/management.css";
import { ref, reactive, computed, onMounted, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { tr, text } from "../locales/index";
import { state } from "../stores/state";
import { api, requestKey } from "../api/client";
import { attempt, notify } from "../stores/notifications";
import { statusText } from "../locales/statuses";
import { dateText } from "../utils/format";
const route = useRoute(),
  router = useRouter(),
  items = ref([]),
  versions = ref([]),
  busy = ref(false),
  show = ref(!!route.query.basin),
  total = ref(0),
  page = ref(1),
  key = ref(requestKey());
const form = reactive({
  basin_code: route.query.basin || "",
  dataset_version_id: Number(route.query.version) || "",
  applicant_name: "",
  affiliation: "",
  usage_type: "project",
  usage_title: "",
  usage_owner: "",
  purpose: "",
  project_url: "",
  terms_accepted: false,
});
// 论文类型用固定代号提交，界面按语言取标签。
const thesisTypes = computed(() => [
  { value: "master", label: tr("硕士", "Master's thesis") },
  { value: "doctor", label: tr("博士", "Doctoral dissertation") },
  { value: "journal", label: tr("期刊论文", "Journal article") },
]);
function thesisTypeLabel(value) {
  return thesisTypes.value.find((t) => t.value === value)?.label || value;
}
// 项目负责人是自由文本，论文类型是枚举，切换时清掉旧值避免张冠李戴。
watch(
  () => form.usage_type,
  (type) => {
    form.usage_owner = type === "thesis" ? "master" : "";
  },
);
// 表单内容一变就换幂等键：重复点击仍由同一个键拦下，而改过内容后重新提交
// 会作为新申请提交，不会撞上“同一键、内容不同”的 409 死路。
watch(form, () => {
  key.value = requestKey();
});
function usageSummary(a) {
  const label =
    a.usage_type === "thesis" ? tr("论文", "Thesis") : tr("项目", "Project");
  const owner =
    a.usage_type === "thesis"
      ? thesisTypeLabel(a.usage_owner)
      : a.usage_owner || "—";
  return `${label} · ${a.usage_title || "—"} · ${owner}`;
}
async function load() {
  await attempt(async () => {
    const r = await api("/applications?page=" + page.value);
    items.value = r.items;
    total.value = r.total;
    versions.value = (await api("/datasets")).items;
    await resolveDefaultVersion();
  });
}
let versionRequest = 0;
async function resolveDefaultVersion() {
  const ticket = ++versionRequest;
  form.dataset_version_id = '';
  form.terms_accepted = false;
  if (!/^[0-9]{14}$/.test(form.basin_code)) return;
  try {
    const basin = await api('/watersheds/' + form.basin_code);
    if (ticket === versionRequest) form.dataset_version_id = basin.versions.find(v => v.status === 'available')?.id || '';
  } catch (error) {
    if (ticket === versionRequest) notify(error.message, 'error');
  }
}
watch(() => form.basin_code, resolveDefaultVersion);
async function submit() {
  busy.value = true;
  await attempt(async () => {
    await api("/applications", {
      method: "POST",
      headers: { "Idempotency-Key": key.value },
      body: { ...form, dataset_version_id: Number(form.dataset_version_id) },
    });
    key.value = requestKey();
    show.value = false;
    notify(
      tr(
        "申请已提交，审核结果将在此显示。",
        "Application submitted. The decision will appear here.",
      ),
    );
    await load();
  });
  busy.value = false;
}
async function withdraw(id) {
  await attempt(() =>
    api(`/applications/${id}/withdraw`, { method: "POST", body: {} }),
  );
  await load();
}
async function obtain(a) {
  busy.value = true;
  await attempt(async () => {
    await api("/jobs", {
      method: "POST",
      headers: { "Idempotency-Key": requestKey() },
      body: {
        basin_code: a.basin_code,
        dataset_version_id: a.dataset_version_id,
        application_id: a.id,
        terms_accepted: true,
      },
    });
    router.push("/tasks");
  });
  busy.value = false;
}
onMounted(load);
</script>
<template>
<div class="management-container">
  <div class="page-heading heading-row">
    <div>
      <h1>{{ tr("流域数据申请", "Basin data applications") }}</h1>

    </div>
    <button class="button primary" @click="show = !show">
      {{ show ? tr("收起表单", "Close form") : tr("新建申请 +", "New application +") }}
    </button>
  </div>
  <form v-if="show" class="panel form-panel" @submit.prevent="submit">
    <h2>{{ tr("填写申请表", "Application form") }}</h2>
    <div class="form-grid">
      <label
        >{{ tr("流域编码（仅一个）", "Basin code (one only)")
        }}<input
          v-model="form.basin_code"
          required
          pattern="[0-9]{14}"
          maxlength="14"
          class="code"
          placeholder="01020301000000" /></label
      ><label
        >{{ tr("申请人姓名", "Applicant name")
        }}<input
          v-model="form.applicant_name"
          required
          maxlength="100" /></label
      ><label
        >{{ tr("单位或身份说明", "Affiliation or researcher status")
        }}<input v-model="form.affiliation" required maxlength="255" /></label
      ><label
        >{{ tr("联系邮箱", "Contact email")
        }}<input :value="state.user?.email" type="email" readonly /></label
      ><label
        >{{ tr("用途", "Usage") }}
        <select v-model="form.usage_type" required>
          <option value="project">{{ tr("项目", "Project") }}</option>
          <option value="thesis">{{ tr("论文", "Thesis or paper") }}</option>
        </select></label
      ><label
        >{{ tr("项目链接（选填）", "Project URL (optional)")
        }}<input
          v-model="form.project_url"
          type="url"
          maxlength="2000"
          placeholder="https://"
      /></label>
      <label v-if="form.usage_type === 'project'"
        >{{ tr("项目名称", "Project name")
        }}<input v-model="form.usage_title" required maxlength="255" /></label
      ><label v-else
        >{{ tr("论文题目", "Thesis title")
        }}<input v-model="form.usage_title" required maxlength="255" /></label
      ><label v-if="form.usage_type === 'project'"
        >{{ tr("项目负责人", "Project lead")
        }}<input v-model="form.usage_owner" required maxlength="255" /></label
      ><label v-else
        >{{ tr("论文类型", "Thesis type") }}
        <select v-model="form.usage_owner" required>
          <option v-for="t in thesisTypes" :key="t.value" :value="t.value">
            {{ t.label }}
          </option>
        </select></label
      >
    </div>
    <label
      >{{ tr("申请理由（至少10字）", "Reason (at least 10 characters)")
      }}<textarea
        v-model="form.purpose"
        required
        minlength="10"
        maxlength="5000"
        rows="4"
      ></textarea>
    </label>
    <details v-if="form.dataset_version_id">
      <summary>
        {{ tr("使用条款和引用要求", "Data terms and citation") }}
      </summary>
      <p class="prewrap">
        {{
          text(
            versions.find((v) => v.id === Number(form.dataset_version_id)),
            "license_text",
          )
        }}
      </p>
      <p class="prewrap">
        {{
          versions.find((v) => v.id === Number(form.dataset_version_id))
            ?.citation
        }}
      </p>
    </details>
    <label class="checkbox"
      ><input type="checkbox" v-model="form.terms_accepted" required />{{
        tr(
          "我已阅读并同意数据使用和引用要求。",
          "I have read and accept the data terms and citation requirements.",
        )
      }}</label
    ><button class="button primary" :disabled="busy || !form.dataset_version_id">
      {{ tr("提交审核", "Submit for review") }} →
    </button>
    <p v-if="form.basin_code.length === 14 && !form.dataset_version_id" class="muted">
      {{
        tr(
          "该流域暂无可申请的数据。",
          "No data is currently available for this basin.",
        )
      }}
    </p>
  </form>
  <section class="panel">
    <div class="panel-heading">
      <h3>{{ tr("申请记录", "Application history") }}</h3>
      <button class="text-button" @click="load">
        ↻ {{ tr("刷新", "Refresh") }}
      </button>
    </div>
    <div v-if="!items.length" class="empty">
      <span class="large-icon">▤</span>
      <h3>{{ tr("还没有申请", "No applications yet") }}</h3>
      <p>
        {{
          tr(
            "您可以先探索流域，或填写上方表单。",
            "Explore the catalog first, or complete the form above.",
          )
        }}
      </p>
    </div>
    <div v-else class="application-list">
      <article v-for="a in items" :key="a.id" class="application-card">
        <div class="heading-row">
          <div>
            <strong class="code">{{ a.basin_code }}</strong
            >
          </div>
          <span
            :class="[
              'pill',
              a.status === 'approved'
                ? 'green'
                : a.status === 'rejected'
                  ? 'red'
                  : 'amber',
            ]"
            >{{
              a.status === "approved" &&
              new Date(a.authorization_expires_at) <= new Date()
                ? tr("授权已过期", "Approval expired")
                : statusText(a.status)
            }}</span
          >
        </div>
        <p class="usage-summary">{{ usageSummary(a) }}</p>
        <p>{{ a.purpose }}</p>
        <div v-if="a.review_comment" class="review-note">
          <strong>{{ tr("审核意见", "Review") }} · </strong
          >{{ a.review_comment }}
        </div>
        <div class="heading-row">
          <small class="muted"
            >{{ dateText(a.submitted_at)
            }}<span v-if="a.authorization_expires_at">
              · {{ tr("有效至", "Valid until") }}
              {{ dateText(a.authorization_expires_at) }}</span
            ></small
          ><button
            v-if="a.status === 'pending'"
            class="text-button"
            @click="withdraw(a.id)"
          >
            {{ tr("撤回", "Withdraw") }}</button
          ><button
            v-if="
              a.status === 'approved' &&
              new Date(a.authorization_expires_at) > new Date()
            "
            class="button primary small-button"
            :disabled="busy"
            @click="obtain(a)"
          >
            {{ tr("生成完整包", "Prepare full package") }} ↓
          </button>
        </div>
      </article>
    </div>
    <div v-if="total > 20" class="pagination">
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
  </section>
</div>
</template>
