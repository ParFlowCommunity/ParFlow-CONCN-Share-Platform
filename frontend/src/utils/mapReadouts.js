export function coordinate(value, axis) {
  if (!Number.isFinite(value)) return '—';
  const n = axis === 'lng' ? ((value + 180) % 360 + 360) % 360 - 180 : Math.max(-90, Math.min(90, value));
  return `${axis === 'lng' ? (n < 0 ? 'W' : 'E') : (n < 0 ? 'S' : 'N')}${Math.abs(n).toFixed(5)}°`;
}
export function scaleAt(latitude, zoom) {
  const metresPerPixel = 156543.033928 * Math.cos(latitude * Math.PI / 180) / 2 ** zoom;
  if (!Number.isFinite(metresPerPixel) || metresPerPixel <= 0) return null;
  const maximum = metresPerPixel * 120;
  const magnitude = 10 ** Math.floor(Math.log10(maximum));
  const distance = [5, 2, 1].map(n => n * magnitude).find(n => n <= maximum) || magnitude / 2;
  return {width: distance / metresPerPixel, text: distance >= 1000 ? `${distance / 1000} km` : `${distance} m`};
}
