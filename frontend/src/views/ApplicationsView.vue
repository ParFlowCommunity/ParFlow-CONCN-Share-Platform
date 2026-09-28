<script setup>
import "../styles/management.css";
import { ref, reactive, onMounted, watch } from "vue";
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
  purpose: "",
  large_basin_reason: "",
  project_url: "",
  terms_accepted: false,
});
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
      {{
        show ? tr("收起表单", "Close form") : tr("新建申请", "New application")
      }}
      +
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
        >{{ tr("项目链接（选填）", "Project URL (optional)")
        }}<input
          v-model="form.project_url"
          type="url"
          maxlength="2000"
          placeholder="https://"
      /></label>
    </div>
    <label
      >{{ tr("研究或使用目的", "Research or intended use")
      }}<textarea
        v-model="form.purpose"
        required
        minlength="10"
        maxlength="5000"
        rows="4"
      ></textarea></label
    ><label
      >{{ tr("申请该流域数据的原因", "Why do you need this basin data?")
      }}<textarea
        v-model="form.large_basin_reason"
        required
        minlength="10"
        maxlength="5000"
        rows="3"
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
