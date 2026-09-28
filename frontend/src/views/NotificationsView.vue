<template><section class="notifications"><el-card shadow="never"><template #header><div class="notice-header"><span>{{tr('通知','Notifications')}} <el-badge v-if="unread" :value="unread"/></span><div><el-button @click="load">{{tr('刷新','Refresh')}}</el-button><el-button :disabled="!unread" :loading="busy" @click="readAll">{{tr('全部标为已读','Mark all read')}}</el-button></div></div></template>
<el-alert v-if="error" :title="error" type="error" :closable="false"/>
<el-empty v-if="!items.length" :description="tr('暂无通知','No notifications')"/>
<article v-for="item in items" :key="item.event_key" :class="{unread:!item.read_at}"><div><span v-if="!item.read_at" class="dot"/><b>{{titles[item.kind]?.()}}</b><time>{{dateText(item.created_at)}}</time></div><p>{{tr('流域编号','Basin code')}}：{{item.basin_code}}</p><p v-if="item.comment">{{item.comment}}</p><router-link :to="item.link">{{tr('查看详情','View details')}}</router-link></article>
<el-pagination v-model:current-page="page" :page-size="20" :total="total" layout="prev,pager,next" @current-change="load"/>
</el-card></section></template>
<script setup>
import {ref,onMounted} from 'vue';import {api} from '../api/client';import {tr} from '../locales';import {dateText} from '../utils/format';
const items=ref([]),unread=ref(0),total=ref(0),page=ref(1),busy=ref(false),error=ref('');
const titles={approve:()=>tr('申请已通过','Application approved'),reject:()=>tr('申请未通过','Application rejected'),revoke:()=>tr('下载授权已撤销','Authorization revoked'),ready:()=>tr('数据包已准备完成','Package ready')};
async function load(){try{const r=await api('/notifications?page='+page.value);items.value=r.items;unread.value=r.unread;total.value=r.total;error.value='';}catch(e){error.value=e.message;}}
async function readAll(){busy.value=true;try{await api('/notifications/read',{method:'POST',body:{}});await load();}catch(e){error.value=e.message;}finally{busy.value=false;}}
onMounted(load);
</script>
<style scoped>.notifications{padding:24px}.notice-header{display:flex;justify-content:space-between;gap:15px;flex-wrap:wrap}article{padding:20px;border-bottom:1px solid #e5e7eb}article.unread{background:#f5f9ff}article time{font-size:12px;color:#909399;margin-left:20px}article p{white-space:pre-wrap;color:#606266}article a{color:#2c6b9e}.dot{display:inline-block;width:7px;height:7px;background:#409eff;border-radius:50%;margin-right:8px}</style>
