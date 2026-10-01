import { ref } from "vue";
export const locale = ref(
  localStorage.getItem("concn_locale") === "en" ? "en" : "zh-CN",
);
export const tr = (zh, en) => (locale.value === "en" ? en : zh);
export const text = (row, key) =>
  row?.[`${key}_${locale.value === "en" ? "en" : "zh"}`] ||
  row?.[`${key}_zh`] ||
  row?.[`${key}_en`] ||
  "";
