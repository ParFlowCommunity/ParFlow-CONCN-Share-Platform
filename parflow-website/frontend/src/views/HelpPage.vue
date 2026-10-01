<template>
  <div style="text-align: center; padding: 60px 20px;">
    <h1>📖 {{tr('使用说明','Help')}}</h1>
    <p v-if="!items.length" style="color: #666; font-size: 18px; margin-top: 20px;">{{tr('这里将展示网站的使用指南和常见问题解答。','Usage guides and frequently asked questions will be shown here.')}}</p>
    <article v-for="item in items" :key="item.slug" style="max-width:900px;margin:30px auto;text-align:left;line-height:1.8;color:#606266"><h2 style="color:#303133;font-size:20px">{{text(item,'title')}}</h2><p style="white-space:pre-wrap">{{text(item,'body')}}</p></article>
  </div>
</template>

<script>
import {tr,text} from '@/locales';
import {api} from '@/api/client';
export default {setup(){return {tr,text};},data(){return {items:[]};},async mounted(){try{this.items=(await api('/content?kind=help')).items;}catch(e){this.$message.error(e.message);}}};
</script>
