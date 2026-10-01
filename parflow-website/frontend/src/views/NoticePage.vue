<template>
  <div style="text-align: center; padding: 60px 20px;">
    <h1>📢 {{tr('公告','Notices')}}</h1>
    <p v-if="!items.length" style="color: #666; font-size: 18px; margin-top: 20px;">{{tr('这里将展示平台的最新公告和动态信息。','Platform notices and updates will be shown here.')}}</p>
    <article v-for="item in items" :key="item.slug" style="max-width:900px;margin:30px auto;text-align:left;line-height:1.8;color:#606266"><h2 style="color:#303133;font-size:20px">{{text(item,'title')}}</h2><p style="white-space:pre-wrap">{{text(item,'body')}}</p></article>
  </div>
</template>

<script>
import {tr,text} from '@/locales';
import {api} from '@/api/client';
export default {setup(){return {tr,text};},data(){return {items:[]};},async mounted(){try{this.items=(await api('/content?kind=notice')).items;}catch(e){this.$message.error(e.message);}}};
</script>
