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
    await shop.route('**/carts/merge/', async (route) => {
      await route.fetch()
      await route.abort('connectionreset')
    }, { times: 1 })
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
  } finally {
    await browser.close()
  }
})().catch((e) => {
  console.error(e)
  process.exitCode = 1
})
