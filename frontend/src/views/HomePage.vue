<template>
  <div style="text-align: center; padding: 60px 20px;">
    <h1>🏠 {{tr('网站主页','Home')}}</h1>
    <p style="color: #666; font-size: 18px; margin-top: 20px;">{{tr('欢迎来到流域数据分享平台，这里将展示平台介绍、优秀案例等内容。','Welcome to the basin data sharing platform. Platform introductions and case studies will be presented here.')}}</p>
  </div>
</template>

<script>
import {tr} from '@/locales';
export default {
  name: 'HomePage',setup(){return {tr};}
}
</script>
