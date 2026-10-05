import { state } from "../stores/state";
import { errorText } from "../locales/errors";
export async function api(path, options = {}) {
  const response = await fetch("/api" + path, {
    ...options,
    credentials: "same-origin",
    headers: {
      "Content-Type": "application/json",
      "X-DataHub": "1",
      ...options.headers,
    },
    body: options.body === undefined ? undefined : JSON.stringify(options.body),
  });
  const result = await response.json();
  if (!response.ok) {
    if (response.status === 401) state.user = null;
    const err = new Error(errorText(result.error));
    err.code = result.error;
    throw err;
  }
  return result;
}
export { requestKey } from '../utils/requestKey';
