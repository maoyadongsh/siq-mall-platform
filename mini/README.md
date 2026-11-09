# SIQ 优选商城 · 微信小程序

买家通过独立原生小程序浏览商品、选择规格、管理购物车与地址、使用优惠券、下单并查看履约、评价、消息和客服。商城 API 与 PC/H5 共用，页面生命周期与凭据管理由小程序单独处理。当前版本使用商城账号密码登录。微信身份换证、原生地址选择、订阅授权及实际送达仍待接入。

## 工程入口

| 文件 | 用途 |
| --- | --- |
| [app.json](app.json) · [app.js](app.js) | 定义 14 个页面、首页/购物车/我的三个标签页、全局 API 地址。默认指向本机开发服务器的 `/api/v1`。 |
| [utils/api.js](utils/api.js) | 请求、独立 access/refresh/session、一次并发刷新及退出清理。401 后自动重放只读请求。 |
| [结算页](pages/checkout/checkout.js) | 从购物车和地址获取报价，按请求代次忽略晚到结果。提交后用当前买家、原报价与幂等键找回订单。 |
| [订单详情](pages/order-detail/order-detail.js) | 查询订单、模拟支付、收货、评价入口；响应未知时查询原支付单，按服务端状态反馈。 |
| [地址页](pages/addresses/addresses.js) · [客服页](pages/support/support.js) | 默认地址使用专用动作；发送失败保留原消息，重试沿用原标识。 |

## 本机联调

1. 先按[项目启动说明](../README.md)运行 Django 和扫描命令。准备一个商城买家账号、一件已上架且有库存的商品。模拟付款须在隔离后端启用演示开关。
2. 在微信开发者工具导入本目录。团队按本地私有配置提供 AppID；仓库的 [project.config.json](project.config.json) 保留公共设置。不要把生产凭据写入小程序包。
3. 在 `app.js` 核对 `globalData.apiBaseUrl`，保留 `/api/v1` 前缀。开发机回环地址供本机联调；体验版和真机应填写设备可访问并在相应平台账号配置好的 HTTPS 请求/媒体域名。
4. 登录商城账号后从商品详情加购，添加手填地址，试算并确认金额。需要原生选址或订阅模板时，当前页面提示能力状态，买家可继续使用手填与站内通知。

## 已验证的行为

在仓库根目录运行：

```powershell
npm --prefix mini test
node --test qa/acceptance/mini-boundaries.cjs
```

基础适配 4 项覆盖并发 401、写请求恢复、退出与游客合并。另有 9 项边界测试以实际页面 JS 配合可控网络响应和 wx 存储验证，包括账号切换、报价乱序、旧版订单意图、支付超时与客服重试。地址验收还捕获实际页面发出的请求，在 Django 测试端点上切换默认地址。[端侧边界测试](../qa/acceptance/mini-boundaries.cjs) · [后端联动测试](../qa/acceptance/test_delivery_boundaries.py)

## 真机验收登记

使用同一构建和隔离账号，记录基础库、工具版本、系统/机型、网络条件、订单号或脱敏请求 ID。依次走商品分享冷启动、地址输入与键盘、选券后修改地址、提交时断网、切后台再恢复、客服消息重试。另为微信授权的成功、拒绝、取消和不可用保留单独结果。当前自动证据覆盖客户端控制流；开发者工具编译、体验版分发及 iOS/Android 实机结果待登记。[移动设计与验收矩阵](../docs/06-mobile-wechat-design.md) · [当前验收台账](../docs/11-readiness-and-acceptance.md)
