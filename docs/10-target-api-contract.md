# API 契约、联调样例与待接入能力

业务基线 `17f5b91`。本页方法索引取自仓库的 [OpenAPI 3.0.3](openapi.yaml)，共 93 个资源路径、111 个操作。字段类型与枚举可在对应组件中查询；跨端会话、幂等重试及输入组合等约束同时参考下文和实际服务。公共前缀为 `/api/v1/`。

## 1. 基础协议与兼容

成功信封含 `code=0`、`message`、`data`、`request_id` 和带时区的 `timestamp`。失败响应结合 HTTP 状态与业务码处理，字段校验可能带 `errors`。健康探针为兼容特例，依赖降级返回 HTTP 503，响应仍可为 `code=0`、`data.status=degraded`。新增端应显式携带资源尾斜杠，避免写操作经重定向丢失请求体。

- **分页**：页码端点返回 `count/page/page_size/total_pages/results`。通知和会话消息使用不透明游标，客户端原样回传。分类或会话改变时重新取首页。
- **金额与标识**：金额为两位小数字符串，订单和支付业务号为 UUID。保留响应中 ID 的精度，业务时间按其自带偏移解析。
- **写入**：带幂等要求的命令以 UUID 作 `Idempotency-Key`；网络超时保留原键和请求体。更新版本化对象按端点传 `expected_version`。排错使用 `request_id` 关联日志。

## 2. 联调一笔可恢复的交易

先让买家拥有有效地址并选择可售 SKU。以下是请求体示例，ID 要换成当前账号与开发库的实际值；定价只读取服务端返回的报价。

```http
POST /api/v1/checkout/quote/
Authorization: Bearer <access>
Content-Type: application/json

{"address_id":"12","items":[{"sku_id":"41","quantity":2}],"user_coupon_id":null}
```

读取 `data.quote_id`、`expires_at`、四项金额和可用券。在报价有效期内确认提交。切换地址或优惠券时撤销旧报价；报价只做试算，首次下单时才占库存与券。

```http
POST /api/v1/orders/
Authorization: Bearer <access>
Idempotency-Key: 2143e317-b880-4f03-a3ef-94acc9561e64
Content-Type: application/json

{"quote_id":"d94bb0c6-1eb8-4407-8e7a-dad88072b2d6","intent_id":"7304083a-65b7-4d1d-89cb-57457913983a"}
```

创建成功为 201，记录 `data.order_no`。响应丢失时查询 `orders/by-intent/{intent}/` 或以原账号、原键和原报价重放。如果查询暂未找到已提交结果，仍保留原意图。只有业务明确拒绝并重新确认报价后才发起新的购买。

在启用演示支付的开发环境，向 `payments/` 提交 `{"order_no":"<order_no>"}`，再向 `payments/{no}/simulate/` 提交 `{"outcome":"success"}` 或 `{"outcome":"failed"}`。两步各有自己的幂等键。超时查询原支付尝试，同时查看 `status`、`order_status`。履约人员从运营接口发货，买家通过收货动作完成订单。资格、快照与金额约束见[数据模型](09-domain-and-data-spec.md)。

## 3. 身份、会话、用户与地址

| 客户端 | 建立与刷新 | 联调注意点 |
| --- | --- | --- |
| Web / H5 | 先取 `auth/csrf/`，登录传 `identifier,password`；刷新通过 `auth/web/refresh/`。 | 带 Cookie、受信任 Origin 和 `X-CSRF-Token`。refresh 存 HttpOnly Cookie，access 在内存中；前端协调跨标签轮换。 |
| 小程序 | `auth/mini/login/` 使用同一商城账号密码，返回 access、refresh、到期时间及 session_id。mini refresh 以 JSON 提交。 | 本地保存独立会话。并发 401 共用一次刷新，自动重放只读请求；写入按业务幂等流程恢复。 |

切换默认地址使用 `POST users/me/addresses/{address_id}/default/` 与空对象；编辑地址使用 PATCH，提交完整必填地址字段及版本；删除提交版本。OpenAPI 的通用 PATCH 模型会省略 required，DELETE 的请求体也可能未展示，实际校验见[地址视图](../backend/users/views.py)。`auth/refresh/` 是保留的兼容路由。微信 code 换证、近期再认证及外部身份绑定/解绑属于待接入设计。

