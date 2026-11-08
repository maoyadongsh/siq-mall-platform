<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import {
  ElAlert,
  ElButton,
  ElCard,
  ElCheckbox,
  ElForm,
  ElFormItem,
  ElInput,
  ElMessageBox,
  ElTag,
} from 'element-plus'
import 'element-plus/es/components/alert/style/css'
import 'element-plus/es/components/button/style/css'
import 'element-plus/es/components/card/style/css'
import 'element-plus/es/components/checkbox/style/css'
import 'element-plus/es/components/form/style/css'
import 'element-plus/es/components/form-item/style/css'
import 'element-plus/es/components/input/style/css'
import 'element-plus/es/components/message-box/style/css'
import 'element-plus/es/components/tag/style/css'

import {
  createAddress,
  deleteAddress,
  fetchAddresses,
  setDefaultAddress,
  updateAddress,
} from '@/api/addresses'
import { useUserStore } from '@/stores/user'

const router = useRouter()
const userStore = useUserStore()
const addresses = ref([])
const loading = ref(false)
const saving = ref(false)
const busyId = ref('')
const errorMessage = ref('')
const successMessage = ref('')
const editingId = ref('')
const formVersion = ref(1)
const showForm = ref(false)
const form = reactive({
  recipient: '',
  phone: '',
  province: '',
  city: '',
  district: '',
  region_code: '',
  detail: '',
  is_default: false,
})

const formValid = computed(() =>
  ['recipient', 'phone', 'province', 'city', 'district', 'region_code', 'detail'].every((field) =>
    form[field].trim(),
  ),
)

function resetForm() {
  editingId.value = ''
  formVersion.value = 1
  showForm.value = false
  Object.assign(form, {
    recipient: '',
    phone: '',
    province: '',
    city: '',
    district: '',
    region_code: '',
    detail: '',
    is_default: false,
  })
}

async function loadAddresses() {
  loading.value = true
  errorMessage.value = ''
  try {
    addresses.value = await fetchAddresses()
  } catch (error) {
    errorMessage.value = error?.message || '地址加载失败'
  } finally {
    loading.value = false
  }
}

function editAddress(address) {
  editingId.value = address.id
  formVersion.value = address.version
  Object.assign(form, {
    recipient: address.recipient,
    phone: address.phone,
    province: address.province,
    city: address.city,
    district: address.district,
    region_code: address.region_code,
    detail: address.detail,
    is_default: address.is_default,
  })
  showForm.value = true
  successMessage.value = ''
  errorMessage.value = ''
}

async function saveAddress() {
  if (!formValid.value) return
  saving.value = true
  errorMessage.value = ''
  successMessage.value = ''
  const payload = { ...form }
  try {
    if (editingId.value) {
      await updateAddress(editingId.value, { ...payload, expected_version: formVersion.value })
      successMessage.value = '地址已更新'
    } else {
      await createAddress(payload)
      successMessage.value = '地址已创建'
    }
    resetForm()
    await loadAddresses()
  } catch (error) {
    errorMessage.value = error?.message || '保存失败，请检查输入后重试'
  } finally {
    saving.value = false
  }
}

async function removeAddress(address) {
  try {
    await ElMessageBox.confirm(`确认删除“${address.recipient}”的这条地址吗？`, '删除地址', {
      type: 'warning',
      confirmButtonText: '删除',
      cancelButtonText: '取消',
    })
  } catch {
    return
  }
  busyId.value = address.id
  errorMessage.value = ''
  try {
    await deleteAddress(address.id, address.version)
    successMessage.value = '地址已删除'
    await loadAddresses()
  } catch (error) {
    errorMessage.value = error?.message || '删除失败，请刷新后重试'
  } finally {
    busyId.value = ''
  }
}

async function makeDefault(address) {
  busyId.value = address.id
  errorMessage.value = ''
  try {
    await setDefaultAddress(address.id)
    successMessage.value = '默认地址已更新'
    await loadAddresses()
  } catch (error) {
    errorMessage.value = error?.message || '默认地址设置失败'
  } finally {
    busyId.value = ''
  }
}

onMounted(() => {
  if (!userStore.isLoggedIn) {
    router.push({ name: 'login', query: { redirect: '/account/addresses' } })
    return
  }
  loadAddresses()
})
</script>

