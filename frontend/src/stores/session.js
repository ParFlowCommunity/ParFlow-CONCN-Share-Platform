import { watch } from "vue";
import { state } from "./state";
import { api } from "../api/client";
import { notify, attempt } from "./notifications";
import { locale } from "../locales";
export async function refreshMe() {
  state.user = await api("/me");
  return state.user;
}
export async function refreshConfig() {
  state.config = await api("/config");
}
let startup;
export function initialize() {
  if (!startup)
    startup = Promise.all([
      refreshConfig(),
      refreshMe().catch((e) => {
        if (e.code !== "LOGIN_REQUIRED") throw e;
      }),
    ]).catch((e) => notify(e.message, "error"));
  return startup;
}
watch(
  locale,
  (value) => {
    localStorage.setItem("concn_locale", value);
    document.documentElement.lang = value;
    if (state.user)
      attempt(() =>
        api("/me/locale", { method: "PUT", body: { locale: value } }),
      );
  },
  { immediate: true },
);
