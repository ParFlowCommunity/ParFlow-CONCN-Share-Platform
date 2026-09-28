import { createRouter,createWebHistory } from 'vue-router';
import { initialize } from '../stores/session';
import { state } from '../stores/state';
const routes=[
  {path:'/',redirect:'/data/view'},
  {path:'/home',component:()=>import('../views/HomePage.vue')},
  {path:'/data/view',component:()=>import('../views/DataView.vue')},
  {path:'/help',component:()=>import('../views/HelpPage.vue')},
  {path:'/notice',component:()=>import('../views/NoticePage.vue')},
  {path:'/login',component:()=>import('../views/Login.vue')},
  {path:'/member',component:()=>import('../views/AccountLayout.vue'),meta:{auth:true},children:[
    {path:'/profile',component:()=>import('../views/UserCenter.vue')},
    {path:'/downloads',component:()=>import('../views/MyDownloads.vue')},
    {path:'/applications',component:()=>import('../views/ApplicationsView.vue')},
    {path:'/notifications',component:()=>import('../views/NotificationsView.vue')},
  ]},
  {path:'/admin',component:()=>import('../views/AdminView.vue'),meta:{auth:true,admin:true}},
  {path:'/explore',redirect:to=>({path:'/data/view',query:to.query})},
  {path:'/account',redirect:to=>({path:'/login',query:to.query})},
  {path:'/tasks',redirect:'/downloads'},
  {path:'/notices',redirect:'/notice'},
  {path:'/:pathMatch(.*)*',redirect:'/'}
];
const router=createRouter({history:createWebHistory(),routes});
router.beforeEach(async to=>{
  await initialize();
  if(to.meta.auth&&!state.user) return {path:'/login',query:{next:to.fullPath}};
  if(to.meta.admin&&state.user?.role!=='admin') return '/data/view';
});
export default router;
