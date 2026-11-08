<script setup>
import { computed, reactive } from 'vue'
import { ElButton, ElCheckbox, ElForm, ElFormItem, ElInput } from 'element-plus'
import 'element-plus/es/components/button/style/css'
import 'element-plus/es/components/checkbox/style/css'
import 'element-plus/es/components/form/style/css'
import 'element-plus/es/components/form-item/style/css'
import 'element-plus/es/components/input/style/css'

const props = defineProps({
  mode: { type: String, required: true },
  loading: { type: Boolean, default: false },
})
const emit = defineEmits(['submit'])
const isRegister = computed(() => props.mode === 'register')
const form = reactive({ identifier: '', password: '', accepted: false })

function submit() {
  if (isRegister.value && !form.accepted) return
  emit('submit', {
    identifier: form.identifier,
    username: form.identifier,
    password: form.password,
    accepted_terms_version: 'demo-v1',
  })
}
</script>

<template>
  <el-form class="auth-form" label-position="top" @submit.prevent="submit">
    <el-form-item
      :label="isRegister ? '用户名（3–30位字母、数字或下划线）' : '用户名或已验证手机号'"
    >
      <el-input
        v-model="form.identifier"
        name="identifier"
        autocomplete="username"
        required
        maxlength="150"
        placeholder="请输入账号"
      />
    </el-form-item>
    <el-form-item label="密码">
      <el-input
        v-model="form.password"
        name="password"
        type="password"
        show-password
        :autocomplete="isRegister ? 'new-password' : 'current-password'"
        required
        placeholder="请输入密码"
      />
    </el-form-item>
    <el-form-item v-if="isRegister">
      <el-checkbox v-model="form.accepted">我已阅读并同意演示版服务说明（demo-v1）</el-checkbox>
    </el-form-item>
    <el-button
      class="auth-form__submit"
      type="primary"
      native-type="submit"
      :loading="loading"
      :disabled="isRegister && !form.accepted"
    >
      {{ isRegister ? '注册并登录' : '登录' }}
    </el-button>
  </el-form>
</template>

<style scoped>
.auth-form__submit {
  width: 100%;
  min-height: 44px;
}

:deep(.el-input__inner) {
  font-size: 16px;
}
</style>
