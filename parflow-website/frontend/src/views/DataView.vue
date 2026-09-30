<template>
  <div id="data-view">
    <!-- 搜索区域 -->
    <el-card class="search-card" shadow="never">
      <el-form :inline="true" :model="searchForm" class="search-form">
        <el-form-item :label="tr('省份', 'Province')">
          <el-select v-model="provinceCode" filterable clearable :placeholder="tr('选择省份', 'Select province')" style="width:160px" @change="provinceChanged">
            <el-option v-for="r in provinces" :key="r.code" :value="r.code" :label="r.name_zh" />
          </el-select>
        </el-form-item>
        <el-form-item :label="tr('城市', 'City')">
          <el-select v-model="cityCode" filterable clearable :disabled="!provinceCode || !cities.length" :loading="citiesLoading" :placeholder="!provinceCode ? tr('请先选择省份', 'Select a province first') : citiesLoading ? tr('正在加载城市…', 'Loading cities…') : tr(!cities.length ? '暂无城市数据' : '选择城市', !cities.length ? 'No city data' : 'Select city')" style="width:170px" @change="cityChanged">
            <el-option v-for="r in cities" :key="r.code" :value="r.code" :label="r.name_zh" />
          </el-select>
        </el-form-item>
        <el-form-item :label="tr('流域编号', 'Basin code')">
          <el-input
            v-model="searchForm.keyword"
            :placeholder="tr('请输入14位数字流域编号', 'Enter a 14-digit basin code')"
            inputmode="numeric"
            @keyup.enter="handleSearch"
            clearable
            style="width: 220px;"
          />
        </el-form-item>
        <el-form-item :label="tr('流域级别', 'Basin level')">
          <el-select
            v-model="searchForm.level"
            :placeholder="tr('请选择级别', 'Select level')"
            clearable
            style="width: 140px;"
          >
            <el-option
              v-for="num in levelOptions"
              :key="num"
              :label="tr(+num+' 级','Level '+num+' basin')"
              :value="num"
            />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="handleSearch" :loading="loading" :disabled="!validSearchCode">{{ tr('搜索', 'Search') }}</el-button>
          <el-button @click="resetSearch">{{ tr('重置', 'Reset') }}</el-button>
          <el-button type="primary" :disabled="!currentWatershed" @click="downloadCurrentWatershed">{{tr('下载数据','Download data')}}</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- 主体区域：左侧地图 + 右侧流域信息（可折叠，折叠后地图占满，信息栏缩成悬浮按钮） -->
    <el-row :gutter="0" class="main-row">
      <el-col
        :xs="24"
        :sm="infoPanelVisible ? 16 : 24"
        :md="infoPanelVisible ? 16 : 24"
        :lg="infoPanelVisible ? 16 : 24"
        class="map-col" :class="{ 'with-info': infoPanelVisible }"
      >
        <el-card class="map-card" shadow="never">
          <template #header>
            <span>{{ tr('流域分布地图', 'Basin map') }}</span>
          </template>
          <MapComponent
            ref="mapComponent"
            :center="mapCenter"
            :boundary-data="boundaryData"
            :highlight-ids="highlightIds"
            :click-highlight-id="clickHighlightId"
            @polygon-click="onPolygonClick"
          />
        </el-card>
      </el-col>
      <el-col v-if="infoPanelVisible" :xs="24" :sm="8" :md="8" :lg="8" class="info-col">
        <el-card class="info-card" shadow="never">
          <template #header>
            <div class="info-card-header">
              <span>{{ tr('流域信息', 'Basin information') }}</span>
              <el-button
                class="info-collapse-btn"
                type="primary"
                size="small"
                :title="tr('收起信息栏', 'Collapse information')"
                @click="infoPanelVisible = false"
              >{{ tr('收起', 'Collapse') }}</el-button>
            </div>
          </template>
          <div v-if="currentWatershed" class="info-content">
            <p><strong>{{ tr('编号：', 'Code:') }}</strong>{{ currentWatershed.id }}</p>
            <p><strong>{{ tr('级别：','Level:') }}</strong>{{ tr('第 '+currentWatershed.level/2+' 级流域','Level '+currentWatershed.level/2+' basin') }}</p>
            <p><strong>{{ tr('经纬度范围：', 'Bounds:') }}</strong>{{ bboxText || '—' }}</p>
            <p><strong>{{ tr('面积：', 'Area:') }}</strong>{{ areaText || '—' }}</p>

          </div>
          <div v-else class="info-placeholder">
            <span style="color: #bbb;">{{ tr('请搜索或点击地图上的流域查看详情', 'Search or click a basin to view details') }}</span>
          </div>

        </el-card>
      </el-col>
    </el-row>

    <!-- 信息栏折叠后的恢复按钮（悬浮在地图右下角，展开信息栏） -->
    <button
      v-if="!infoPanelVisible"
      class="info-restore-btn"
      @click="infoPanelVisible = true"
    >{{ tr('流域信息 ▸', 'Basin information ▸') }}</button>
    <BasinDownloadDialog v-model="downloadOpen" :basin="downloadBasin" :version="downloadVersion"/>
  </div>