| 路径（省略公共前缀） | 方法 | JSON 或表单写入模型 |
| --- | --- | --- |
| `auth/csrf/` | GET | — |
| `auth/login/` | POST | POST LoginRequest |
| `auth/logout/` | POST | POST LogoutRequest |
| `auth/mini/login/` | POST | POST LoginRequest |
| `auth/mini/logout/` | POST | — |
| `auth/mini/refresh/` | POST | POST MiniRefreshInputRequest |
| `auth/password/change/` | POST | POST PasswordChangeRequest |
| `auth/password/reset/` | POST | POST PasswordResetRequest |
| `auth/refresh/` | POST | POST TokenRefreshRequest |
| `auth/register/` | POST | POST RegisterRequest |
| `auth/verifications/` | POST | POST VerificationRequest |
| `auth/web/refresh/` | POST | — |
| `health/` | GET | — |
| `regions/` | GET | — |
| `users/me/` | GET, PATCH | PATCH PatchedProfileUpdateRequest |
| `users/me/addresses/` | GET, POST | POST AddressInputRequest |
| `users/me/addresses/{address_id}/` | PATCH, DELETE | PATCH PatchedAddressWriteRequest |
| `users/me/addresses/{address_id}/default/` | POST | — |
| `users/me/coupons/` | GET | — |
| `users/me/phone/` | POST | POST PhoneBindRequest |
| `users/me/reviews/` | GET | — |

## 4. 商品、购物车、订单与模拟支付

商品列表支持 `q,category,min_price,max_price,sort` 和页码。分类筛选包含启用后代，排序使用 newest、price_asc、price_desc 或 title。购物车数量更新校验版本，游客合并与加购累加按原命令重试。试算可传一个 `user_coupon_id`，结果返回可用、不可用和已选券。订单明细读取成交快照。当前用户可查询已提交命令，动作名例如 `order.create` 或 `payment.simulate`。

| 路径（省略公共前缀） | 方法 | JSON 或表单写入模型 |
| --- | --- | --- |
| `carts/items/` | GET, POST | POST LineRequest |
| `carts/items/{id}/` | PATCH, DELETE | PATCH PatchedUpdateRequest |
| `carts/merge/` | POST | POST BasketRequest |
| `categories/tree/` | GET | — |
| `checkout/quote/` | POST | POST QuoteInputRequest |
| `operations/{operation}/{token}/` | GET | — |
| `orders/` | GET, POST | POST CreateRequest |
| `orders/{no}/` | GET | — |
| `orders/{no}/cancel/` | POST | POST CancelRequest |
| `orders/{no}/receive/` | POST | — |
| `orders/by-intent/{intent}/` | GET | — |
| `payments/` | POST | POST PayRequest |
| `payments/{no}/` | GET | — |
| `payments/{no}/simulate/` | POST | POST OutcomeRequest |
| `products/` | GET | — |
| `products/{id}/` | GET | — |
| `products/{id}/reviews/` | GET | — |

## 5. 券、评价、消息、CMS 与客服

- **券与评价**：领券校验有效窗口、余量、限领与幂等。已领券读领取时条款；评价按本人已完成订单项提交，同一订单项只能评价一次，公开评分取已通过审核的评价。
- **站内消息**：列表的 `read_watermark`、用户和分类绑定。批量已读提交 `{"watermark":"<read_watermark>","type":"order"}`（对应订单分类）；按 ID 已读提交 `ids`。翻历史页沿用首次列表上界。订阅登记返回 `delivery_status=not_sent`。
- **内容**：公开内容限定发布指针、展示端与有效时段；预览走运营授权接口。选择通知的公告在生效时由扫描器投递一次，撤回、过期或被替换的版本无投递。
- **客服**：历史与增量读取区分 direction、cursor 和 limit。首次发送与重试使用同一 `client_message_id` 和正文，已读使用本会话的消息 ID，关闭后需新开会话。

| 路径（省略公共前缀） | 方法 | JSON 或表单写入模型 |
| --- | --- | --- |
| `cms/announcements/{identifier}/` | GET | — |
| `cms/home/` | GET | — |
| `cms/pages/{identifier}/` | GET | — |
| `conversations/` | GET, POST | POST CreateInputRequest |
| `conversations/{id}/` | GET | — |
| `conversations/{id}/close/` | POST | POST CloseInputRequest |
| `conversations/{id}/messages/` | GET, POST | POST MessageInputRequest |
| `conversations/{id}/read/` | POST | POST SupportReadInputRequest |
| `coupons/` | GET | — |
| `coupons/{id}/claim/` | POST | — |
| `notifications/` | GET | — |
| `notifications/read/` | POST | POST ReadInputRequest |
| `notifications/subscriptions/` | POST | POST SubscriptionInputRequest |
| `notifications/unread-count/` | GET | — |
| `reviews/` | POST | POST SubmitInputRequest |

## 6. 运营接口

