import { reactive } from "vue";
export const state = reactive({
  user: null,
  config: null,
  notice: "",
  noticeKind: "info",
});