</template>
<script>
import { markRaw } from 'vue';
import BasinDownloadDialog from '@/components/BasinDownloadDialog.vue';
import MapComponent from '@/components/MapComponent.vue';
import { formatBBox,formatArea } from '@/utils/format';
import { tr } from '@/locales';
import { state } from '@/stores/state';
import { api,requestKey } from '@/api/client';
export default {
  name:'DataView',components:{MapComponent,BasinDownloadDialog},setup(){return {tr,state};},
  data(){return {provinces:[],cities:[],provinceCode:'',cityCode:'',citiesLoading:false,regionRequest:0,searchForm:{keyword:'',level:1},levelOptions:[1,2,3,4,5,6,7],tableData:[],currentWatershed:null,
    loading:false,downloading:false,downloadOpen:false,downloadBasin:null,downloadVersion:null,mapCenter:[116.40769,39.89945],boundaryData:null,boundaryLevel:null,
    highlightIds:[],clickHighlightId:'',infoPanelVisible:true,bboxMap:{},selectedVersion:null,boundaryRequest:0,selectionRequest:0};},
  computed:{
    validSearchCode(){return /^[0-9]{14}$/.test(this.searchForm.keyword);},
    bboxText(){return this.currentWatershed?formatBBox(this.currentWatershed.bbox):'';},
    areaText(){return this.currentWatershed?formatArea(this.currentWatershed.area):'';},
    isSmall(){return !!this.currentWatershed&&(!!state.user?.slots?.some(s=>s.basin_code===this.currentWatershed.id)||this.currentWatershed.level/2 >= (state.config?.small_min_hierarchy_level||5));}
  },
  async mounted(){this.loadRegions();await this.loadBoundaries(2);if(this.$route.query.basin){this.searchForm.keyword=String(this.$route.query.basin);await this.handleSearch();}},
  activated(){this.$nextTick(()=>this.$refs.mapComponent?.handleResize());},
  deactivated(){this.downloadOpen=false;},
  beforeUnmount(){this.regionRequest++;this.boundaryRequest++;this.selectionRequest++;},
  watch:{
    'searchForm.level'(value,old){if(value!==old){this.currentWatershed=null;this.selectedVersion=null;this.highlightIds=[];this.clickHighlightId='';this.loadBoundaries(value?value*2:null);}},
    infoPanelVisible(){this.$nextTick(()=>this.$refs.mapComponent?.handleResize());}
  },
  methods:{
    async loadRegions(){try{this.provinces=(await api('/regions')).items;}catch(e){this.$message.error(e.message);}},
    clearSelection(){this.selectionRequest++;this.currentWatershed=null;this.selectedVersion=null;this.highlightIds=[];this.clickHighlightId='';},
    locateRegion(region){if(!region)return;this.clearSelection();this.$refs.mapComponent?.focusRegion(region.view_bounds);},
    async provinceChanged(code){
      const ticket=++this.regionRequest;this.cityCode='';this.cities=[];this.citiesLoading=false;
      if(!code){this.$refs.mapComponent?.focusRegion([73,18,135,54]);return;}
      this.locateRegion(this.provinces.find(r=>r.code===code));this.citiesLoading=true;
      try{const result=await api('/regions?province='+encodeURIComponent(code));if(ticket===this.regionRequest)this.cities=result.items;}
      catch(e){if(ticket===this.regionRequest)this.$message.error(e.message);}
      finally{if(ticket===this.regionRequest)this.citiesLoading=false;}
    },
    cityChanged(code){this.locateRegion(code?this.cities.find(r=>r.code===code):this.provinces.find(r=>r.code===this.provinceCode));},

    async loadBoundaries(level){
      const ticket=++this.boundaryRequest;this.boundaryData=null;this.bboxMap={};this.boundaryLevel=level;
      if(!level)return;
      try{const data=await api('/boundaries?level='+level);if(ticket!==this.boundaryRequest)return;
        this.bboxMap=this.buildBBoxMap(data);this.boundaryData=markRaw(data);
      }catch(e){if(ticket===this.boundaryRequest)this.$message.error(e.message);}
    },
    buildBBoxMap(data){const result={};for(const f of data.features||[]){const box=[Infinity,Infinity,-Infinity,-Infinity];
      const walk=c=>{if(typeof c[0]==='number'){box[0]=Math.min(box[0],c[0]);box[1]=Math.min(box[1],c[1]);box[2]=Math.max(box[2],c[0]);box[3]=Math.max(box[3],c[1]);}else c.forEach(walk);};
      if(f.geometry)walk(f.geometry.coordinates);if(Number.isFinite(box[0]))result[String(f.properties.PFBAS_ID)]={minLng:box[0],minLat:box[1],maxLng:box[2],maxLat:box[3]};}return result;},
    displayRow(row){let bbox=this.bboxMap[row.basin_code]||row.bbox_wgs84||null;if(Array.isArray(bbox))bbox={minLng:bbox[0],minLat:bbox[1],maxLng:bbox[2],maxLat:bbox[3]};
      return {...row,id:row.basin_code,level:row.pfbas_level,region:row.region_zh||row.region_en||'—',area:row.area_km2,bbox,lng:row.center_lng,lat:row.center_lat};},
    async handleSearch(){
      const keyword=this.searchForm.keyword;if(!this.validSearchCode){this.$message.info(tr('流域编号必须为14位数字。','The basin code must contain exactly 14 digits.'));return;}
      this.loading=true;
      try{const result=await api('/watersheds?q='+encodeURIComponent(keyword));this.tableData=result.items;
        if(result.items.length){const row=result.items[0];await this.selectCode(row.basin_code,row.pfbas_level);return;}
        // Boundary-only preview does not create a published dataset or grant download permission.
        let level=this.boundaryLevel;
        if(/^\d{14}$/.test(keyword)){const count=keyword.replace(/0+$/,'').length;level=Math.max(2,Math.min(14,count+count%2));}
        if(level&&level!==this.boundaryLevel){this.searchForm.level=level/2;await this.$nextTick();await this.loadBoundaries(level);}
        const feature=this.boundaryData?.features.find(f=>String(f.properties.PFBAS_ID)===keyword);
        if(feature){await this.selectCode(keyword,level,feature.properties);return;}
        this.currentWatershed=null;this.highlightIds=[];this.clickHighlightId='';this.$message.info(tr('没有找到匹配的流域。正式目录尚未接入时，请使用完整编码查找边界。','No matching basin. Until the catalog is connected, use a full code to find its boundary.'));
      }catch(e){this.$message.error(e.message);}finally{this.loading=false;}
    },
    async selectCode(code,level,properties={},fromClick=false){
      const ticket=++this.selectionRequest;let row;
      try{row=await api('/watersheds/'+encodeURIComponent(code));}
      catch(e){if(e.code!=='NOT_FOUND')throw e;row={basin_code:code,pfbas_level:level,area_km2:properties.area_km2,versions:[],boundary_only:true};}
      if(ticket!==this.selectionRequest)return;
      if(level!==this.boundaryLevel){this.searchForm.level=level/2;await this.$nextTick();await this.loadBoundaries(level);}
      if(ticket!==this.selectionRequest)return;
      this.currentWatershed=this.displayRow(row);if(fromClick){this.clickHighlightId=code;}else{this.highlightIds=[code];this.clickHighlightId='';}this.infoPanelVisible=true;
      this.selectedVersion=row.versions?.find(v=>v.status==='available')?.id||null;
      const box=this.currentWatershed.bbox;
      const lng=this.currentWatershed.lng??(box?(box.minLng+box.maxLng)/2:null),lat=this.currentWatershed.lat??(box?(box.minLat+box.maxLat)/2:null);
      if(lng!==null&&lat!==null)this.$nextTick(()=>this.$refs.mapComponent?.focusWatershed(lng,lat));
    },
    async onPolygonClick(properties){const code=String(properties.PFBAS_ID||'');if(!code)return;try{await this.selectCode(code,this.boundaryLevel,properties,true);}catch(e){this.$message.error(e.message);}},
    resetSearch(){this.regionRequest++;this.provinceCode='';this.cityCode='';this.cities=[];this.citiesLoading=false;this.clearSelection();this.$refs.mapComponent?.focusRegion([73,18,135,54]);this.searchForm.keyword='';this.tableData=[];this.currentWatershed=null;this.highlightIds=[];this.clickHighlightId='';this.selectedVersion=null;this.searchForm.level=1;},
    async downloadCurrentWatershed(){
      const w=this.currentWatershed;if(!w){this.$message.info(tr('请先搜索或点击一个流域。','Select one basin first.'));return;}
      if(!state.user){this.$router.push({path:'/login',query:{next:'/data/view?basin='+w.id}});return;}
      if(!this.selectedVersion){this.$message.warning(tr('该流域暂时无法下载。','This basin is not currently available for download.'));return;}
      this.downloadBasin={...w};this.downloadVersion=Number(this.selectedVersion);this.downloadOpen=true;
    }
  }
};
</script>

