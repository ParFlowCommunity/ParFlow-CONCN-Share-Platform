<template><nav class="account-tabs" :aria-label="tr('个人中心导航','Account navigation')"><router-link v-for="item in items" :key="item[0]" :to="item[0]">{{tr(item[1],item[2])}}</router-link></nav></template>
<script setup>
import {tr} from '../locales';
const items=[['/profile','基本信息','Profile'],['/downloads','我的下载','My downloads'],['/applications','我的申请','My applications'],['/notifications','通知','Notifications']];
</script>
<style scoped>.account-tabs{display:flex;gap:26px;border-bottom:1px solid #e4e7ed;background:white;padding:0 24px;overflow:auto}.account-tabs a{padding:17px 0;text-decoration:none;color:#606266;white-space:nowrap;border-bottom:2px solid transparent}.account-tabs a.router-link-active{color:#2c6b9e;border-color:#2c6b9e}</style>
