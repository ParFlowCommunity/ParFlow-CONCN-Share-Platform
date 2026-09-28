<template>
  <el-dialog :model-value="modelValue" :title="mode==='confirm'?tr('填写下载用途','Download purpose'):tr('下载数据','Download data')" :width="mode==='apply'?'560px':'460px'" style="max-width:94vw" @update:model-value="$emit('update:modelValue',$event)" :close-on-click-modal="!busy" :close-on-press-escape="!busy" :show-close="!busy">
    <p v-if="mode!=='confirm'" class="basin-summary">{{tr('流域编号','Basin code')}}：<b>{{basin?.id}}</b> · {{tr('第 '+basin?.level/2+' 级流域','Level '+basin?.level/2)}}</p>
    <p v-if="loading">{{tr('正在检查下载资格…','Checking access…')}}</p>
    <el-alert v-if="error" :title="error" type="error" :closable="false"/>
    <template v-if="!loading && mode==='confirm'">
      <p class="download-summary">{{tr('本次下载流域（1个）：','Basin to download (1): ')}}<b>{{basin?.id}}</b></p>
      <form id="download-purpose" class="purpose-form" @submit.prevent="submitJob">
        <el-input v-model="downloadForm.affiliation" maxlength="100" show-word-limit :aria-label="tr('科研单位','Affiliation')" :placeholder="tr('请填写科研单位，如：XX大学、XX研究所（必填）','Research affiliation, e.g. university or institute (required)')"/>
        <el-input v-model="downloadForm.purpose" type="textarea" :rows="3" maxlength="200" show-word-limit :aria-label="tr('下载用途','Download purpose')" :placeholder="tr('请填写下载用途，如：科研分析、毕业设计、课程教学、项目开发等（必填）','Purpose: research, thesis, teaching or project development (required)')"/>
      </form>
      <el-checkbox v-model="accepted" class="terms-check">{{tr('我已阅读并同意数据使用条款','I accept the data usage terms')}}</el-checkbox>
      <details class="compact-terms"><summary>{{tr('查看条款','View terms')}}</summary><div class="terms">{{terms}}</div></details>
    </template>
    <form v-if="!loading && mode==='apply'" id="basin-application" @submit.prevent="submitApplication">
      <p>{{tr('该流域需要审核，请填写申请。每份申请对应一个流域。','Approval is required. Complete this application for one basin.')}}</p>
      <label>{{tr('姓名','Name')}}<input v-model="form.applicant_name" required maxlength="100"/></label>
      <label>{{tr('单位或身份说明','Affiliation')}}<input v-model="form.affiliation" required maxlength="255"/></label>
      <label>{{tr('联系邮箱','Email')}}<input :value="state.user?.email" disabled/></label>
      <label>{{tr('使用目的（至少10字）','Purpose (at least 10 characters)')}}<textarea v-model="form.purpose" required minlength="10" maxlength="5000" rows="3"/></label>
      <label>{{tr('申请原因（至少10字）','Reason (at least 10 characters)')}}<textarea v-model="form.large_basin_reason" required minlength="10" maxlength="5000" rows="3"/></label>
      <label>{{tr('项目链接（选填）','Project URL (optional)')}}<input v-model="form.project_url" type="url" maxlength="2000"/></label>
      <div class="terms">{{terms}}</div>
      <el-checkbox v-model="accepted">{{tr('我已阅读并同意数据使用条款','I accept the data usage terms')}}</el-checkbox>
    </form>
    <el-result v-if="mode==='submitted'" icon="success" :title="tr('申请已提交','Application submitted')" :sub-title="tr('审核结果可在“我的申请”和“通知”中查看。','Check My applications and Notifications for the decision.')"/>
    <div v-if="mode==='job'" class="job-state">
      <h3>{{statusText(job?.status)}}</h3>
      <p v-if="active">{{tr('可以关闭窗口，任务会继续处理。','You can close this window. Processing will continue.')}}</p>
      <p v-if="job?.error_code">{{errorText(job.error_code)}}</p>
      <el-button v-if="job?.status==='succeeded'" type="primary" :loading="busy" @click="save">{{tr('保存 ZIP','Save ZIP')}}</el-button>
      <el-button v-if="active && job?.status!=='cancel_requested'" :loading="busy" @click="cancel">{{tr('取消任务','Cancel task')}}</el-button>
    </div>
    <template #footer>
      <el-button :disabled="busy" @click="$emit('update:modelValue',false)">{{mode==='confirm'?tr('取消','Cancel'):tr('关闭','Close')}}</el-button>
      <el-button v-if="mode==='confirm' && !loading" type="primary" :disabled="!accepted || !downloadForm.affiliation.trim() || !downloadForm.purpose.trim()" :loading="busy" native-type="submit" form="download-purpose">{{tr('下载','Download')}}</el-button>
      <el-button v-if="mode==='apply' && !loading" type="primary" native-type="submit" form="basin-application" :disabled="!accepted" :loading="busy">{{tr('提交申请','Submit application')}}</el-button>
      <el-button v-if="mode==='submitted'" type="primary" @click="go('/applications')">{{tr('我的申请','My applications')}}</el-button>
      <el-button v-if="mode==='job'" @click="go('/downloads')">{{tr('我的下载','My downloads')}}</el-button>
      <el-button v-if="mode==='error'" @click="initialize">{{tr('重试','Retry')}}</el-button>
    </template>
  </el-dialog>
