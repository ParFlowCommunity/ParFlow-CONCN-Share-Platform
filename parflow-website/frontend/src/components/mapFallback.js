// Keep the original map component's interaction contract when its provider is unavailable.
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';

export function leafletFallback() {
  class LngLat {
    constructor(lng, lat) { this.lng = lng; this.lat = lat; }
  }
  const pair = p => [p.lat, p.lng];
  class Map {
    constructor(element, options) {
      this.inner = L.map(element, { ...options, zoomSnap: 0.1, zoomControl: false, preferCanvas: true });
      this.baseMaps = {
        standard: L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        maxZoom: 18,
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
        }),
        terrain: L.tileLayer('https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png', {
          maxNativeZoom: 17, maxZoom: 18,
          attribution: 'Map data: &copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>, SRTM | Map style: &copy; <a href="https://opentopomap.org">OpenTopoMap</a> (CC-BY-SA)',
        }),
      };
      this.setBaseMap('standard');
    }
    setBaseMap(type) {
      const layer = this.baseMaps[type] || this.baseMaps.standard;
      if (this.baseLayer === layer) return;
      if (this.baseLayer) this.inner.removeLayer(this.baseLayer);
      this.baseLayer = layer;
      layer.addTo(this.inner);
    }
    centerAndZoom(p, zoom) { this.inner.setView(pair(p), zoom); }
    panTo(p) { this.inner.panTo(pair(p)); }
    setZoom(z) { this.inner.setZoom(z); }
    getZoom() { return this.inner.getZoom(); }
    getCenter() { return this.inner.getCenter(); }
    addEventListener(event, fn) { this.inner.on(event, fn); }
    addLayer() { /* Native provider tiles are unavailable; the fallback owns its base layer. */ }
    addOverlay(polygon) { this.inner.addLayer(polygon); }
    removeOverlay(polygon) { this.inner.removeLayer(polygon); }
    setViewport(points) { if (points.length) this.inner.fitBounds(points.map(pair), { padding: [8, 8], animate: false }); }
    resize() { this.inner.invalidateSize(); }
    dispose() { this.inner.remove(); }
  }
  function Polygon(points, options) {
    const polygon = L.polygon(points.map(pair), options);
    polygon.addEventListener = (event, fn) => polygon.on(event, fn);
    return polygon;
  }
  return { Map, LngLat, Polygon, TileLayer: class {} };
}
