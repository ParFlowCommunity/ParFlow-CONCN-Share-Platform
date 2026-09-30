<template>
  <div class="user-center-container">
    <!-- 基本信息 -->
    <el-card shadow="never" class="info-summary-card">
      <template #header>
        <span>{{ tr('基本信息', 'Account information') }}</span>
      </template>
      <div class="info-summary">
        <div class="summary-item">
          <span class="label">{{ tr('用户名', 'Username') }}</span>
          <span class="value">{{ profile.username || '—' }}</span>
        </div>
        <div class="summary-item">
          <span class="label">{{ tr('邮箱', 'Email') }}</span>
          <span class="value">{{ profile.email || '—' }}</span>
        </div>
        <div class="summary-item">
          <span class="label">{{ tr('注册时间', 'Registered') }}</span>
          <span class="value">{{ dateText(profile.created_at) }}</span>
        </div>
      </div>
      <div style="margin:16px 8px 0;color:#606266;font-size:14px">
        <el-tag size="small" style="margin-left:16px">{{profile.email_verified_at?tr('邮箱已验证','Email verified'):tr('邮箱未验证','Email unverified')}}</el-tag>
        <el-button v-if="!profile.email_verified_at" link type="primary" :loading="verifyLoading" @click="verifyEmail">{{tr('发送验证邮件','Verify email')}}</el-button>
      </div>
    </el-card>

    <el-row :gutter="20" class="settings-row">
      <!-- 修改密码 -->
      <el-col :xs="24" :md="8">
        <el-card shadow="never" class="setting-card">
          <template #header>
            <span>{{ tr('修改密码', 'Change password') }}</span>
          </template>
          <el-form
            ref="passwordFormRef"
            :model="passwordForm"
            :rules="passwordRules"
            label-width="90px"
          >
            <el-form-item :label="tr('原密码', 'Current password')" prop="old_password">
              <el-input v-model="passwordForm.old_password" type="password" :placeholder="tr('请输入原密码', 'Enter current password')" show-password />
            </el-form-item>
            <el-form-item :label="tr('新密码', 'New password')" prop="new_password">
              <el-input v-model="passwordForm.new_password" type="password" :placeholder="tr('8-128位，须含字母和数字', '8–128 characters, letters and numbers')" show-password />
            </el-form-item>
            <el-form-item :label="tr('确认新密码', 'Confirm password')" prop="confirm_password">
              <el-input v-model="passwordForm.confirm_password" type="password" :placeholder="tr('再次输入新密码', 'Confirm new password')" show-password />
            </el-form-item>
            <el-form-item>
              <el-button type="primary" :loading="passwordLoading" @click="handleChangePassword" style="width:100%;">{{ tr('确认修改', 'Save changes') }}</el-button>
            </el-form-item>
          </el-form>
        </el-card>
      </el-col>

      <!-- 修改邮箱 -->
      <el-col :xs="24" :md="8">
        <el-card shadow="never" class="setting-card">
          <template #header>
            <span>{{ tr('修改邮箱', 'Change email') }}</span>
          </template>
          <el-form
            ref="emailFormRef"
            :model="emailForm"
            :rules="emailRules"
            label-width="90px"
          >
            <el-form-item :label="tr('当前邮箱', 'Current email')">
              <el-input :model-value="profile.email || '—'" disabled />
            </el-form-item>
            <el-form-item :label="tr('新邮箱', 'New email')" prop="email">
              <el-input v-model="emailForm.email" :placeholder="tr('请输入新邮箱', 'Enter new email')" />
            </el-form-item>
            <el-form-item :label="tr('当前密码', 'Current password')" prop="password">
              <el-input v-model="emailForm.password" type="password" :placeholder="tr('为安全起见需验证密码', 'Enter password to verify')" show-password />
            </el-form-item>
            <el-form-item>
              <el-button type="primary" :loading="emailLoading" @click="handleChangeEmail" style="width:100%;">{{ tr('确认修改', 'Save changes') }}</el-button>
            </el-form-item>
          </el-form>
        </el-card>
      </el-col>

      <!-- 修改用户名 -->
      <el-col :xs="24" :md="8">
        <el-card shadow="never" class="setting-card">
          <template #header>
            <span>{{ tr('修改用户名', 'Change username') }}</span>
          </template>
          <el-form
            ref="usernameFormRef"
            :model="usernameForm"
            :rules="usernameRules"
            label-width="90px"
          >
            <el-form-item :label="tr('当前用户名', 'Current username')">
              <el-input :model-value="profile.username || '—'" disabled />
            </el-form-item>
            <el-form-item :label="tr('新用户名', 'New username')" prop="username">
              <el-input v-model="usernameForm.username" :placeholder="tr('4-64位', '4–64 characters')" />
            </el-form-item>
            <el-form-item>
              <el-button type="primary" :loading="usernameLoading" @click="handleChangeUsername" style="width:100%;">{{ tr('确认修改', 'Save changes') }}</el-button>
            </el-form-item>
          </el-form>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>
