import { state } from "./state";
import { tr } from "../locales";
let timer;
export function notify(message, kind = "info") {
  state.notice = message;
  state.noticeKind = kind;
  clearTimeout(timer);
  timer = setTimeout(() => (state.notice = ""), 7000);
}
export async function attempt(fn) {
  try {
    return await fn();
  } catch (error) {
    notify(
      error.message || tr("网络连接失败。", "Network connection failed."),
      "error",
    );
  }
}
