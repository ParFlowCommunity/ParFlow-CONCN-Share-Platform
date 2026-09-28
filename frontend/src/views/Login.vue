<template>
  <div class="login-container">
    <div class="login-box">
      <div class="login-header">
        <img src="/new_logo.jpeg" alt="ParFlow CONCN Share Platform" class="logo-img" />
      </div>

      <el-tabs v-model="activeTab" @tab-click="handleTabClick">
        <el-tab-pane :label="tr('登录', 'Sign in')" name="login">
          <el-form
            ref="loginFormRef"
            :model="loginForm"
            :rules="loginRules"
            label-width="80px"
            @keyup.enter="handleLogin"
          >
            <el-form-item :label="tr('邮箱', 'Email')" prop="email">
              <el-input v-model="loginForm.email" :placeholder="tr('请输入邮箱', 'Enter your email')" type="email" autocomplete="username" />
            </el-form-item>
            <el-form-item :label="tr('密码', 'Password')" prop="password">
              <el-input v-model="loginForm.password" type="password" :placeholder="tr('请输入密码', 'Enter password')" show-password />
            </el-form-item>
            <el-form-item>
              <el-button type="primary" @click="handleLogin" :loading="loginLoading" style="width:100%;">{{ tr('登录', 'Sign in') }}</el-button>
            </el-form-item>
          </el-form>
          <div class="forgot-row">
            <a href="#" @click.prevent="openForgotDialog">{{ tr('忘记密码？', 'Forgot password?') }}</a>
          </div>
        </el-tab-pane>

        <el-tab-pane :label="tr('注册', 'Register')" name="register">
          <el-form
            ref="registerFormRef"
            :model="registerForm"
            :rules="registerRules"
            label-width="80px"
            @keyup.enter="handleRegister"
          >
            <el-form-item :label="tr('用户名', 'Username')" prop="username">
              <el-input v-model="registerForm.username" :placeholder="tr('请输入用户名（4-64位）', 'Username (4–64 characters)')" />
            </el-form-item>
            <el-form-item :label="tr('密码', 'Password')" prop="password">
              <el-input v-model="registerForm.password" type="password" :placeholder="tr('8-128位，须含字母和数字', '8–128 characters, letters and numbers')" show-password />
            </el-form-item>
            <el-form-item :label="tr('确认密码', 'Confirm password')" prop="confirmPassword">
              <el-input v-model="registerForm.confirmPassword" type="password" :placeholder="tr('请再次输入密码', 'Confirm password')" show-password />
            </el-form-item>
            <el-form-item :label="tr('邮箱', 'Email')" prop="email">
              <el-input v-model="registerForm.email" :placeholder="tr('请输入邮箱（必填）', 'Email (required)')" />
            </el-form-item>
            <el-form-item>
              <el-button type="primary" @click="handleRegister" :loading="registerLoading" style="width:100%;">{{ tr('注册', 'Register') }}</el-button>
            </el-form-item>
          </el-form>
        </el-tab-pane>
      </el-tabs>

      <div class="login-footer">
        <span v-if="activeTab === 'login'">{{tr('还没有账号？','No account yet?')}}<a href="#" @click.prevent="activeTab='register'">{{ tr('立即注册', 'Register now') }}</a></span>
        <span v-else>{{tr('已有账号？','Already registered?')}}<a href="#" @click.prevent="activeTab='login'">{{ tr('去登录', 'Sign in') }}</a></span>
      </div>
    </div>

    <el-dialog v-model="forgotDialogVisible" :title="tr('找回密码','Reset password')" width="400px" :close-on-click-modal="false">
      <el-form @submit.prevent="handleForgotPassword" label-width="80px">
        <el-form-item :label="tr('注册邮箱','Email')"><el-input v-model="forgotEmail" type="email" :placeholder="tr('请输入注册邮箱','Enter your email')" /></el-form-item>
        <el-form-item><el-button type="primary" :loading="forgotLoading" @click="handleForgotPassword">{{tr('发送重置链接','Send reset link')}}</el-button></el-form-item>
      </el-form><p>{{tr('如果邮箱符合条件，将收到操作链接。','If the email is eligible, a reset link will be sent.')}}</p>
    </el-dialog>
    <el-dialog v-model="emailDialogVisible" :title="tr('邮箱操作','Email action')" width="420px" :close-on-click-modal="false">
      <p>{{tr('验证或变更邮箱时直接点击确认；重置密码时请填写新密码。','For email verification or change, confirm directly. For a password reset, enter your new password.')}}</p>
      <el-input v-model="newPassword" type="password" show-password autocomplete="new-password" :placeholder="tr('新密码（仅重置密码时填写）','New password (password reset only)')" style="margin:16px 0" />
      <el-button type="primary" :loading="emailLoading" @click="completeEmailAction">{{tr('确认操作','Confirm')}}</el-button>
    </el-dialog>
  </div>