<script>
import { tr } from '@/locales';
import { state } from '@/stores/state';
import { api } from '@/api/client';
import { refreshMe } from '@/stores/session';
import { dateText } from '@/utils/format';
export default {
  name:'UserCenterView',setup(){return {tr,dateText};},
  data(){return {passwordForm:{old_password:'',new_password:'',confirm_password:''},emailForm:{email:'',password:''},usernameForm:{username:''},passwordLoading:false,emailLoading:false,usernameLoading:false,verifyLoading:false};},
  computed:{
    profile(){return state.user||{};},
    passwordRules(){return {old_password:[{required:true,message:tr('请输入原密码','Enter current password'),trigger:'blur'}],new_password:[{validator:(_,v,cb)=>cb(v&&v.length>=8&&v.length<=128&&/[A-Za-z]/.test(v)&&/\d/.test(v)?undefined:new Error(tr('密码需包含字母数字且为8–128位','Use 8–128 characters, including letters and numbers'))),trigger:'blur'}],confirm_password:[{validator:(_,v,cb)=>cb(v&&v===this.passwordForm.new_password?undefined:new Error(tr('两次密码不一致','Passwords do not match'))),trigger:'blur'}]};},
    emailRules(){return {email:[{required:true,type:'email',message:tr('请输入有效邮箱','Enter valid email'),trigger:'blur'}],password:[{required:true,message:tr('请输入密码','Enter password'),trigger:'blur'}]};},
    usernameRules(){return {username:[{required:true,min:4,max:64,message:tr('用户名需要4–64位','Use 4–64 characters'),trigger:'blur'}]};}
  },
  mounted(){refreshMe().catch(e=>this.$message.error(e.message));},
  methods:{
    async handleChangePassword(){if(!await this.$refs.passwordFormRef.validate().catch(()=>false))return;this.passwordLoading=true;try{const {old_password,new_password}=this.passwordForm;await api('/me/password',{method:'PUT',body:{old_password,new_password}});state.user=null;this.$router.push('/login');this.$message.success(tr('密码已修改，请重新登录。','Password changed. Sign in again.'));}catch(e){this.$message.error(e.message);}finally{this.passwordLoading=false;}},
    async handleChangeEmail(){if(!await this.$refs.emailFormRef.validate().catch(()=>false))return;this.emailLoading=true;try{await api('/me/change-email',{method:'POST',body:this.emailForm});this.$message.success(tr('验证链接已发送到新邮箱，完成验证后才会变更。','A link was sent to the new email. Verify it to complete the change.'));this.emailForm={email:'',password:''};}catch(e){this.$message.error(e.message);}finally{this.emailLoading=false;}},
    async handleChangeUsername(){if(!await this.$refs.usernameFormRef.validate().catch(()=>false))return;this.usernameLoading=true;try{await api('/me/username',{method:'PUT',body:this.usernameForm});await refreshMe();this.usernameForm.username='';this.$message.success(tr('用户名已更新。','Username updated.'));}catch(e){this.$message.error(e.message);}finally{this.usernameLoading=false;}},
    async verifyEmail(){this.verifyLoading=true;try{await api('/me/verify-email',{method:'POST',body:{}});this.$message.success(tr('验证邮件已发送。','Verification email sent.'));}catch(e){this.$message.error(e.message);}finally{this.verifyLoading=false;}}
  }
};
</script>
<style scoped>
.user-center-container {
  max-width: 1100px;
  margin: 0 auto;
  padding: 20px;
}
.info-summary-card {
  margin-bottom: 20px;
}
.info-summary {
  display: flex;
  flex-wrap: wrap;
  gap: 40px;
  padding: 4px 8px;
}
.summary-item {
  display: flex;
  align-items: center;
}
.summary-item .label {
  color: #909399;
  font-size: 14px;
  margin-right: 10px;
}
.summary-item .value {
  color: #303133;
  font-size: 14px;
  font-weight: 500;
}
.settings-row {
  margin: 0 !important;
}
.setting-card {
  margin-bottom: 20px;
  height: 100%;
}
</style>
