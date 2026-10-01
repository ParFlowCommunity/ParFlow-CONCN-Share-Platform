<template>
  <el-config-provider :locale="elementLocale"><div id="app">
    <el-container>
      <el-header height="80px" class="header">
        <div class="header-left">
          <div class="logo">
            <img src="/new_logo.jpeg" alt="ParFlow CONCN Share Platform" style="height: 60px; vertical-align: middle;" />
          </div>
        </div>

        <div class="header-center">
          <el-menu
            :default-active="activeMenu"
            mode="horizontal"
            background-color="#ffffff"
            text-color="#333333"
            active-text-color="#2c6b9e"
            @select="handleMenuSelect"
            style="border-bottom: none;"
          >
            <el-menu-item index="/home">{{ tr('网站主页', 'Home') }}</el-menu-item>
            <el-sub-menu index="/data">
              <template #title>{{tr('流域数据','Basin data')}}</template>
              <el-menu-item index="/data/view">{{tr('流域数据','Basin data')}}</el-menu-item>
            </el-sub-menu>
            <el-menu-item index="/help">{{ tr('使用说明', 'Help') }}</el-menu-item>
            <el-menu-item index="/notice">{{ tr('公告', 'Notices') }}</el-menu-item>
          </el-menu>
        </div>

        <div class="header-right">
          <el-dropdown v-if="isLoggedIn" trigger="click" @command="accountCommand">
            <el-button class="account-trigger"><span class="account-name">{{ username }}</span><span aria-hidden="true"> ▾</span></el-button>
            <template #dropdown><el-dropdown-menu>
              <el-dropdown-item command="/downloads">{{tr('我的下载','My downloads')}}</el-dropdown-item>
              <el-dropdown-item command="/profile">{{tr('用户中心','Account')}}</el-dropdown-item>
              <el-dropdown-item command="/applications">{{tr('我的申请','My applications')}}</el-dropdown-item>
              <el-dropdown-item command="/notifications">{{tr('通知','Notifications')}}</el-dropdown-item>
              <template v-if="state.user?.role==='admin'">
                <el-dropdown-item divided command="/admin?tab=users">{{tr('用户管理','Users')}}</el-dropdown-item>
                <el-dropdown-item command="/admin?tab=jobs">{{tr('下载记录','Download records')}}</el-dropdown-item>
                <el-dropdown-item command="/admin?tab=reviews">{{tr('申请审批','Application reviews')}}</el-dropdown-item>
                <el-dropdown-item command="/admin?tab=config">{{tr('平台设置','Settings')}}</el-dropdown-item>
                <el-dropdown-item command="/admin?tab=content">{{tr('内容管理','Content')}}</el-dropdown-item>
              </template>
              <el-dropdown-item divided command="logout">{{tr('退出登录','Sign out')}}</el-dropdown-item>
            </el-dropdown-menu></template>
          </el-dropdown>
          <el-button v-else type="primary" @click="goToLogin">{{tr('登录/注册','Sign in / Register')}}</el-button>
          <el-button type="primary" @click="switchLanguage">{{locale==='en'?'中文':'English'}}</el-button>
        </div>
      </el-header>

      <el-main class="main-content">
        <el-alert v-if="state.config?.maintenance_mode" :title="tr('平台维护中，暂不接受新请求。','Maintenance: new requests are paused.')" type="warning" :closable="false" />
        <router-view v-slot="{Component}">
          <KeepAlive include="DataView" :max="1"><component :is="Component"/></KeepAlive>
        </router-view>
      </el-main>
    </el-container>
  </div>
</el-config-provider></template>
<script>
import { computed,watch } from 'vue';
import zhCn from 'element-plus/es/locale/lang/zh-cn';
import en from 'element-plus/es/locale/lang/en';
import { ElMessage } from 'element-plus';
import { locale,tr } from './locales';
import { state } from './stores/state';
import { api } from './api/client';
export default {
  name:'App',
  setup(){
    watch(()=>state.notice,message=>{if(message) ElMessage({message,type:state.noticeKind==='error'?'error':'info'});});
    return {state,locale,tr,elementLocale:computed(()=>locale.value==='en'?en:zhCn)};
  },
  computed:{activeMenu(){return this.$route.path;},isLoggedIn(){return !!state.user;},username(){return state.user?.username || '';}},
  methods:{
    accountCommand(command){if(command==='logout')this.handleLogout();else this.$router.push(command);},
    handleMenuSelect(path){this.$router.push(path);},
    switchLanguage(){locale.value=locale.value==='en'?'zh-CN':'en';},
    goToLogin(){this.$router.push('/login');},
    goToUserCenter(){this.$router.push('/profile');},
    goToDownloads(){this.$router.push('/downloads');},
    async handleLogout(){try{await api('/logout',{method:'POST',body:{}});state.user=null;this.$router.push('/login');}catch(e){this.$message.error(e.message);}}
  }
};
</script>
<style>
/* 全局样式：确保整个页面占满视口 */
html, body {
  height: 100%;
  margin: 0;
  padding: 0;
}
#app {
  height: 100%;
  font-family: 'Helvetica Neue', Arial, sans-serif;
}
.el-container {
  height: 100%;
  flex-direction: column;
}
</style>

<style scoped>
* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

.header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  background-color: #ffffff;
  border-bottom: 1px solid #e6e6e6;
  padding: 0 0;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
  flex-shrink: 0;
  width: 100%;
  height: 80px;
}
.header-left {
  display: flex;
  align-items: center;
  min-width: 160px;
  padding-left: 20px;
}
.logo {
  display: flex;
  align-items: center;
}
.header-center {
  flex: 2;
  display: flex;
  justify-content: center;
}
.header-center .el-menu {
  width: 100%;
  max-width: 800px;
  display: flex;
  justify-content: space-around;
}
.header-right {
  display: flex;
  align-items: center;
  gap: 12px;
  min-width: 180px;
  justify-content: flex-end;
  padding-right: 20px;
}
.header-right .username {
  font-size: 16px;
  font-weight: 500;
  color: #333;
  margin-right: 4px;
}
.main-content {
  background-color: #f5f7fa;
  padding: 0;
  flex: 1;
  width: 100%;
  /* 关键：让 main-content 可收缩，防止溢出 */
  min-height: 0;
}

:deep(.el-menu-item),
:deep(.el-sub-menu .el-sub-menu__title) {
  font-size: 20px !important;
  font-weight: bold !important;
}
:deep(.header-right .el-button) {
  font-size: 20px !important;
  font-weight: bold !important;
  padding: 14px 28px !important;
  height: auto !important;
}
/* 我的下载/退出按钮缩小,不与用户中心等主按钮同样大小 */
:deep(.header-right .el-button.header-small-btn) {
  font-size: 14px !important;
  font-weight: normal !important;
  padding: 6px 12px !important;
}
</style>

<style scoped>
/* Retain the desktop header; prevent overflow inside narrow browser panels. */
@media (max-width: 900px) {
  .header {height:auto !important;min-height:80px;flex-wrap:wrap;padding:10px 0;gap:8px;}
  .header-left {min-width:0;}
  .header-right {min-width:0;gap:8px;}
  .header-center {order:3;flex-basis:100%;}
  :deep(.header-right .el-button) {font-size:14px !important;padding:8px 12px !important;}
}
@media (max-width: 500px) {
  .header-left {padding-left:12px;}
  .header-right {padding-right:12px;}
  .logo img {max-width:150px;object-fit:contain;}
}
</style>
<style scoped>
.account-name{max-width:140px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;}
.account-trigger{color:#2c6b9e;}
</style>
