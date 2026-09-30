<template>
  <div class="map-container" @mouseleave="mouseLng=null;mouseLat=null">
    <div ref="mapContainer" class="map-canvas"></div>
    <div v-if="mapLoading || mapError" class="map-load-status" role="status" @click.stop>
      <span>{{ mapError || tr('正在加载地图，请稍候…', 'Loading map…') }}</span>
      <button v-if="mapError" type="button" @click="initMap">{{ tr('重试', 'Retry') }}</button>
    </div>
    <div v-if="scale" class="map-scale" :aria-label="tr('比例尺','Scale')"><div class="scale-line" :style="{width:scale.width+'px'}"></div><span>{{scale.text}}</span></div>
    <div class="map-coordinates">{{tr('经度','Longitude')}}: {{coordinate(mouseLng,'lng')}}　{{tr('纬度','Latitude')}}: {{coordinate(mouseLat,'lat')}}</div>
    <label class="map-type-control" @click.stop @dblclick.stop @mousedown.stop @wheel.stop>
      {{ tr('地图类型', 'Map type') }}
      <select v-model="mapType" @change="changeMapType">
        <option value="standard">{{ tr('标准', 'Standard') }}</option>
        <option value="terrain">{{ tr('地形', 'Terrain') }}</option>
      </select>
    </label>
  </div>
</template>

<script>
import { markRaw } from 'vue';
import {coordinate,scaleAt} from '../utils/mapReadouts';
import { loadMapProvider, mapKey } from './mapProvider';
let T;
// 普通流域: 蓝色描边无填充; 高亮流域: 半透明橙色填充 + 同普通流域蓝色描边
import { tr } from '@/locales';


// 普通流域: 蓝色描边无填充; 高亮流域: 半透明橙色填充 + 同普通流域蓝色描边
const DEFAULT_STYLE = { color: '#2c6b9e', weight: 1.5, opacity: 0.85, fillColor: '#ffffff', fillOpacity: 0 };
const CLICK_STYLE = { color:'#23865a',weight:2,opacity:1,fillColor:'#35a774',fillOpacity:0.3 };
const HIGHLIGHT_STYLE = { color: '#2c6b9e', weight: 1.5, opacity: 0.85, fillColor: '#e67e22', fillOpacity: 0.35 };