运营权限通过 Django Group/Permission 及服务端对象过滤校验。`catalog.manage_catalog` 允许维护商品与库存，`orders.fulfill` 允许发货，`support.reply` 和 `support.assign` 对应接待与分配，修改他人角色需要 `accounts.manage_roles`、版本及原因。只读审计要求 `audit.view`，可按 object_type、object_id、action、created_after、created_before 过滤，再按稳定顺序分页。媒体上传为 multipart 文件。

| 路径（省略公共前缀） | 方法 | JSON 或表单写入模型 |
| --- | --- | --- |
| `ops/audits/` | GET | — |
| `ops/categories/` | GET, POST | POST CategoryInputRequest |
| `ops/categories/{id}/` | PATCH | PATCH PatchedCategoryUpdateRequest |
| `ops/cms/` | GET, POST | POST ContentInputRequest |
| `ops/cms/{id}/` | GET | — |
| `ops/cms/{id}/draft/` | PATCH | PATCH PatchedRevisionInputRequest |
| `ops/cms/{id}/preview/` | GET | — |
| `ops/cms/{id}/publish/` | POST | POST PublishInputRequest |
| `ops/cms/{id}/unpublish/` | POST | POST PublishInputRequest |
| `ops/conversations/` | GET, POST | POST CreateInputRequest |
| `ops/conversations/{id}/` | GET | — |
| `ops/conversations/{id}/assign/` | POST | POST AssignInputRequest |
| `ops/conversations/{id}/close/` | POST | POST CloseInputRequest |
| `ops/conversations/{id}/messages/` | GET, POST | POST MessageInputRequest |
| `ops/conversations/{id}/read/` | POST | POST SupportReadInputRequest |
| `ops/coupons/` | GET, POST | POST DraftRequest |
| `ops/coupons/{id}/` | GET, PATCH | PATCH PatchedDraftPatchRequest |
| `ops/coupons/{id}/publish/` | POST | POST ActionRequest |
| `ops/coupons/{id}/stop-claiming/` | POST | POST ActionRequest |
| `ops/dashboard/` | GET | — |
| `ops/media/` | POST | POST MediaInputRequest |
| `ops/notification-templates/` | GET | — |
| `ops/notification-templates/{id}/` | GET, PATCH | PATCH PatchedTemplateVersionRequest |
| `ops/notification-templates/{id}/activate/` | POST | POST TemplateActivateRequest |
| `ops/order-activities/` | GET | — |
| `ops/orders/` | GET | — |
| `ops/orders/{no}/` | GET | — |
| `ops/orders/{no}/ship/` | POST | POST ShipRequest |
| `ops/products/` | GET, POST | POST DraftInputRequest |
| `ops/products/{id}/` | GET, PATCH | PATCH PatchedProductEditRequest |
| `ops/products/{id}/publish/` | POST | POST VersionInputRequest |
| `ops/products/{id}/unpublish/` | POST | POST VersionInputRequest |
| `ops/reviews/` | GET | — |
| `ops/reviews/{id}/moderate/` | POST | POST ModerateInputRequest |
| `ops/role-options/` | GET | — |
| `ops/roles/` | GET | — |
| `ops/skus/{id}/` | PATCH | PATCH PatchedVariantEditRequest |
| `ops/skus/{id}/stock-adjustments/` | GET, POST | POST AdjustmentInputRequest |
| `ops/users/` | GET | — |
| `ops/users/{id}/roles/` | POST | POST RoleUpdateRequest |

## 7. 错误处理与契约验收

| 响应 | 调用方应如何处理 |
| --- | --- |
| 401 / 403 / 404 | 401 按对应客户端协议刷新或登录；403 核对功能角色、CSRF/Origin 或演示开关；404 核对公开状态、编号和对象归属。 |
| 409 / 10008、10009、10010 | 依次对应版本冲突、操作处理中、幂等键异参。版本冲突取最新版本供用户核对；处理中原键重试并遵守 Retry-After；异参核对原请求记录。 |
| 409 / 40005、40006 | 报价发生变化或过期，重新试算并由用户确认。不得保留按钮上旧的应付金额提交新报价。 |
| 429 / 503 | 遵守退避提示，继续保留尚未确认的写入标识。排查限流、依赖健康和服务日志，向用户提供可恢复操作。 |

新增端点需同时验证成功、非法输入、功能权限、对象越权、幂等或版本冲突，以及前端未知结果恢复。字段细节见[序列化契约](openapi.yaml)，业务码见[错误常量](../backend/common/constants.py)，A1–A8 的联调复验见[独立验收](13-independent-acceptance.md)。
