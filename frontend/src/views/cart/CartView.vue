<script setup lang="ts">
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
import type { CartItem, GuestCart, GuestCartLine } from '@/types/models'
import { messageOf } from '@/utils/errors'

type GuestLine = GuestCartLine & { reason?: string }
type GuestState = Omit<GuestCart, 'items'> & { items: GuestLine[] }

const user = useUserStore()
const guest = ref<GuestState>(guestCart()),
  items = ref<CartItem[]>([]),
  error = ref(''),
  loading = ref(false),
  busy = ref(false),
  pending = ref<ReturnType<typeof pendingAdd>>(null)
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
        error.value = messageOf(e)
        guest.value = guestCart()
      }
    }
    const out = await getCart()
    if (ticket === serial) items.value = out.items
  } catch (e) {
    if (ticket === serial) error.value = messageOf(e)
  } finally {
    if (ticket === serial) loading.value = false
  }
}
async function mutate(task: () => Promise<unknown>) {
  if (busy.value) return
  busy.value = true
  error.value = ''
  try {
    await task()
    await load()
  } catch (e) {
    await load()
    error.value = messageOf(e)
  } finally {
    busy.value = false
  }
}
function rememberPrices() {
  const userId = user.profile?.id
  if (!userId) return
  sessionStorage.setItem(
    'siq.quote.prices.' + userId,
    JSON.stringify(Object.fromEntries(picked.value.map((i) => [i.sku_id, i.current_price]))),
  )
}
function editGuest(i: GuestLine, input: HTMLInputElement | null = null) {
  try {
    guest.value = input ? updateGuest(i.sku_id, input.valueAsNumber) : removeGuest(i.sku_id)
    error.value = ''
  } catch (e) {
    if (input) input.value = String(i.quantity)
    error.value = messageOf(e)
  }
}
function confirmPending() {
  const userId = user.profile?.id
  const op = pending.value
  if (!userId || !op) return
  mutate(() => addMember(userId, op.line))
}
watch(
  () => user.profile?.id,
  () => { items.value = []; pending.value = null; load() },
  { immediate: true },
)
</script>
<template>
  <section class="catalog cart">
    <header class="cart__header">
      <div><p class="catalog__eyebrow">YOUR SELECTION</p><h1>购物车</h1><p>核对商品与数量，价格、库存和优惠将在结算时再次确认。</p></div>
      <router-link to="/products">继续选购 <span aria-hidden="true">→</span></router-link>
    </header>

    <div v-if="error" class="cart__notice cart__notice--error" role="alert"><span>{{ error }}</span><button :disabled="loading || busy" @click="load()">刷新</button></div>
    <div v-if="loading" class="catalog__state" role="status"><span class="catalog__spinner" aria-hidden="true" />正在读取购物车…</div>
    <template v-else>
      <section v-if="guest.items.length" class="cart__section">
        <header><div><p class="cart__section-kicker">GUEST SELECTION</p><h2>{{ user.isLoggedIn ? '待合并的商品' : '已选商品' }}</h2></div><span>{{ guest.items.length }} 种规格</span></header>
        <article v-for="i in guest.items" :key="i.sku_id" class="cart-line">
          <div class="cart-line__info"><h3>{{ i.title }}</h3><p>{{ i.label }}</p><small v-if="i.reason" class="cart-line__warning">{{ i.reason }}</small></div>
          <p class="cart-line__price"><small>加入时单价</small><strong class="siq-price">¥{{ i.current_price }}</strong></p>
          <label class="cart-line__quantity"><span>数量</span><input type="number" min="1" max="99" :disabled="!!guest.batch" :value="i.quantity" @change="editGuest(i, $event.target as HTMLInputElement)"></label>
          <button class="cart-line__remove" :disabled="!!guest.batch" @click="editGuest(i)">移除</button>
        </article>
        <div class="cart__section-actions">
          <button v-if="user.isLoggedIn" class="catalog-button catalog-button--primary" :disabled="busy" @click="load(true)">重新核对并合并</button>
          <router-link v-else class="catalog-button catalog-button--primary" :to="{ path: '/login', query: { redirect: '/cart' } }">登录并合并购物车</router-link>
        </div>
      </section>

      <div v-if="user.isLoggedIn && pending" class="cart__recovery" role="status"><div><strong>上次加购结果待确认</strong><p>先核对原操作，避免重复加入商品。</p></div><button class="catalog-button catalog-button--primary" :disabled="busy" @click="confirmPending">确认上次加购结果</button></div>

      <div v-if="user.isLoggedIn && items.length" class="cart__layout">
        <section class="cart__section cart__items">
          <header><div><p class="cart__section-kicker">IN YOUR CART</p><h2>商品清单</h2></div><span>{{ items.length }} 种规格</span></header>
          <article v-for="i in items" :key="i.id" class="cart-line" :class="{ 'cart-line--unavailable': !i.available }">
            <label class="cart-line__check"><input type="checkbox" :checked="i.selected" :disabled="busy || (!i.available && !i.selected)" @change="mutate(() => patchItem(i, { selected: !i.selected }))"><span class="siq-sr-only">选择{{ i.title }}</span></label>
            <div class="cart-line__info"><h3>{{ i.title }}</h3><p>{{ i.label }}</p><small v-if="!i.available" class="cart-line__warning">{{ i.unavailable_reason }}</small></div>
            <p class="cart-line__price"><small>单价</small><strong class="siq-price">¥{{ i.current_price }}</strong></p>
            <label class="cart-line__quantity"><span>数量</span><input :value="i.quantity" :disabled="busy" type="number" min="1" max="99" @change="mutate(() => patchItem(i, { quantity: Number(($event.target as HTMLInputElement).value) }))"></label>
            <button class="cart-line__remove" :disabled="busy" @click="mutate(() => deleteItem(i))">移除</button>
          </article>
        </section>

        <aside class="cart__summary">
          <p class="cart__section-kicker">ORDER SUMMARY</p>
          <h2>结算摘要</h2>
          <dl><div><dt>已选规格</dt><dd>{{ picked.length }} 种</dd></div><div><dt>商品价格</dt><dd>结算时核对</dd></div><div><dt>优惠与配送</dt><dd>结算时试算</dd></div></dl>
          <p v-if="picked.some((i) => !i.available)" class="cart__summary-warning">请取消选中失效商品或调整数量后继续。</p>
          <p v-else class="cart__summary-note">最终应付金额以服务端实时报价为准。</p>
          <router-link v-if="ready && !busy" class="catalog-button catalog-button--primary cart__checkout" to="/checkout" @click="rememberPrices">结算预览（{{ picked.length }}种规格）<span aria-hidden="true">→</span></router-link>
          <button v-else class="catalog-button catalog-button--primary cart__checkout" disabled>{{ busy ? '正在更新购物车…' : '选择可售商品后结算' }}</button>
        </aside>
      </div>

      <div v-if="!error && !guest.items.length && !items.length" class="cart__empty">
        <span aria-hidden="true">S</span><h2>购物车还是空的</h2><p>从一件真正需要的日常好物开始。</p><router-link class="catalog-button catalog-button--primary" to="/products">去选购商品</router-link>
      </div>
    </template>
  </section>