export default {
  name: 'MapComponent',
  setup(){return {tr,coordinate};},
  props: {
    clickHighlightId: {type:String,default:''},
    center: {
      type: Array,
      default: () => [116.40769, 39.89945],
    },
    zoom: {
      type: Number,
      default: 5,
    },
    // GeoJSON 边界数据（FeatureCollection），用于显示流域多边形
    boundaryData: {
      type: Object,
      default: null,
    },
    // 需要高亮的流域 id 列表（搜索命中）
    highlightIds: {
      type: Array,
      default: () => [],
    },
  },
  emits: ['polygon-click'],
  data() {
    return {
      map: null,
      mapLoading: false,
      mapError: "",
      mouseLng:null,mouseLat:null,scale:null,
      boundaryOverlays: [],    // 已添加的边界多边形（T.Polygon）
      renderTimer: null,       // 分批渲染定时器（大级别防止一次性创建数万多边形卡死）
      mapType: 'terrain',
      baseLayers: [],
      _clickFid: null,         // 当前点击高亮的流域 id（点击高亮, 与搜索高亮相互覆盖）
      _skipNextHighlightRender: false, // 点击高亮后跳过父组件同步 highlightIds 触发的重渲染
    };
  },
  watch: {
    center: {
      handler(newCenter) {
        if (this.map && newCenter) {
          this.map.panTo(new T.LngLat(newCenter[0], newCenter[1]));
        }
      },
      deep: true,
    },
    boundaryData: {
      handler(newData) {
        if (newData && newData.features) {
          // 切换级别只更新边界，保持当前中心和缩放。
          this.renderBoundaries(newData);
        } else {
          this.clearBoundaries();
        }
      },
      deep: true,
    },
    highlightIds: {handler(){this.applyHighlightStyles();},deep:true},
    clickHighlightId(){this.applyHighlightStyles();},
  },
  mounted() {
    this.initMap();
  },
  beforeUnmount() {
    this.clearBoundaries();
    if (this.map) {
      try {
        if (typeof this.map.dispose === 'function') {
          this.map.dispose();
        }
      } catch (e) {
        // 忽略
      }
      this.map = null;
      this.boundaryOverlays = [];
    }
  },
  methods: {
    async initMap() {
      if (this.mapLoading) return;
      this.mapLoading = true;
      this.mapError = '';
      try {
        T = await loadMapProvider();
        if (!this.$refs.mapContainer) return;
        // 1. 创建地图实例
        //    maxZoom=18（天地图瓦片最高 18 级，超过会瓦片缺失出现白屏）、
        //    minZoom=3（防止缩放过远整屏无瓦片）
        this.map = markRaw(new T.Map(this.$refs.mapContainer, { maxZoom: 18, minZoom: 3 }));
        this.map.addEventListener('mousemove', e => {
          const p=e.lnglat||e.latlng;
          if(!p)return;
          this.mouseLng=Number(typeof p.getLng==='function'?p.getLng():typeof p.lng==='function'?p.lng():p.lng);
          this.mouseLat=Number(typeof p.getLat==='function'?p.getLat():typeof p.lat==='function'?p.lat():p.lat);
        });
        this.map.addEventListener('moveend',this.updateScale);
        this.map.addEventListener('zoomend',this.updateScale);

        // 兜底：若仍出现超限缩放，强制拉回（某些天地图版本对构造参数支持不完整）
        this.map.addEventListener('zoomend', () => {
          const z = this.map.getZoom();
          if (z > 18) this.map.setZoom(18);
          if (z < 3) this.map.setZoom(3);
        });

        await this.$nextTick();
        this._forceResize();
        this.focusRegion([73, 18, 135, 54]);
        this.updateScale();
        this.changeMapType();
        if (this.boundaryData) this.renderBoundaries(this.boundaryData);
      } catch (error) {
        console.error('地图初始化失败:', error);
        this.mapError = this.mapErrorText(error);
        this.clearBoundaries();
        if (this.map) this.map.dispose();
        this.map = null;
      } finally {
        this.mapLoading = false;
      }
    },

    updateScale(){
      if(!this.map)return;
      const p=this.map.getCenter();
      const lat=Number(typeof p.getLat==='function'?p.getLat():typeof p.lat==='function'?p.lat():p.lat);
      this.scale=scaleAt(lat,this.map.getZoom());
    },
    changeMapType() {
      if (!this.map) return;
      if (typeof this.map.setBaseMap === 'function') {
        this.map.setBaseMap(this.mapType);
        return;
      }
      this.baseLayers.forEach(layer => this.map.removeLayer(layer));
      const types = this.mapType === 'terrain' ? ['ter', 'cta'] : ['vec', 'cva'];
      this.baseLayers = types.map(type => markRaw(new T.TileLayer(
        `https://t0.tianditu.gov.cn/${type}_w/wmts?SERVICE=WMTS&REQUEST=GetTile&VERSION=1.0.0&LAYER=${type}&STYLE=default&TILEMATRIXSET=w&FORMAT=tiles&TILEMATRIX={z}&TILEROW={y}&TILECOL={x}&tk=${encodeURIComponent(mapKey)}`
      )));
      this.baseLayers.forEach(layer => this.map.addLayer(layer));
    },

    // 定位到指定流域：把流域置于地图中央，并按流域级别调整缩放
    focusRegion(bounds) {
      if (!this.map || !Array.isArray(bounds) || bounds.length !== 4) return;
      this.map.setViewport([new T.LngLat(bounds[0],bounds[1]),new T.LngLat(bounds[2],bounds[3])]);
      if(this.map.getZoom()>10)this.map.setZoom(10);
    },
    // 地图 SDK 的失败文案按当前语言显示；其他错误沿用原始消息。
    mapErrorText(error) {
      const known = {
        MAP_SDK_LOAD_FAILED: [
          '天地图加载失败，请检查网络连接后重试。',
          'Failed to load the map service. Check your network connection and retry.',
        ],
        MAP_SDK_UNAVAILABLE: [
          '天地图脚本已返回，但地图组件不可用。请检查网络后重试。',
          'The map service returned without a usable component. Check your network and retry.',
        ],
      };
      const text = known[error?.code];
      // 直接用模块作用域的 tr，不依赖 setup() 返回值在实例上的可见性。
      return text ? tr(text[0], text[1]) : error?.message;
    },

    // 定位到指定流域：只把流域平移到视野中央，缩放完全保持用户当前的值。
    // 早期版本会按流域级别自动缩放，但同一级别的流域面积能差上百倍，写死的级别
    // 不是太远就是太近；改成不动缩放后行为可预测，缩放由用户自己掌握。
    focusWatershed(lng, lat) {
      if (!this.map || lng === undefined || lat === undefined) return;
      // 用 centerAndZoom 一步设置中心和缩放。
      // 注意不能用 panTo + setZoom 连调: panTo 带平移动画, 会与 setZoom 相互打断, 导致没有实际移动
      this.map.centerAndZoom(new T.LngLat(lng, lat), this.map.getZoom());
    },

    // 地图容器尺寸变化后通知地图重算（兼容不同天地图版本）
    _forceResize() {
      if (!this.map) return;
      if (typeof this.map.resize === 'function') {
        this.map.resize();
        return;
      }
      if (typeof this.map.invalidateSize === 'function') {
        this.map.invalidateSize();
        return;
      }
      if (window) window.dispatchEvent(new Event('resize'));
    },

    // ---- 兼容不同天地图版本：v2.0 用 addOverLay（L 大写），v3/v4 用 addOverlay ----
    _addOverlay(overlay) {
      const fn = this.map.addOverlay || this.map.addOverLay;
      if (typeof fn === 'function') fn.call(this.map, overlay);
    },

    _removeOverlay(overlay) {
      const fn = this.map.removeOverlay || this.map.removeOverLay;
      if (typeof fn === 'function') fn.call(this.map, overlay);
    },

    // ---- 流域边界渲染 ----
    clearBoundaries() {
      // 取消未完成的分批渲染
      if (this.renderTimer) {
        clearTimeout(this.renderTimer);
        this.renderTimer = null;
      }
      this.boundaryOverlays.forEach((p) => {
        this._removeOverlay(p);
      });
      this.boundaryOverlays = [];
    },

    renderBoundaries(geojson) {
      if (!this.map || !geojson || !geojson.features) return;

      // 清空旧边界
      this.clearBoundaries();

      const highlightSet = new Set((this.highlightIds || []).map(String));
      const features = geojson.features;

      // 先收集所有待添加的多边形，避免渲染中途被新数据打断
      const jobs = [];
      features.forEach((feature) => {
        const props = feature.properties || {};
        const fid = String(props.PFBAS_ID || props.id || '');
        const isHighlight = highlightSet.size > 0 && highlightSet.has(fid);

        // 普通流域: 只显示蓝色边界轮廓（fillOpacity 0 = 透明）
        // 搜索命中流域: 半透明橙色填充（fillOpacity 0.35, 能透出底图）+ 与普通流域相同的蓝色描边
        const style = this.styleFor(fid);

        const geom = feature.geometry;
        if (!geom) return;

        if (geom.type === 'Polygon') {
          jobs.push({ coordinates: geom.coordinates, style, props });
        } else if (geom.type === 'MultiPolygon') {
          // 每个"部分"结构和 Polygon 相同: [外环, 内环...]，直接传给 _addPolygon
          // （注意: 不能包一层 [part]，否则 _addPolygon 取 coordinates[0] 会拿到整个部分）
          // 所有部分共享同一 PFBAS_ID，点击任一 part 都发射同一 properties
          geom.coordinates.forEach((part) => jobs.push({ coordinates: part, style, props }));
        }
      });

      // 分批渲染：大级别（如 14 级 5 万多个多边形）一次性创建会卡死浏览器
      const BATCH_SIZE = 100;
      let index = 0;
      const addNextBatch = () => {
        this.renderTimer = null;
        const end = Math.min(index + BATCH_SIZE, jobs.length);
        const started = performance.now();
        for (; index < end; index++) {
          this._addPolygon(jobs[index].coordinates, jobs[index].style, jobs[index].props);
          if (performance.now() - started >= 8) { index++; break; }
        }
        if (index < jobs.length) {
          this.renderTimer = setTimeout(addNextBatch, 0);
        } else {
          console.log(`[边界] 已渲染 ${features.length} 个流域边界`);
        }
      };
      addNextBatch();
    },

    _addPolygon(coordinates, style, properties) {
      // coordinates: Polygon 是 [[lng,lat],...][]，MultiPolygon 我们传的是 [ring]
      // 取第一个环（外环）的坐标
      const outer = coordinates[0];
      if (!outer || outer.length < 3) return;

      const points = outer.map((coord) => new T.LngLat(coord[0], coord[1]));
      style=this.styleFor(String(properties?.PFBAS_ID||properties?.id||''));
      const polygon = markRaw(new T.Polygon(points, {
        color: style.color,
        weight: style.weight,
        opacity: style.opacity,
        fillColor: style.fillColor,
        fillOpacity: style.fillOpacity,
      }));

      // 记录流域 id 与初始样式（点击高亮/恢复时用 setStyle 就地修改，避免全量重渲染）
      const fid = properties ? String(properties.PFBAS_ID || properties.id || '') : '';
      polygon._fid = fid;
      polygon._baseStyle = style;

      // 点击多边形时向父组件发射流域属性（PFBAS_ID / area）
      if (properties) {
        const self = this;
        polygon.addEventListener('click', function () {
          self.$emit('polygon-click', properties);
        });
      }

      this._addOverlay(polygon);
      this.boundaryOverlays.push(polygon);
    },

    // 就地高亮指定流域（恢复其他流域为各自初始样式，再把高亮样式套到目标流域上）。
    // 只调用 setStyle，不重建多边形 → 大级别下也不会卡顿
    styleFor(fid){return fid===this.clickHighlightId?CLICK_STYLE:(this.highlightIds||[]).map(String).includes(fid)?HIGHLIGHT_STYLE:DEFAULT_STYLE;},
    applyHighlightStyles(){this.boundaryOverlays.forEach(poly=>{if(typeof poly.setStyle==='function')poly.setStyle(this.styleFor(poly._fid));});},

    // 供父组件调用: 右侧栏折叠/展开后地图容器尺寸变化，通知地图重算
    handleResize() {
      this._forceResize();
    },
  },
};
</script>

