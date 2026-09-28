<template>
  <div class="downloads-container">
    <el-card shadow="never">
      <template #header>
        <div class="downloads-header">
          <span>{{ tr('我的下载', 'My downloads') }}</span>
          <el-button type="primary" size="small" @click="loadDownloads">{{ tr('刷新', 'Refresh') }}</el-button>
        </div>
      </template>

      <el-table
        v-loading="loading"
        :data="downloads"
        row-key="id"
        scrollbar-always-on
        style="width: 100%"
        :empty-text="tr('暂无下载记录', 'No downloads yet')"
      >
        <el-table-column :label="tr('下载时间', 'Created')" min-width="155" show-overflow-tooltip><template #default="{row}">{{dateText(row.created_at)}}</template></el-table-column>
        <el-table-column :label="tr('流域级别', 'Basin level')" min-width="90">
          <template #default="{ row }">
            <el-tag size="small" type="info">{{row.pfbas_level?tr('第 '+row.pfbas_level/2+' 级','Level '+row.pfbas_level/2):'—'}}</el-tag>
          </template>
        </el-table-column>
        <el-table-column :label="tr('流域编号', 'Basin code')" min-width="160">
          <template #default="{ row }">
            <span class="ids-text">{{ row.basin_code }}</span>
          </template>
        </el-table-column>
        <el-table-column :label="tr('文件大小', 'File size')" min-width="95">
          <template #default="{ row }">
            {{ sizeText(row.byte_size) }}
          </template>
        </el-table-column>
        <el-table-column :label="tr('状态','Status')" min-width="105"><template #default="{row}"><el-tag :type="row.status==='failed'?'danger':'info'">{{statusText(row.status)}}</el-tag><div v-if="row.error_code" style="font-size:12px">{{errorText(row.error_code)}}</div></template></el-table-column>
        <el-table-column :label="tr('操作', 'Actions')" width="130" fixed="right">
          <template #default="{ row }">
            <el-button
              type="primary"
              size="small"
              v-if="row.status==='succeeded'" :loading="busy===row.id"
              @click="redownload(row)"
            >{{ tr('下载', 'Download') }}</el-button>
            <el-button v-if="['queued','running','packaging'].includes(row.status)" size="small" :loading="busy===row.id" @click="cancelJob(row)">{{tr('取消','Cancel')}}</el-button>
            <el-button v-if="['failed','expired','cancelled'].includes(row.status)" type="primary" size="small" :loading="busy===row.id" @click="retry(row)">{{tr('重新获取','Request again')}}</el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-pagination v-model:current-page="page" :page-size="20" :total="total" layout="prev,pager,next" @current-change="loadDownloads" style="margin-top:16px" />
    </el-card>
  </div>
</template>
<script>
import {tr} from '@/locales';
import {state} from '@/stores/state';
import {api,requestKey} from '@/api/client';
import {download} from '@/api/downloads';
import {refreshMe} from '@/stores/session';
import {statusText} from '@/locales/statuses';
import {errorText} from '@/locales/errors';
import {dateText,sizeText} from '@/utils/format';
export default {
  name:'MyDownloadsView',setup(){return {tr,state,statusText,errorText,dateText,sizeText};},
  data(){return {loading:false,downloads:[],page:1,total:0,busy:null,timer:null,disposed:false,loadTicket:0};},
  mounted(){this.loadDownloads();},beforeUnmount(){this.disposed=true;clearTimeout(this.timer);},
  methods:{
    async loadDownloads(silent=false){
      silent = silent === true;
      clearTimeout(this.timer);
      const ticket=++this.loadTicket;
      if(!silent)this.loading=true;
      try{
        const result=await api('/jobs?page='+this.page);
        if(this.disposed||ticket!==this.loadTicket)return;
        const existing=new Map(this.downloads.map(row=>[row.id,row]));
        this.downloads=result.items.map(row=>{
          const old=existing.get(row.id);
          if(!old)return row;
          for(const [key,value] of Object.entries(row))if(JSON.stringify(old[key])!==JSON.stringify(value))old[key]=value;
          return old;
        });
        this.total=result.total;
        if(!silent)await refreshMe();
      }catch(e){if(!this.disposed&&ticket===this.loadTicket&&!silent)this.$message.error(e.message);}
      finally{
        if(ticket===this.loadTicket){
          this.loading=false;
          if(!this.disposed&&this.downloads.some(row=>['queued','running','packaging','cancel_requested'].includes(row.status)))
            this.timer=setTimeout(()=>this.loadDownloads(true),5000);
        }
      }
    },
    async redownload(row){this.busy=row.id;try{await download(row.id);}catch(e){this.$message.error(e.message);}finally{this.busy=null;}},
    async cancelJob(row){this.busy=row.id;try{await api('/jobs/'+row.id+'/cancel',{method:'POST',body:{}});await this.loadDownloads();}catch(e){this.$message.error(e.message);}finally{this.busy=null;}},
    async retry(row){this.busy=row.id;try{await api('/jobs',{method:'POST',headers:{'Idempotency-Key':requestKey()},body:{basin_code:row.basin_code,dataset_version_id:row.dataset_version_id,...(row.application_id?{application_id:row.application_id}:{}),terms_accepted:true,package_mode:'full'}});await this.loadDownloads();}catch(e){this.$message.error(e.message);}finally{this.busy=null;}}
  }
};
</script>
<style scoped>
.downloads-container {
  max-width: 1200px;
  min-width: 0;
  margin: 0 auto;
  padding: 20px;
}
.downloads-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.ids-text {
  font-family: Consolas, Monaco, monospace;
  font-size: 12px;
  color: #606266;
}
</style>