</template>
<style src="../catalog/catalog.css"></style>
<style scoped>
.cart__header {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 24px;
  margin-bottom: 32px;
}
.cart__header h1 {
  margin: 8px 0 10px;
  font-size: clamp(30px, 4vw, 40px);
  font-weight: 600;
}
.cart__header p:last-child {
  margin: 0;
  color: var(--mall-text-secondary);
  font-size: 14px;
}
.cart__header > a {
  display: inline-flex;
  align-items: center;
  gap: 14px;
  min-height: 44px;
  font-size: 13px;
  text-decoration: none;
}
.cart__notice,
.cart__recovery {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 20px;
  padding: 16px 18px;
  border: 1px solid var(--mall-border);
  border-radius: var(--mall-radius-md);
  background: var(--mall-surface);
}
.cart__notice--error {
  color: var(--mall-color-danger);
  border-color: rgb(180 35 24 / 18%);
  background: #fff7f5;
}
.cart__recovery {
  border-color: rgb(138 90 24 / 20%);
  background: #fbf5e9;
}
.cart__recovery strong {
  color: var(--mall-color-warning);
}
.cart__recovery p {
  margin: 3px 0 0;
  color: var(--mall-text-secondary);
  font-size: 12px;
}
.cart__layout {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 300px;
  gap: 24px;
  align-items: start;
}
.cart__section {
  overflow: hidden;
  border: 1px solid var(--mall-border);
  border-radius: var(--mall-radius-lg);
  background: var(--mall-surface);
}
.cart__section + .cart__recovery,
.cart__section + .cart__layout {
  margin-top: 24px;
}
.cart__section > header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 22px 24px;
  border-bottom: 1px solid var(--mall-border);
}
.cart__section > header h2 {
  margin: 4px 0 0;
  font-size: 20px;
  font-weight: 600;
}
.cart__section > header > span {
  color: var(--mall-text-secondary);
  font-size: 12px;
}
.cart__section-kicker {
  margin: 0;
  color: var(--mall-text-secondary);
  font-size: 9px;
  font-weight: 650;
  letter-spacing: 0.13em;
}
.cart-line {
  display: grid;
  grid-template-columns: auto minmax(180px, 1fr) 120px 96px 52px;
  gap: 16px;
  align-items: center;
  padding: 22px 24px;
  border-bottom: 1px solid var(--mall-border);
}
.cart__section:not(.cart__items) .cart-line {
  grid-template-columns: minmax(180px, 1fr) 120px 96px 52px;
}
.cart-line:last-child {
  border-bottom: 0;
}
.cart-line--unavailable {
  background: #faf9f6;
}
.cart-line__check input {
  width: 18px;
  height: 18px;
  min-height: 0;
  padding: 0;
  accent-color: var(--mall-color-primary);
}
.cart-line__info {
  min-width: 0;
}
.cart-line__info h3 {
  margin: 0 0 5px;
  overflow-wrap: anywhere;
  font-size: 15px;
  font-weight: 600;
}
.cart-line__info p {
  margin: 0;
  color: var(--mall-text-secondary);
  font-size: 12px;
}
.cart-line__warning {
  display: block;
  margin-top: 6px;
  color: var(--mall-color-danger);
  font-size: 11px;
}
.cart-line__price {
  margin: 0;
}
.cart-line__price small,
.cart-line__price strong {
  display: block;
}
.cart-line__price small,
.cart-line__quantity > span {
  margin-bottom: 3px;
  color: var(--mall-text-secondary);
  font-size: 10px;
}
.cart-line__price strong {
  color: var(--mall-color-primary);
  font-size: 15px;
}
.cart-line__quantity {
  display: grid;
}
.cart-line__quantity input {
  width: 76px;
  text-align: center;
}
.cart-line__remove {
  min-height: 44px;
  padding: 0 !important;
  border: 0 !important;
  color: var(--mall-text-secondary) !important;
  background: transparent !important;
  font-size: 12px;
}
.cart-line__remove:hover {
  color: var(--mall-color-danger) !important;
}
.cart__section-actions {
  display: flex;
  justify-content: flex-end;
  padding: 18px 24px;
  border-top: 1px solid var(--mall-border);
}
.cart__summary {
  position: sticky;
  top: calc(var(--mall-header-height) + 24px);
  padding: 26px;
  border-radius: var(--mall-radius-lg);
  color: #fff;
  background: var(--mall-color-primary);
  box-shadow: var(--mall-shadow-md);
}
.cart__summary .cart__section-kicker {
  color: rgb(255 255 255 / 60%);
}
.cart__summary h2 {
  margin: 7px 0 24px;
  font-size: 22px;
  font-weight: 550;
}
.cart__summary dl {
  margin: 0;
}
.cart__summary dl > div {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  padding: 11px 0;
  border-bottom: 1px solid rgb(255 255 255 / 12%);
  font-size: 12px;
}
.cart__summary dt {
  color: rgb(255 255 255 / 65%);
}
.cart__summary dd {
  margin: 0;
  text-align: right;
}
.cart__summary-note,
.cart__summary-warning {
  margin: 18px 0;
  color: rgb(255 255 255 / 65%);
  font-size: 11px;
  line-height: 1.7;
}
.cart__summary-warning {
  color: #ffe0b2;
}
.cart__checkout {
  display: flex;
  width: 100%;
  margin-top: 10px;
  color: var(--mall-color-primary) !important;
  border-color: #fff !important;
  background: #fff !important;
}
.cart__checkout span {
  margin-left: 12px;
}
.cart__checkout:disabled {
  color: var(--mall-text-secondary) !important;
  border-color: #e4e6e2 !important;
  background: #e4e6e2 !important;
}
.cart__empty {
  padding: 72px 24px;
  border: 1px solid var(--mall-border);
  border-radius: var(--mall-radius-lg);
  background: rgb(255 255 255 / 58%);
  text-align: center;
}
.cart__empty > span {
  display: grid;
  width: 48px;
  height: 48px;
  margin: 0 auto 20px;
  place-items: center;
  border-radius: 15px 15px 15px 5px;
  color: #fff;
  background: var(--mall-color-primary);
  font-size: 21px;
}
.cart__empty h2 {
  margin-bottom: 10px;
  font-size: 24px;
}
.cart__empty p {
  margin-bottom: 24px;
  color: var(--mall-text-secondary);
}
@media (max-width: 1000px) {
  .cart__layout {
    grid-template-columns: 1fr;
  }
  .cart__summary {
    position: static;
  }
}
@media (max-width: 700px) {
  .cart__header {
    align-items: flex-start;
  }
  .cart__header > a {
    display: none;
  }
  .cart-line,
  .cart__section:not(.cart__items) .cart-line {
    grid-template-columns: auto minmax(0, 1fr) auto;
    gap: 12px;
    padding: 18px;
  }
  .cart__section:not(.cart__items) .cart-line {
    grid-template-columns: minmax(0, 1fr) auto;
  }
  .cart-line__info {
    grid-column: 2;
  }
  .cart__section:not(.cart__items) .cart-line__info {
    grid-column: 1;
  }
  .cart-line__price {
    grid-column: 2;
  }
  .cart__section:not(.cart__items) .cart-line__price {
    grid-column: 1;
  }
  .cart-line__quantity {
    grid-column: 2;
  }
  .cart__section:not(.cart__items) .cart-line__quantity {
    grid-column: 1;
  }
  .cart-line__remove {
    grid-column: 3;
    grid-row: 1 / span 3;
  }
  .cart__section:not(.cart__items) .cart-line__remove {
    grid-column: 2;
  }
  .cart__notice,
  .cart__recovery {
    align-items: flex-start;
    flex-direction: column;
  }
}
</style>
