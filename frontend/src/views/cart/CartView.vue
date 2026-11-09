<script setup>
import { computed, ref, watch } from 'vue'
import { useUserStore } from '@/stores/user'
import {
  guestCart,
  updateGuest,
  removeGuest,
  mergeGuest,
  getCart,
  patchItem,
  deleteItem,
  pendingAdd,
  addMember,
} from '@/api/cart'
const user = useUserStore()
const guest = ref(guestCart()),
  items = ref([]),
  error = ref(''),
  loading = ref(false),
  busy = ref(false),
  pending = ref(null)
const picked = computed(() => items.value.filter((i) => i.selected))
const ready = computed(() => picked.value.length && picked.value.every((i) => i.available))
let serial = 0
async function load(merge = false) {
  const ticket = ++serial
  error.value = ''
  loading.value = true
  try {
    await user.restoreSession()
    if (ticket !== serial) return
    const id = user.profile?.id
    guest.value = guestCart()
    if (!id) {
      items.value = []
      return
    }
    pending.value = pendingAdd(id)
    if (guest.value.items.length && (merge || !guest.value.needsConfirmation)) {
      try {
        guest.value = await mergeGuest(id)
      } catch (e) {
        error.value = e.message
        guest.value = guestCart()
      }
    }
    const out = await getCart()
    if (ticket === serial) items.value = out.items
  } catch (e) {
    if (ticket === serial) error.value = e.message
  } finally {
    if (ticket === serial) loading.value = false
  }
}
async function mutate(task) {
  if (busy.value) return
  busy.value = true
  error.value = ''
  try {
    await task()
    await load()
  } catch (e) {
    await load()
    error.value = e.message
  } finally {
    busy.value = false
  }
}
function rememberPrices() {
  sessionStorage.setItem(
    'siq.quote.prices.' + user.profile.id,
    JSON.stringify(Object.fromEntries(picked.value.map((i) => [i.sku_id, i.current_price]))),
  )
}
function editGuest(i, input = null) {
  try {
    guest.value = input ? updateGuest(i.sku_id, input.valueAsNumber) : removeGuest(i.sku_id)
    error.value = ''
  } catch (e) {
    if (input) input.value = i.quantity
    error.value = e.message
  }
}
watch(
  () => user.profile?.id,
  () => { items.value = []; pending.value = null; load() },
  { immediate: true },
)
</script>
<template>
  <section class="catalog cart">
    <h1>购物车</h1>
    <p v-if="error" role="alert">
      {{ error }} <button :disabled="loading || busy" @click="load()">刷新</button>
    </p>
    <p v-if="loading">正在读取购物车…</p>
    <template v-else>
      <template v-if="guest.items.length">
        <h2>{{ user.isLoggedIn ? '待合并的商品' : '已选商品' }}</h2>
        <article v-for="i in guest.items" :key="i.sku_id">
          <h3>{{ i.title }} · {{ i.label }}</h3>
          <p>加入时单价 ¥{{ i.current_price }}</p>
          <label>数量
            <input
              type="number"
              min="1"
              max="99"
              :disabled="!!guest.batch"
              :value="i.quantity"
              @change="editGuest(i, $event.target)"
            ></label>
          <button :disabled="!!guest.batch" @click="editGuest(i)">移除</button>
          <p v-if="i.reason">{{ i.reason }}</p>
        </article>
        <button v-if="user.isLoggedIn" :disabled="busy" @click="load(true)">重新核对并合并</button>
        <router-link v-else :to="{ path: '/login', query: { redirect: '/cart' } }">
          登录并合并购物车
        </router-link>
      </template>
      <button
        v-if="user.isLoggedIn && pending"
        :disabled="busy"
        @click="mutate(() => addMember(user.profile.id, pending.line))"
      >
        确认上次加购结果
      </button>
      <template v-if="user.isLoggedIn && items.length">
        <article v-for="i in items" :key="i.id">
          <label><input
                   type="checkbox"
                   :checked="i.selected"
                   :disabled="busy || (!i.available && !i.selected)"
                   @change="mutate(() => patchItem(i, { selected: !i.selected }))"
                 >
            {{ i.title }} · {{ i.label }}</label>
          <p>
            单价 ¥{{ i.current_price }} <span v-if="!i.available">{{ i.unavailable_reason }}</span>
          </p>
          <label>数量
            <input
              :value="i.quantity"
              :disabled="busy"
              type="number"
              min="1"
              max="99"
              @change="mutate(() => patchItem(i, { quantity: Number($event.target.value) }))"
            ></label>
          <button :disabled="busy" @click="mutate(() => deleteItem(i))">移除</button>
        </article>
        <p v-if="picked.some((i) => !i.available)">请取消选中失效商品或调整数量后继续。</p>
        <router-link v-if="ready && !busy" class="cta" to="/checkout" @click="rememberPrices">
          结算预览（{{ picked.length }}种规格）
        </router-link>
      </template>
      <p v-if="!error && !guest.items.length && !items.length">购物车还是空的。</p>
      <router-link to="/">继续选购</router-link>
    </template>
  </section>
</template>
<style src="../catalog/catalog.css"></style>
<style scoped>
.cart article {
  margin: 12px 0;
}
.cart input[type='number'] {
  width: 6em;
}
.cart input[type='checkbox'] {
  min-height: 0;
}
.cart .cta {
  background: var(--mall-color-primary);
  color: white;
  padding: 0 18px;
  border-radius: 8px;
  margin-right: 16px;
}
</style>