</template>
<script>
import { tr } from '@/locales';
import { state } from '@/stores/state';
import { api } from '@/api/client';
import { refreshMe } from '@/stores/session';
export default {
  name:'LoginView',setup(){return {tr};},
  data(){return {activeTab:'login',loginForm:{email:'',password:''},registerForm:{username:'',email:'',password:'',confirmPassword:''},loginLoading:false,registerLoading:false,forgotDialogVisible:false,forgotEmail:'',forgotLoading:false,emailToken:'',emailDialogVisible:false,emailLoading:false,newPassword:''};},
  computed:{
    loginRules(){return {email:[{required:true,type:'email',message:tr('请输入有效邮箱','Enter a valid email'),trigger:'blur'}],password:[{required:true,message:tr('请输入密码','Enter password'),trigger:'blur'}]};},
    registerRules(){return {username:[{required:true,min:4,max:64,message:tr('用户名需要4–64位','Use 4–64 characters'),trigger:'blur'}],email:this.loginRules.email,password:[{validator:(_,v,cb)=>cb(typeof v==='string'&&v.length>=8&&v.length<=128&&/[A-Za-z]/.test(v)&&/\d/.test(v)?undefined:new Error(tr('密码需要8–128位，包含字母和数字','Use 8–128 characters, including letters and numbers'))),trigger:'blur'}],confirmPassword:[{validator:(_,v,cb)=>cb(v&&v===this.registerForm.password?undefined:new Error(tr('两次密码不一致','Passwords do not match'))),trigger:'blur'}]};}
  },
  mounted(){if(this.$route.query.email_token){this.emailToken=String(this.$route.query.email_token);this.emailDialogVisible=true;const query={...this.$route.query};delete query.email_token;this.$router.replace({path:'/login',query});}else if(state.user)this.$router.replace('/profile');},
  methods:{
    handleTabClick(){this.$refs.loginFormRef?.clearValidate();this.$refs.registerFormRef?.clearValidate();},
    nextPage(){const next=this.$route.query.next;return typeof next==='string'&&next.startsWith('/')&&!next.startsWith('//')?next:'/data/view';},
    async handleLogin(){if(this.loginLoading||!await this.$refs.loginFormRef.validate().catch(()=>false))return;this.loginLoading=true;
      try{await api('/login',{method:'POST',body:this.loginForm});await refreshMe();this.$router.push(this.nextPage());}catch(e){this.$message.error(e.message);}finally{this.loginLoading=false;}},
    async handleRegister(){if(this.registerLoading||!await this.$refs.registerFormRef.validate().catch(()=>false))return;this.registerLoading=true;
      try{const {username,email,password}=this.registerForm;await api('/register',{method:'POST',body:{username,email,password}});this.activeTab='login';this.loginForm.email=email;this.loginForm.password='';this.registerForm.password='';this.registerForm.confirmPassword='';this.$message.success(tr('注册成功，请输入邮箱和密码登录。','Registration complete. Sign in with your email and password.'));}catch(e){this.$message.error(e.message);}finally{this.registerLoading=false;}},
    openForgotDialog(){this.forgotEmail=this.loginForm.email;this.forgotDialogVisible=true;},
    async handleForgotPassword(){this.forgotLoading=true;try{await api('/forgot-password',{method:'POST',body:{email:this.forgotEmail}});this.$message.success(tr('如果邮箱符合条件，将收到重置链接。','If eligible, a reset link will be sent.'));this.forgotDialogVisible=false;}catch(e){this.$message.error(e.message);}finally{this.forgotLoading=false;}},
    async completeEmailAction(){this.emailLoading=true;try{await api('/email-action',{method:'POST',body:{token:this.emailToken,...(this.newPassword?{new_password:this.newPassword}:{})}});state.user=null;this.emailToken='';this.newPassword='';this.emailDialogVisible=false;this.$message.success(tr('操作成功，请重新登录。','Done. Please sign in again.'));}catch(e){this.$message.error(e.message);}finally{this.emailLoading=false;}}
  }
};
</script>
<style scoped>
.login-container {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 100vh;
  background: #f0f2f5;
  padding: 0;
}
.login-box {
  width: 420px;
  background: #fff;
  border-radius: 8px;
  padding: 40px 35px 30px;
  box-shadow: 0 4px 12px rgba(0,0,0,0.1);
}
.login-header {
  text-align: center;
  margin-bottom: 30px;
}
.login-header .logo-img {
  height: 60px;
  vertical-align: middle;
}
.login-footer {
  text-align: center;
  margin-top: 20px;
  font-size: 14px;
  color: #909399;
}
.login-footer a {
  color: #2c6b9e;
  text-decoration: none;
}
.login-footer a:hover {
  text-decoration: underline;
}
.forgot-row {
  text-align: right;
  margin-top: -6px;
}
.forgot-row a {
  color: #909399;
  font-size: 13px;
  text-decoration: none;
}
.forgot-row a:hover {
  color: #2c6b9e;
  text-decoration: underline;
}
.reset-code-alert {
  margin-bottom: 8px;
}
.reset-code {
  font-family: Consolas, Monaco, monospace;
  font-size: 16px;
  letter-spacing: 1px;
}
.reset-code-tip {
  font-weight: normal;
  font-size: 12px;
}
.re-get-row {
  text-align: right;
  margin-bottom: 8px;
}
.re-get-row a {
  color: #2c6b9e;
  font-size: 13px;
  text-decoration: none;
}
.re-get-row a:hover {
  text-decoration: underline;
}
.reset-form {
  margin-top: 10px;
}
</style>