<style scoped>
#data-view {
  height: 100%;
  display: flex;
  flex-direction: column;
  padding: 0;
  font-family: 'Helvetica Neue', Arial, sans-serif;
  background-color: #f5f7fa;
}
.search-card {
  margin-bottom: 10px;
  flex-shrink: 0;
  border-radius: 0;
}
.search-card :deep(.el-card__body) {padding:14px 20px;}
.search-form :deep(.el-form-item) {margin-bottom:0; margin-right:12px;}
.search-form {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
  padding: 0 10px;
}
.main-row {
  flex: 1;
  margin: 0 !important;
  width: 100%;
  min-height: 0;
}
.map-col,
.info-col {
  display: flex;
  flex-direction: column;
}
.map-card {
  height: 100%;
  border-radius: 0;
  display: flex;
  flex-direction: column;
}
/* 统一两个卡片 header 的高度与内边距并垂直居中，保证标题线（header 下边框）水平对齐 */
.map-card :deep(.el-card__header),
.info-card :deep(.el-card__header) {
  display: flex;
  align-items: center;
  height: 52px;
  padding: 0 20px;
  box-sizing: border-box;
}
.map-card :deep(.el-card__body) {
  flex: 1;
  padding: 0;
  display: flex;
  flex-direction: column;
}
.map-card :deep(.map-container) {
  flex: 1;
  width: 100%;
  min-height: 300px;
  background-color: #f5f7fa;
}
.info-card {
  height: 100%;
  border-radius: 0;
  display: flex;
  flex-direction: column;
}
.info-card :deep(.el-card__body) {
  flex: 1;
  padding: 0;
  display: flex;
  flex-direction: column;
}
.info-content {
  flex: 1;
  padding: 15px;
  overflow-y: auto;
}
.info-content p {
  overflow-wrap: anywhere;
  margin: 8px 0;
  font-size: 14px;
  line-height: 1.8;
  border-bottom: 1px solid #f0f0f0;
  padding-bottom: 6px;
}
.info-content strong {
  display: inline-block;
  width: 90px; /* 容纳最长的 label "经纬度范围:"（6 字符 ≈ 84px）不折行 */
  white-space: nowrap;
  color: #606266;
}
.info-placeholder {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #bbb;
  font-size: 16px;
}
/* 信息栏 header: 收起按钮推至整个屏幕最右侧 */
.info-card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex: 1; /* 占满 header 整行, 否则 space-between 只在内容宽度内生效, 右侧留大片空白 */
}
/* 覆盖统一 header 的右内边距: 与登录页注册按钮右缘对齐
   （登录框 .login-box 右内边距 35px, 注册按钮 width:100% 距屏幕右缘即 35px） */
