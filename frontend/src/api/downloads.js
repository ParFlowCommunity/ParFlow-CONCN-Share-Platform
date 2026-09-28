import { api } from "./client";
import { refreshMe } from "../stores/session";
export const download = async (id) => {
  const result = await api(`/jobs/${id}/download-session`, {
    method: "POST",
    body: {},
  });
  const a = document.createElement("a");
  a.href = result.url;
  a.download = "";
  document.body.appendChild(a);
  a.click();
  a.remove();
  await refreshMe();
};