<style scoped>
.map-canvas { width: 100%; height: 100%; min-height: 400px; }
.map-load-status { position: absolute; z-index: 1100; top: 60px; left: 12px; right: 12px; padding: 12px; background: white; color: #303133; border: 1px solid #dcdfe6; }
.map-load-status button { margin-left: 12px; cursor: pointer; }
.map-container {
  width: 100%;
  height: 100%;
  min-height: 400px;
  position: relative;
}

.map-type-control {
  position: absolute;
  top: 10px;
  left: 10px;
  z-index: 1000;
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 10px;
  border: 1px solid #dcdfe6;
  border-radius: 4px;
  background: white;
  color: #606266;
  font-size: 13px;
}
.map-type-control select { padding: 3px; max-width: 130px; }
</style>

<style scoped>
.map-coordinates,.map-scale{position:absolute;z-index:1000;bottom:32px;background:rgba(255,255,255,.94);color:#4b5563;border:1px solid #dce2e8;border-radius:4px;padding:6px 9px;font-size:12px;pointer-events:none;box-shadow:0 1px 5px #0001;}
.map-coordinates{right:12px;font-variant-numeric:tabular-nums;}
.map-scale{left:12px;text-align:center;}.scale-line{height:5px;border:2px solid #59636e;border-top:0;margin:0 auto 3px;box-sizing:border-box;}
@media(max-width:500px){.map-coordinates{bottom:66px;font-size:11px;right:8px;}.map-scale{left:8px;}}
</style>