<template>
  <div class="address-page">
    <el-card shadow="never">
      <template #header>
        <div class="address-page__header">
          <div>
            <h1>地址管理</h1>
            <p>最多保存20条；平台地址能力未接入时可全程手填。</p>
          </div>
          <el-button :disabled="busyId !== ''" @click="showForm ? resetForm() : (showForm = true)">
            {{ showForm ? '取消编辑' : '新建地址' }}
          </el-button>
        </div>
      </template>

      <el-alert
        v-if="errorMessage"
        :title="errorMessage"
        type="error"
        :closable="false"
        show-icon
      />
      <el-alert
        v-if="successMessage"
        :title="successMessage"
        type="success"
        :closable="false"
        show-icon
      />

      <el-form
        v-if="showForm"
        class="address-form"
        label-position="top"
        @submit.prevent="saveAddress"
      >
        <div class="address-form__grid">
          <el-form-item label="收件人" required>
            <el-input v-model="form.recipient" maxlength="50" />
          </el-form-item>
          <el-form-item label="联系电话" required>
            <el-input v-model="form.phone" maxlength="20" />
          </el-form-item>
          <el-form-item label="省份" required>
            <el-input v-model="form.province" maxlength="50" />
          </el-form-item>
          <el-form-item label="城市" required>
            <el-input v-model="form.city" maxlength="50" />
          </el-form-item>
          <el-form-item label="区县" required>
            <el-input v-model="form.district" maxlength="50" />
          </el-form-item>
          <el-form-item label="地区码" required>
            <el-input v-model="form.region_code" maxlength="12" placeholder="例如330106" />
          </el-form-item>
        </div>
        <el-form-item label="详细地址" required>
          <el-input v-model="form.detail" type="textarea" :rows="3" maxlength="200" />
        </el-form-item>
        <el-checkbox v-model="form.is_default">设为默认地址</el-checkbox>
        <div class="address-form__actions">
          <el-button native-type="submit" type="primary" :loading="saving" :disabled="!formValid">
            {{ editingId ? '保存修改' : '创建地址' }}
          </el-button>
          <el-button @click="resetForm">取消</el-button>
        </div>
      </el-form>

      <div v-if="loading" class="address-page__state">地址加载中…</div>
      <div v-else-if="!addresses.length" class="address-page__state">
        暂无地址，请先新建一条用于结算的地址。
      </div>
      <div v-else class="address-list">
        <article v-for="address in addresses" :key="address.id" class="address-item">
          <div class="address-item__heading">
            <strong>{{ address.recipient }} {{ address.phone }}</strong>
            <el-tag v-if="address.is_default" type="success">默认</el-tag>
          </div>
          <p>{{ address.province }}{{ address.city }}{{ address.district }}{{ address.detail }}</p>
          <p class="address-item__meta">
            地区码：{{ address.region_code }} · 版本：{{ address.version }}
          </p>
          <div class="address-item__actions">
            <el-button :disabled="busyId !== ''" @click="editAddress(address)">编辑</el-button>
            <el-button
              v-if="!address.is_default"
              :loading="busyId === address.id"
              @click="makeDefault(address)"
            >
              设为默认
            </el-button>
            <el-button
              type="danger"
              plain
              :disabled="busyId !== ''"
              @click="removeAddress(address)"
            >
              删除
            </el-button>
          </div>
        </article>
      </div>
      <el-button class="address-page__refresh" :loading="loading" @click="loadAddresses">
        刷新列表
      </el-button>
      <router-link class="address-page__back" to="/account">返回我的账号</router-link>
    </el-card>
  </div>
</template>

<style scoped>
.address-page {
  max-width: 960px;
  margin: 0 auto;
}
.address-page__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
}
.address-page__header h1 {
  margin: 0;
  font-size: 24px;
}
.address-page__header p {
  margin: 8px 0 0;
  color: var(--mall-text-secondary);
}
.address-form {
  padding: 24px 0;
  border-bottom: 1px solid var(--mall-border);
}
.address-form__grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0 16px;
}
.address-form__actions,
.address-item__actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 16px;
}
.address-form__actions .el-button,
.address-item__actions .el-button {
  min-height: 44px;
  margin: 0;
}
.address-page__state {
  padding: 32px 0;
  text-align: center;
  color: var(--mall-text-secondary);
}
.address-item {
  padding: 20px 0;
  border-bottom: 1px solid var(--mall-border);
}
.address-item__heading {
  display: flex;
  align-items: center;
  gap: 12px;
}
.address-item__meta {
  color: var(--mall-text-secondary);
  font-size: 13px;
}
.address-page__refresh {
  min-height: 44px;
  margin-top: 16px;
}
.address-page__back {
  display: inline-flex;
  align-items: center;
  min-height: 44px;
  margin-left: 16px;
}
:deep(.el-input__inner),
:deep(.el-textarea__inner) {
  font-size: 16px;
}
@media (max-width: 767px) {
  .address-form__grid {
    grid-template-columns: 1fr;
  }
  .address-page__header {
    align-items: stretch;
    flex-direction: column;
  }
}
</style>
