import { tr } from "./index";
const errors = {
  LOGIN_REQUIRED: ["请先登录账号。", "Please sign in first."],
  INVALID_CREDENTIALS: ["邮箱或密码不正确。", "Incorrect email or password."],
  INVALID_EMAIL: ["请输入有效邮箱。", "Enter a valid email."],
  INVALID_PASSWORD: [
    "密码需要 8–128 位，并包含字母和数字。",
    "Use 8–128 characters, including letters and numbers.",
  ],
  INVALID_FIELD: [
    "请检查必填字段及其长度。",
    "Check required fields and their lengths.",
  ],
  ACCOUNT_OR_RECORD_EXISTS: [
    "邮箱、用户名或记录已存在。",
    "This email, username or record already exists.",
  ],
  ACCOUNT_EXISTS: ["该邮箱已被使用。", "This email is already in use."],
  SMALL_BASIN_QUOTA_EXCEEDED: [
    "您已使用两个不同的小流域名额，可重复下载已有流域，其他流域可提交申请。",
    "You have used both small-basin slots. Existing basins remain available for repeat downloads.",
  ],
  APPROVAL_REQUIRED: [
    "该流域需要有效的审核授权。",
    "This basin requires valid approval.",
  ],
  SMALL_BASIN_USE_DIRECT: [
    "该流域当前属于小流域，请使用直接下载入口。",
    "This is currently a small basin. Use the direct download option.",
  ],
  DATA_UNAVAILABLE: [
    "该流域的数据版本尚未发布或暂不可用。",
    "This basin release is not published or is unavailable.",
  ],
  FILE_UNAVAILABLE: [
    "文件或下载授权已过期，请重新获取。",
    "The file or download session has expired. Request it again.",
  ],
  EMAIL_SERVICE_UNAVAILABLE: [
    "邮件服务尚未配置或暂不可用。",
    "Email delivery is not configured or is unavailable.",
  ],
  EMAIL_VERIFICATION_REQUIRED: [
    "请先在账号中心验证邮箱。",
    "Verify your email in your account first.",
  ],
  INVALID_TOKEN: [
    "邮箱操作链接无效或已过期。",
    "This email action link is invalid or expired.",
  ],
  FORBIDDEN: [
    "当前账号无权执行此操作。",
    "Your account cannot perform this action.",
  ],
  INVALID_STATE: [
    "状态已发生变化，请刷新后再试。",
    "The status has changed. Refresh and try again.",
  ],
  LOGIN_LOCKED: [
    "登录尝试过多，请 15 分钟后重试。",
    "Too many login attempts. Try again in 15 minutes.",
  ],
  RATE_LIMITED: [
    "操作太频繁，请稍后重试。",
    "Too many requests. Please try again shortly.",
  ],
  ACTIVE_JOB_LIMIT: [
    "已有两个未完成任务，请等待完成或取消任务。",
    "Two tasks are already active. Wait or cancel a task.",
  ],
  QUEUE_FULL: [
    "处理队列已满，请稍后重试。",
    "The queue is full. Try again shortly.",
  ],
  TERMS_REQUIRED: ["请确认数据使用条款。", "Accept the data terms first."],
  MAINTENANCE: [
    "平台正在维护，暂不接受新请求。",
    "Maintenance is in progress. New requests are paused.",
  ],
  CLIP_FAILED: [
    "裁切失败，请联系管理员检查源数据和工具配置。",
    "Clipping failed. Ask the administrator to check source data and tools.",
  ],
  TASK_TIMEOUT: [
    "任务超时，请联系管理员。",
    "The task timed out. Contact the administrator.",
  ],
  WORKER_LOST: [
    "处理进程中断，可重新提交任务。",
    "The worker was interrupted. Submit a new task to retry.",
  ],
  DISK_FULL: [
    "处理服务器存储不足。",
    "The processing server has insufficient storage.",
  ],
  OUTPUT_TOO_LARGE: [
    "完整包超过当前资源上限，请联系管理员。",
    "The full package exceeds the resource limit. Contact the administrator.",
  ],
  CANCELLED: ["任务已取消。", "The task was cancelled."],
  NOT_FOUND: ["未找到对应记录。", "Record not found."],
  SERVICE_UNAVAILABLE: [
    "服务暂不可用，请稍后再试。",
    "The service is temporarily unavailable.",
  ],
  BOUNDARY_UNAVAILABLE: [
    "边界数据尚未接入，可继续通过目录选择流域。",
    "Boundary data is not connected. You can still use the catalog.",
  ],
};
export const errorText = (code) => {
  const pair = errors[code];
  return pair
    ? tr(...pair)
    : tr(
        "操作失败，请检查输入或稍后重试。",
        "Request failed. Check your input or try again later.",
      );
};
