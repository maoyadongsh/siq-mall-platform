const { chromium } = require('playwright-core')
const assert = require('node:assert/strict')
;(async () => {
  const browser = await chromium.launch({
    executablePath:
      process.env.SIQ_CHROME_PATH || 'C:/Program Files/Google/Chrome/Application/chrome.exe',
    headless: true,
  })
  try {
    const ctx = await browser.newContext({ viewport: { width: 390, height: 844 } })
    await ctx.addInitScript(() => Object.defineProperty(navigator, 'locks', { value: undefined }))
    const origin = process.env.SIQ_BROWSER_URL
    const page = await ctx.newPage()
    await page.goto(origin + '/login')
    await page.locator('[name=identifier]').fill('accept_operator')
    await page.locator('[name=password]').fill(process.env.SIQ_TEST_PASSWORD)
    await page.locator('[type=submit]').click()
    await page.getByRole('link', { name: '商品管理' }).waitFor()
    await page.getByRole('link', { name: '商品管理' }).click()
    await page.getByRole('button', { name: '新建商品' }).click()
    await page.locator('.draft').getByLabel('商品名称', { exact: true }).fill('测试茶杯')
    await page.getByLabel('分类', { exact: true }).fill('茶具')
    await page.getByLabel('规格名称').fill('青绿')
    await page.getByLabel('售价').fill('99')
    await page.getByLabel('可售库存').fill('3')
    await page.getByRole('button', { name: '添加规格' }).click()
    await page.getByLabel('规格名称').last().fill('暖白')
    await page.getByLabel('售价').last().fill('129')
    await page.getByRole('button', { name: '保存草稿' }).click()
    await page.getByRole('link', { name: '维护商品' }).click()
    const png = await page.evaluate(() => {
      const canvas = document.createElement('canvas')
      canvas.width = 40
      canvas.height = 30
      canvas.getContext('2d').fillRect(0, 0, 40, 30)
      return canvas.toDataURL('image/png').split(',')[1]
    })
    await page
      .locator('input[type=file]')
      .setInputFiles({ name: 'cup.png', mimeType: 'image/png', buffer: Buffer.from(png, 'base64') })
    await page.getByRole('button', { name: '保存商品信息' }).click()
    await page.getByText('商品信息已保存', { exact: true }).waitFor()
    const variant = page
      .locator('.variant-editor')
      .filter({ has: page.getByRole('heading', { name: '青绿' }) })
    await variant.getByLabel('售价').fill('109')
    await variant.getByLabel('修改原因').fill('补货调价')
    await variant.getByRole('button', { name: '保存规格' }).click()
    await variant.getByText('规格已保存', { exact: true }).waitFor()
    await variant.getByLabel('库存调整量').fill('2')
    await variant.getByLabel('调整原因').fill('到货盘点')
    await page.route(
      '**/stock-adjustments/',
      async (route) => {
        await route.fetch()
        await route.abort('connectionreset')
      },
      { times: 1 },
    )
    await variant.getByRole('button', { name: '登记库存调整' }).click()
    await variant.getByRole('button', { name: '确认上次库存调整结果' }).click()
    await variant.getByText('可售库存 5', { exact: true }).waitFor()
    await variant.getByRole('listitem').first().waitFor()
    assert.equal(await variant.getByRole('listitem').count(), 1)
    await page.getByRole('link', { name: '返回商品管理' }).click()
    await page.getByRole('button', { name: '上架', exact: true }).click()
    await page.getByText('在售', { exact: true }).waitFor()
    const shop = await browser.newPage({ viewport: { width: 1440, height: 900 } })
    await shop.goto(origin)
    await shop.getByRole('link', { name: '查看规格' }).click()
    await shop.locator('img.product-cover').evaluate((img) => img.decode())
    assert.equal(await shop.locator('img.product-cover').evaluate((img) => img.naturalWidth), 40)
    await shop.getByRole('button', { name: '青绿' }).click()
    await shop.getByText('¥109.00 · 有货').waitFor()
    await shop.setViewportSize({ width: 375, height: 812 })
    await shop.getByRole('button', { name: /暖白/ }).click()
    await shop.getByText('¥129.00 · 暂时缺货').waitFor()
    await page.getByRole('button', { name: '下架', exact: true }).click()
    await page.getByText('已下架', { exact: true }).waitFor()
    await shop.reload()
    await shop.getByText('商品已下架或不存在', { exact: false }).waitFor()
    console.log('PASS catalog desktop/mobile publish/SKU/unpublish')
    await page.goto(origin + '/account/addresses')
    await page.getByRole('button', { name: '新建地址' }).click()
    await page.getByLabel('收件人').fill('测试用户')
    await page.getByLabel('联系电话').fill('13800000000')
    await page.getByLabel('省份').selectOption({ label: '浙江省' })
    await page.getByLabel('城市').selectOption({ label: '杭州市' })
    await page.getByLabel('区县').selectOption({ label: '西湖区' })
    await page.getByLabel('详细地址').fill('样例路1号')
    await page.getByRole('button', { name: '创建地址' }).click()
    await page.getByText('地址已创建', { exact: true }).waitFor()
    const tab = await ctx.newPage()
    await tab.goto(origin + '/account/addresses')
    for (const p of [page, tab]) await p.getByRole('button', { name: '编辑', exact: true }).click()
    await page.getByLabel('详细地址').fill('修改甲')
    await page.getByRole('button', { name: '保存修改' }).click()
    await page.getByText('地址已更新', { exact: true }).waitFor()
    await tab.getByLabel('详细地址').fill('修改乙')
    const conflict = tab.waitForResponse(
      (r) => r.request().method() === 'PATCH' && r.status() === 409,
    )
    await tab.getByRole('button', { name: '保存修改' }).click()
    await conflict
    assert.equal(await tab.getByLabel('详细地址').inputValue(), '修改乙')
    console.log('PASS address cascading fields + stale edit retained')
    let active = 0,
      peak = 0,
      requests = 0
    let started
    const seen = new Promise((r) => (started = r))
    await ctx.route('**/auth/web/refresh/', async (route) => {
      active++
      peak = Math.max(active, peak)
      if (++requests === 1) {
        started()
        await new Promise((r) => setTimeout(r, 11000))
      }
      try {
        const resp = await route.fetch()
        await route.fulfill({ response: resp })
      } finally {
        active--
      }
    })
    await page.reload({ waitUntil: 'domcontentloaded' })
    await seen
    await new Promise((r) => setTimeout(r, 10100))
    await tab.reload({ waitUntil: 'domcontentloaded' })
    for (const p of [page, tab]) await p.getByRole('button', { name: '新建地址' }).waitFor()
    assert.equal(peak, 1)
    assert.equal(requests, 2)
    console.log('PASS two-tab fallback 11s refresh')
    await page.goto(origin + '/ops/products')
    await page.getByRole('button', { name: '上架', exact: true }).click()
    await page.getByText('在售', { exact: true }).waitFor()
    await shop.goto(origin)
    await shop.getByRole('link', { name: '查看规格' }).click()
    await shop.getByRole('button', { name: '青绿' }).click()
    await shop.getByRole('button', { name: '加入购物车' }).click()
    await shop.getByText('已加入购物车', { exact: true }).waitFor()
    await shop.getByRole('link', { name: '查看购物车' }).click()
    await shop.getByRole('link', { name: '登录并合并购物车' }).click()
    await shop.locator('[name=identifier]').fill('accept_operator')
    await shop.locator('[name=password]').fill(process.env.SIQ_TEST_PASSWORD)
    await shop.route(
      '**/carts/merge/',
      async (route) => {
        await route.fetch()
        await route.abort('connectionreset')
      },
      { times: 1 },
    )
    await shop.locator('[type=submit]').click()
    await shop.getByRole('button', { name: '重新核对并合并' }).click()
    await shop.getByRole('link', { name: /结算预览/ }).waitFor()
    assert.equal(await shop.getByLabel('数量', { exact: true }).inputValue(), '1')
    await shop.getByText('单价 ¥109.00', { exact: false }).waitFor()
    await page.getByRole('link', { name: '维护商品' }).click()
    const edit = page
      .locator('.variant-editor')
      .filter({ has: page.getByRole('heading', { name: '青绿' }) })
    await edit.getByLabel('售价').fill('129')
    await edit.getByLabel('修改原因').fill('报价变更验证')
    await edit.getByRole('button', { name: '保存规格' }).click()
    await edit.getByText('规格已保存', { exact: true }).waitFor()
    await shop.getByRole('link', { name: /结算预览/ }).click()
    await shop.getByText('价格已更新', { exact: false }).waitFor()
    await shop.getByText('¥0.00', { exact: true }).waitFor()
    await shop.getByText('¥129.00', { exact: true }).last().waitFor()
    console.log('PASS guest cart -> sign in -> merge -> repriced checkout')
    await shop.route(
      '**/api/v1/orders/',
      async (route) => {
        assert.equal(route.request().method(), 'POST')
        const response = await route.fetch()
        assert.equal(response.status(), 201)
        await route.abort('connectionreset')
      },
      { times: 1 },
    )
    await shop.getByRole('button', { name: '确认金额并提交订单' }).click()
    await shop.getByRole('button', { name: '找回上次提交的订单' }).click()
    await shop.getByRole('heading', { name: '待付款', exact: true }).waitFor()
    const no = new URL(shop.url()).pathname.split('/').pop()
    await shop.getByRole('button', { name: '进入模拟支付' }).click()
    await shop.getByRole('button', { name: '模拟付款失败' }).click()
    await shop.getByText('上次模拟付款失败', { exact: false }).waitFor()
    await shop.getByRole('button', { name: '进入模拟支付' }).click()
    await shop.getByRole('button', { name: '模拟付款成功' }).click()
    await shop.getByRole('heading', { name: '待发货', exact: true }).waitFor()
    await page.goto(origin + '/ops/orders')
    await page.getByLabel('订单号', { exact: true }).fill(no)
    await page.getByRole('button', { name: '查询', exact: true }).click()
    await page.getByRole('link', { name: '查看订单' }).click()
    await page.getByLabel('承运商').fill('演示物流')
    await page.getByLabel('物流单号').fill('DEMO-SMOKE')
    await page.getByRole('button', { name: '确认整单发货' }).click()
    await page.getByRole('heading', { name: '待收货', exact: true }).waitFor()
    await shop.reload()
    await shop.getByRole('button', { name: '确认收货', exact: true }).click()
    await shop.getByRole('button', { name: '已收到商品，完成订单' }).click()
    await shop.getByRole('heading', { name: '已完成', exact: true }).waitFor()
    await shop.goto(origin + '/account')
    await shop.getByRole('link', { name: '我的订单与交易记录' }).click()
    assert.equal(
      await shop
        .getByRole('link', { name: '查看订单' })
        .waitFor()
        .then(() => shop.getByRole('link', { name: '查看订单' }).count()),
      1,
    )
    console.log(
      'PASS lost order response -> recover -> failed payment -> retry -> ship -> receive -> history',
    )
    await shop.goto(origin)
    await shop.getByRole('link', { name: '查看规格' }).click()
    await shop.getByRole('button', { name: '青绿' }).click()
    await shop.getByRole('button', { name: '加入购物车' }).click()
    await shop.getByText('已加入购物车', { exact: true }).waitFor()
    await shop.getByRole('link', { name: '查看购物车' }).click()
    await shop.getByRole('link', { name: /结算预览/ }).click()
    await shop.getByRole('button', { name: '确认金额并提交订单' }).click()
    await shop.getByRole('heading', { name: '待付款', exact: true }).waitFor()
    await page.goto(origin + '/ops/coupons')
    await page.getByRole('button', { name: '新建优惠券' }).click()
    await page.getByLabel('券名称').fill('春日满129减20')
    await page.getByRole('button', { name: '保存草稿' }).click()
    await page.getByRole('button', { name: '发布', exact: true }).click()
    await page.getByLabel('操作原因').fill('领券验收')
    await page.getByRole('button', { name: '确认发布' }).click()
    await page.getByText('发放中', { exact: true }).waitFor()
    await shop.goto(origin + '/coupons')
    await shop.route(
      '**/coupons/*/claim/',
      async (route) => {
        assert.equal((await route.fetch()).status(), 201)
        await route.abort('connectionreset')
      },
      { times: 1 },
    )
    await shop.getByRole('button', { name: '领取优惠券' }).click()
    await shop.getByRole('button', { name: '领取优惠券' }).click()
    await shop.getByText('已领取「春日满129减20」', { exact: false }).waitFor()
    await page.getByRole('button', { name: '停止领取' }).click()
    await page.getByLabel('操作原因').fill('结束发放')
    await page.getByRole('button', { name: '确认停领' }).click()
    await page.getByText('已停领', { exact: true }).waitFor()
    async function useCoupon() {
      await shop.goto(origin)
      await shop.getByRole('link', { name: '查看规格' }).click()
      await shop.getByRole('button', { name: '青绿' }).click()
      await shop.getByRole('button', { name: '加入购物车' }).click()
      await shop.getByText('已加入购物车', { exact: true }).waitFor()
      await shop.getByRole('link', { name: '查看购物车' }).click()
      await shop.getByRole('link', { name: /结算预览/ }).click()
      await shop.getByLabel('结算优惠券').selectOption({ label: '春日满129减20 · 可减 ¥20.00' })
      await shop.getByText('¥109.00', { exact: true }).waitFor()
      await shop.getByRole('button', { name: '确认金额并提交订单' }).click()
      await shop.getByText('已减 ¥20.00', { exact: false }).waitFor()
    }
    await useCoupon()
    await shop.getByRole('button', { name: '取消订单', exact: true }).click()
    await shop.getByRole('button', { name: '确认取消并释放库存' }).click()
    await shop.getByRole('heading', { name: '已取消', exact: true }).waitFor()
    await useCoupon()
    await shop.getByRole('button', { name: '进入模拟支付' }).click()
    await shop.getByRole('button', { name: '模拟付款成功' }).click()
    await shop.getByRole('heading', { name: '待发货', exact: true }).waitFor()
    await shop.goto(origin + '/account/coupons')
    await shop.getByLabel('券状态').selectOption('used')
    await shop.getByRole('heading', { name: '春日满129减20' }).waitFor()
    console.log(
      'PASS coupon publish -> claim retry -> stop -> select -> release -> reuse -> redeem',
    )

    await shop.goto(origin + '/orders/' + no)
    await shop.getByRole('link', { name: '评价商品与查看审核结果' }).click()
    await shop.getByRole('radio', { name: '1 星', exact: true }).check()
    await shop.getByLabel('评价内容').fill('杯子比预想的小')
    await shop.route(
      '**/api/v1/reviews/',
      async (route) => {
        assert.equal((await route.fetch()).status(), 201)
        await route.abort('connectionreset')
      },
      { times: 1 },
    )
    await shop.getByRole('button', { name: '提交评价' }).click()
    await shop.getByRole('button', { name: '提交评价' }).click()
    await shop.getByText('评价已提交，等待审核', { exact: true }).waitFor()
    const guest = await browser.newPage({ viewport: { width: 375, height: 812 } })
    await guest.clock.install()
    await guest.goto(origin)
    await guest.getByRole('link', { name: '查看规格' }).click()
    await guest.getByText('暂无公开评价。', { exact: true }).waitFor()
    const staff = await browser.newPage({ viewport: { width: 1440, height: 900 } })
    await staff.goto(origin + '/login')
    await staff.locator('[name=identifier]').fill('accept_moderator')
    await staff.locator('[name=password]').fill(process.env.SIQ_TEST_PASSWORD)
    await staff.locator('[type=submit]').click()
    await staff.getByRole('link', { name: '评价审核' }).click()
    await staff.getByRole('button', { name: '公开评价' }).click()
    await staff.getByRole('button', { name: '确认公开' }).click()
    await staff.getByText('审核已保存', { exact: true }).waitFor()
    await guest.bringToFront()
    await guest.clock.fastForward(46000)
    await guest.getByText('杯子比预想的小', { exact: true }).waitFor()
    await guest.getByText('1.0 / 5', { exact: true }).waitFor()
    await staff.getByLabel('审核状态').selectOption('approved')
    await staff.getByRole('button', { name: '筛选' }).click()
    await staff.getByRole('button', { name: '隐藏评价' }).click()
    await staff.getByLabel('审核原因', { exact: false }).fill('演示撤回')
    await staff.getByRole('button', { name: '确认隐藏' }).click()
    await staff.getByText('当前筛选下没有评价。', { exact: true }).waitFor()
    await guest.bringToFront()
    await guest.clock.fastForward(46000)
    await guest.getByText('暂无公开评价。', { exact: true }).waitFor()
    await shop.goto(origin + '/account/reviews')
    await shop.getByText('审核说明：演示撤回', { exact: true }).waitFor()
    console.log(
      'PASS review lost response -> retry -> moderator publishes low rating -> public score -> hide -> buyer reason',
    )

    await page.goto(origin + '/ops/notification-templates')
    await page.setViewportSize({ width: 1440, height: 900 })
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true)
    await page.locator('.template-list button').filter({ hasText: 'order.paid' }).first().click()
    await page.getByLabel('标题', { exact: true }).fill('支付成功提醒 {order_no}')
    await page.getByLabel('正文', { exact: true }).fill('订单 {order_no} 已完成模拟支付，请查看履约动态。')
    await page.getByRole('button', { name: '保存为新版本' }).click()
    await page.getByRole('button', { name: '启用此版本' }).click()
    await page.getByText('新版本已启用，后续事件将使用此模板。', { exact: true }).waitFor()
    console.log('PASS notification template draft -> server preview -> activate')

    await shop.goto(origin + '/messages')
    await shop
      .getByRole('heading', { name: '评价审核结果已更新' })
      .nth(1)
      .waitFor({ timeout: 40000 })
    await shop.getByRole('button', { name: '全部已读' }).click()
    await shop.getByText(/已处理 \d+ 条消息/).waitFor()
    await shop.reload()
    assert.equal(await shop.getByRole('button', { name: '查看并标为已读' }).count(), 0)
    await shop.getByRole('button', { name: '订单', exact: true }).click()
    for (const width of [1440, 375]) {
      await shop.setViewportSize({ width, height: 844 })
      assert.equal(await shop.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true)
    }
    await shop.getByRole('button', { name: '查看关联内容' }).first().click()
    await shop.waitForURL(/\/orders\//)
    console.log('PASS inbox order/review delivery -> read all -> business target')
  } finally {
    await browser.close()
  }
})().catch((e) => {
  console.error(e)
  process.exitCode = 1
})
