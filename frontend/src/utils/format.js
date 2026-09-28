import { locale } from "../locales";
export const dateText = (value) =>
  value
    ? new Date(value).toLocaleString(
        locale.value === "en" ? "en-GB" : "zh-CN",
        { hour12: false },
      )
    : "—";
export function sizeText(bytes) {
  if (bytes == null) return "—";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 ** 2) return `${(bytes / 1024).toFixed(1)} KiB`;
  if (bytes < 1024 ** 3) return `${(bytes / 1024 ** 2).toFixed(1)} MiB`;
  return `${(bytes / 1024 ** 3).toFixed(2)} GiB`;
}

/**
 * 流域信息格式化工具（DataView 右侧信息栏与 MapComponent 浮动信息卡共用）
 */

/**
 * 把流域包围盒格式化为范围字符串，如 "N26.12 S25.13 W114.22 E115.34"
 * 顺序: 北限(N) 南限(S) 西限(W) 东限(E)，保留两位小数
 * @param {{minLng:number, minLat:number, maxLng:number, maxLat:number}} bbox
 * @returns {string} 空 bbox 或非法值返回 ''
 */
export function formatBBox(bbox) {
  if (!bbox) return '';
  const { minLng, minLat, maxLng, maxLat } = bbox;
  if ([minLng, minLat, maxLng, maxLat].some((v) => typeof v !== 'number' || isNaN(v))) {
    return '';
  }
  const two = (v) => Math.abs(v).toFixed(2);
  // 方位指示（与正负号无关，全部取绝对值）: N=最北纬度 S=最南纬度 W=最西经度 E=最东经度
  const latN = `N${two(maxLat)}`;
  const latS = `S${two(minLat)}`;
  const lngW = `W${two(minLng)}`;
  const lngE = `E${two(maxLng)}`;
  return `${latN} ${latS} ${lngW} ${lngE}`;
}

/**
 * 面积保留两位小数
 * @param {number} area 单位 km²
 * @returns {string} 空值/非法值返回 ''
 */
export function formatArea(area) {
  if (area === null || area === undefined || area === '' || isNaN(Number(area))) {
    return '';
  }
  return `${Number(area).toFixed(2)} km²`;
}