.info-card :deep(.el-card__header) {
  padding: 0 15px;
}
.info-collapse-btn {
  /* 实心蓝底白字（type="primary" 默认样式, 与登录按钮一致）;
     字号比 mini 默认放大半号（12px → 14px）;
     padding 相应收窄, 保证按钮整体大小不变（与缩小后尺寸接近） */
  margin: 0;
  padding: 2px 8px;
  font-size: 14px;
  flex-shrink: 0;
}
/* 信息栏折叠后的悬浮恢复按钮（覆盖在地图右下角） */
.info-restore-btn {
  position: fixed;
  right: 24px;
  bottom: 32px;
  z-index: 2000;
  padding: 8px 14px;
  background: #fff;
  color: #409eff;
  border: 1px solid #c6e2ff;
  border-radius: 18px;
  font-size: 13px;
  cursor: pointer;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.15);
}
.info-restore-btn:hover {
  background: #ecf5ff;
}
.download-actions { padding: 15px; border-top: 1px solid #ebeef5; }
.download-actions .el-button { width: 100%; }
.info-placeholder { padding: 15px; }
@media (min-width: 768px) {
  .map-col.with-info { flex: 0 0 80%; max-width: 80%; }
  .info-col { flex: 0 0 20%; max-width: 20%; }
}
@media (max-width: 767px) {
  .main-row { flex: none; }
  .map-col { height: 380px; }
  .info-card { height: auto; min-height: 300px; }
  .map-card :deep(.map-container) {
    min-height: 320px;
  }
  .info-placeholder {
    min-height: 150px;
  }
  .search-form {
    padding: 0 5px;
  }
  .search-form .el-form-item {
    margin-bottom: 5px;
  }
}
</style>