</template>
<script setup>
import {ref,reactive,computed,watch,onBeforeUnmount} from 'vue';
import {useRouter} from 'vue-router';
import {tr} from '../locales';
import {state} from '../stores/state';
import {refreshMe} from '../stores/session';
import {api,requestKey} from '../api/client';
import {download} from '../api/downloads';
import {statusText} from '../locales/statuses';
import {errorText} from '../locales/errors';
const props=defineProps({modelValue:Boolean,basin:Object,version:Number});
const emit=defineEmits(['update:modelValue']);
const router=useRouter(), loading=ref(false),busy=ref(false),error=ref(''),mode=ref('confirm'),accepted=ref(false),terms=ref(''),applicationId=ref(null),job=ref(null);
const downloadForm=reactive({affiliation:'',purpose:''});
watch(downloadForm,()=>{key=requestKey();});
const form=reactive({applicant_name:'',affiliation:'',purpose:'',large_basin_reason:'',project_url:''});
const active=computed(()=>['queued','running','packaging','cancel_requested'].includes(job.value?.status));
let timer,serial=0,key=requestKey();
watch(form,()=>{key=requestKey();});
watch(()=>props.modelValue,open=>{clearTimeout(timer);serial++;if(open)initialize();});
onBeforeUnmount(()=>{serial++;clearTimeout(timer);});
async function initialize(){
  const ticket=++serial;loading.value=true;error.value='';mode.value='confirm';accepted.value=false;applicationId.value=null;job.value=null;key=requestKey();
  try{
    await refreshMe();
    const [datasets,eligibility]=await Promise.all([api('/datasets'),api(`/watersheds/${props.basin.id}/download-access?version=${props.version}`)]);
    if(ticket!==serial)return;
    const version=datasets.items.find(v=>v.id===props.version);
    terms.value=version?.[state.user?.preferred_locale==='en'?'license_text_en':'license_text_zh']||'';
    applicationId.value=eligibility.application_id;
    mode.value=eligibility.direct||eligibility.application_id?'confirm':'apply';
  }catch(e){if(ticket===serial){error.value=e.message;mode.value='error';}}
  finally{if(ticket===serial)loading.value=false;}
}
function body(){return {basin_code:props.basin.id,dataset_version_id:props.version,terms_accepted:accepted.value};}
async function submitJob(){
  if(busy.value||!accepted.value||!downloadForm.affiliation.trim()||!downloadForm.purpose.trim())return;busy.value=true;error.value='';
  try{const r=await api('/jobs',{method:'POST',headers:{'Idempotency-Key':key},body:{...body(),download_affiliation:downloadForm.affiliation.trim(),download_purpose:downloadForm.purpose.trim(),...(applicationId.value?{application_id:applicationId.value}:{})}});job.value={id:r.id,status:'queued'};mode.value='job';key=requestKey();if(props.modelValue)await poll();}
  catch(e){error.value=e.message;if(['SMALL_BASIN_QUOTA_EXCEEDED','APPROVAL_REQUIRED'].includes(e.code)){mode.value='apply';applicationId.value=null;key=requestKey();}}
  finally{busy.value=false;}
}
async function submitApplication(){
  if(busy.value||!accepted.value)return;busy.value=true;error.value='';
  try{await api('/applications',{method:'POST',headers:{'Idempotency-Key':key},body:{...body(),...form}});mode.value='submitted';key=requestKey();}catch(e){error.value=e.message;}finally{busy.value=false;}
}
async function poll(){
  clearTimeout(timer);const ticket=serial;
  try{const r=await api('/jobs/'+job.value.id);if(ticket!==serial||!props.modelValue)return;job.value=r;error.value='';}
  catch(e){if(ticket!==serial)return;error.value=e.message;}
  if(ticket===serial&&props.modelValue&&active.value)timer=setTimeout(poll,3000);
}
async function save(){busy.value=true;try{await download(job.value.id);}catch(e){error.value=e.message;}finally{busy.value=false;}}
async function cancel(){busy.value=true;try{await api('/jobs/'+job.value.id+'/cancel',{method:'POST',body:{}});await poll();}catch(e){error.value=e.message;}finally{busy.value=false;}}
function go(path){emit('update:modelValue',false);router.push(path);}
</script>
<style scoped>
.basin-summary{background:#f3f7fb;padding:14px;border-radius:5px;overflow-wrap:anywhere}.terms{white-space:pre-wrap;max-height:120px;overflow:auto;background:#f7f8fa;padding:12px;margin:12px 0;font-size:13px}label{display:block;margin:12px 0}input:not(.el-input__inner),textarea:not(.el-textarea__inner){display:block;width:100%;box-sizing:border-box;border:1px solid #dcdfe6;border-radius:4px;padding:9px;margin-top:6px;font:inherit}input:disabled{background:#f5f7fa}.job-state{text-align:center;padding:25px 0}
.download-summary{font-size:13px;margin:0 0 12px;color:#606266}.download-summary b{font-weight:500}.purpose-form{display:flex;flex-direction:column;gap:10px}.terms-check{margin-top:8px}.compact-terms{font-size:12px;color:#909399}.compact-terms summary{cursor:pointer}.purpose-form :deep(.el-input__inner){font-size:12px}.purpose-form :deep(.el-textarea__inner){font-size:12px;padding-bottom:22px}
</style>
