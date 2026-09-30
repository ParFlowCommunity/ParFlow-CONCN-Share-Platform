import { tr } from "./index";
const statuses = {
  queued: ["排队中", "Queued"],
  running: ["裁切中", "Clipping"],
  packaging: ["打包校验", "Packaging"],
  succeeded: ["可下载", "Ready"],
  failed: ["失败", "Failed"],
  cancel_requested: ["正在取消", "Cancelling"],
  cancelled: ["已取消", "Cancelled"],
  expired: ["已过期", "Expired"],
  pending: ["待审核", "Pending"],
  approved: ["已通过", "Approved"],
  rejected: ["已驳回", "Rejected"],
  withdrawn: ["已撤回", "Withdrawn"],
  revoked: ["已撤销", "Revoked"],
  active: ["已取得", "Acquired"],
  reserved: ["预占中", "Reserved"],
  draft: ["草稿", "Draft"],
  published: ["已发布", "Published"],
  disabled: ["已停用", "Disabled"],
};
export const statusText = (value) =>
  statuses[value] ? tr(...statuses[value]) : value;
