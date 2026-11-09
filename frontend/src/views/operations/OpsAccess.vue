<script setup>
import { onMounted, ref } from 'vue'
import { getRoleOptions, getRoleUsers, updateUserRoles } from '@/api/operations'
import { useUserStore } from '@/stores/user'

const userStore = useUserStore()
const users = ref([])
const options = ref([])
const selected = ref(null)
const roleIds = ref([])
const reason = ref('')
const loading = ref(false)
const busy = ref(false)
const error = ref('')
const notice = ref('')

async function load() {
  loading.value = true
  error.value = ''
  try {
    const [userData, optionData] = await Promise.all([getRoleUsers(), getRoleOptions()])
    users.value = userData
    options.value = optionData
    if (selected.value) {
      const current = users.value.find((row) => row.id === selected.value.id)
      if (current) select(current)
    }
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
}
function select(row) {
  selected.value = row
  roleIds.value = row.roles.map((role) => Number(role.id))
  reason.value = ''
  notice.value = ''
}
async function save() {
  if (busy.value || !selected.value || !reason.value.trim()) return
  busy.value = true
  error.value = ''
  notice.value = ''
  try {
    await updateUserRoles(selected.value, roleIds.value, reason.value.trim())
    await load()
    notice.value = '角色已更新，目标用户的既有会话已撤销。'
  } catch (e) {
    error.value = e.response ? e.message : `${e.message}；结果待确认，请刷新或原键重试。`
  } finally {
    busy.value = false
  }
}
onMounted(load)
</script>

<template>
  <section class="ops-access">
    <h1>用户与角色</h1><p>角色变更需要原因和当前会话版本；不能修改自己的角色。手机号、地址和凭据不在此显示。</p>
    <p v-if="error" role="alert">{{ error }}</p><p v-if="notice" role="status">{{ notice }}</p><p v-if="loading">正在读取用户…</p>
    <div class="ops-access__layout">
      <div class="ops-access__users"><button v-for="row in users" :key="row.id" :aria-pressed="selected?.id === row.id" @click="select(row)"><strong>{{ row.username }}</strong><span>{{ row.roles.map((role) => role.name).join('、') || '无业务角色' }}</span></button></div>
      <form v-if="selected" class="ops-access__editor" @submit.prevent="save">
        <h2>{{ selected.username }}</h2><p>当前会话版本 {{ selected.expected_version }}</p>
        <fieldset><legend>业务角色</legend><label v-for="role in options" :key="role.id"><input v-model="roleIds" type="checkbox" :value="Number(role.id)"> {{ role.name }}<small>{{ role.permissions.join('、') || '无额外权限' }}</small></label></fieldset>
        <label>变更原因<textarea v-model="reason" maxlength="200" required /></label>
        <button :disabled="busy || !reason.trim() || selected.id === userStore.profile.id">{{ selected.id === userStore.profile.id ? '不能修改自己的角色' : '保存角色变更' }}</button>
      </form>
      <p v-else>请选择用户。</p>
    </div>
  </section>
</template>

<style scoped>
.ops-access__layout {
  display: grid;
  grid-template-columns: minmax(240px, 1fr) minmax(320px, 2fr);
  gap: 20px;
  margin-top: 20px;
}
.ops-access__users {
  display: grid;
  align-content: start;
  gap: 8px;
}
.ops-access__users button,
.ops-access__editor {
  padding: 12px;
  border: 1px solid var(--mall-border);
  border-radius: 8px;
  text-align: left;
  background: #fff;
}
.ops-access__users button {
  display: grid;
  gap: 5px;
  min-height: 44px;
}
.ops-access__users button[aria-pressed='true'] {
  border-color: var(--mall-color-primary);
}
.ops-access__editor {
  display: grid;
  gap: 14px;
}
.ops-access__editor label {
  display: grid;
  gap: 5px;
}
.ops-access__editor textarea,
.ops-access__editor button {
  min-height: 44px;
  font: inherit;
}
.ops-access__editor small {
  color: var(--mall-text-secondary);
}
@media (max-width: 700px) {
  .ops-access__layout {
    grid-template-columns: 1fr;
  }
}
</style>
