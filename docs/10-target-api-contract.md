# 目标接口契约与联调样例

版本 v1.0｜2026-11-06｜目标设计；I02 Web部分已实现，实际可调用接口以openapi.yaml为准。

## 1. 基础协议与兼容

前缀`/api/v1/`，下表省略前缀；资源复数、尾斜杠。JSON字段snake_case，ID为字符串，金额固定两位十进制字符串，业务时间ISO8601 UTC。响应信封timestamp沿用现有带+08:00时区格式。

```json
{
  "code": 0,
  "message": "ok",
  "data": {"order_no": "D202611060001", "status": "pending"},
  "request_id": "trace-example-01",
  "timestamp": "2026-11-06T12:00:00+08:00"
}
```

成功查询/更新/动作200，创建201；删除返回200且data=null，保持信封；不要混入无响应体的204。错误data=null，字段错误`errors:[{field,detail}]`，非200HTTP表达失败。业务冲突需要新数据时客户端重新GET/quote，不把复杂业务实体塞进detail字符串。

页码协议与现有代码保持一致：请求`page`默认1，`page_size`默认20最大100（超过钳制）；data包含`count,page,page_size,total_pages,results`。商品、运营列表、个人订单使用此协议；订单可有创建时间上界筛选避免翻页漂移。聊天历史、通知流使用独立游标协议：请求`cursor,limit`，data为`results,next_cursor,has_more`，limit默认20最大100。游标不透明、绑定过滤条件与账号，由会话/收件人事务序号和ID生成，见09；不能静默切换同一接口协议。

`X-Request-ID`仅追踪。下表标记K的请求必须带`Idempotency-Key`（UUID文本，最长64字符），同键同参重放首次HTTP状态与业务结果，外层request_id使用当前请求。带V的编辑提交`expected_version`，旧版本409。GET不产生发货、标已读等副作用。

认证标记：A公开，U已登录且对象属本人，O指定运营权限+对象范围。所有U/O接口都校验session撤销和账号启用；client_type不参与授权。

本文件描述完整V1终态，各迭代只开放已实现契约：I05提供购物车/无券试算，I06增加订单和演示支付，I07再增加选券与券状态。未实现的能力不接受假成功、不显示可点击入口；保留字段在启用前必须明确不支持，不能静默忽略。新能力发布同步更新OpenAPI与客户端能力判断。

现有`GET health/`及`POST auth/refresh/`保持本期骨架契约；health依赖故障为HTTP503且code=0/data.status=degraded的已知特例。新增浏览器Cookie刷新走`auth/web/refresh/`，小程序走`auth/mini/refresh/`；旧JSON refresh路由仅在迁移过渡阶段保留，完成客户端迁移后按版本策略退役。不能直接把旧路由请求体改掉而让现有客户端崩溃。

## 2. 公共数据形状

| Schema | 必需字段 | 可选/只读字段 |
| --- | --- | --- |
| UserSummary | id, nickname | avatar_url, phone_masked, has_verified_phone；不得返回角色可写字段 |
| WebSession | access, access_expires_at, user | refresh通过HttpOnly Cookie设置，JSON不返回refresh；session_id可返回用于管理 |
| MiniSession | access, refresh, access_expires_at, refresh_expires_at, session_id, user | 客户端专用凭据；不返回微信session_key/app_secret |
| AddressInput | recipient,phone,province,city,district,region_code,detail | is_default默认false；编辑另带expected_version |
| Address | AddressInput + id,version | created_at,updated_at；仅本人或履约授权详情返回 |
| ProductCard | id,title,cover_url,min_price,currency,sale_status | 原价仅有真实依据时显示，不能伪造划线价 |
| ProductDetail | ProductCard + description_blocks,images,skus | skus含id,sku_code,spec_values,price,available_stock,enabled；不带内部采购成本 |
| CartItem | id,sku_id,quantity,selected,version,product_summary,current_price,availability | unavailable_reason；列表合计仅供浏览，提交必须quote |
| QuoteInput | items:[{sku_id,quantity}],address_id | user_coupon_id可为null；items 1–50，重复sku400 |
| Quote | quote_id,expires_at,items,goods_amount,freight_amount,discount_amount,payable_amount,currency,address_summary | selected_coupon,unavailable_coupons:[{id,reason}]；无效选择409，不静默忽略 |
| OrderSummary | order_no,status,goods_amount,freight_amount,discount_amount,payable_amount,currency,created_at,expires_at | allowed_actions数组；它优化UI但不能替代服务端权限检查 |
| OrderDetail | OrderSummary + items,address_snapshot,events | payment_summary,shipment,coupon_snapshot；全部来自订单快照 |
| UserCoupon | id,name,status,type,threshold_amount,valid_from,valid_until,scope_summary | reduction_amount或discount_bps/cap_amount，reserved_order_no；不可用原因 |
| Notice | id,type,title,body,target_type,target_id,created_at,is_read | read_at；目标仍需独立权限检查 |
| Conversation | id,status,created_at,updated_at | assigned_agent_display_name，last_message，unread_count；无在线状态则不显示 |
| ChatMessage | id,conversation_id,sender_role,client_message_id,body,created_at | 已读状态来自读水位，不由发送成功推断 |

字段长度、枚举、金额和唯一约束采用[09数据模型](09-domain-and-data-spec.md)。新增只读字段不得被PATCH写入，未知可写字段400；输出新增可选字段允许旧客户端忽略。枚举新增需有客户端未知值兜底，破坏性变更另开版本。

## 3. 身份、会话与用户

| 方法 / 路径 | 权限 | 输入 → data | 成功 / 关键异常 |
| --- | --- | --- | --- |
| GET `auth/csrf/` | A | 无→csrf_token；配套CSRF Cookie | 200；不返回认证身份 |
| POST `auth/register/` | A+CSRF | username,password,accepted_terms_version→WebSession | 201；用户名数据库唯一兜底，重复409；弱密码400 |
| POST `auth/login/` | A+CSRF | identifier,password→WebSession | 200；错误统一401不枚举账户；429 |
| POST `auth/web/refresh/` | Cookie+CSRF | 空JSON→access,access_expires_at；轮换Cookie | 200；失效/撤销401 |
| POST `auth/logout/` | U+CSRF(web) | scope=current/all→null | 200；本端清Cookie/凭据；全端撤销session |
| POST `auth/password/change/` | U | current_password,new_password→null | 200；校验失败400；修改后全部会话撤销并重新登录 |
| POST `auth/verifications/` | A或U按用途 | purpose,target→challenge_id,expires_at,retry_after_seconds | 201；限流429；注册/找回响应不泄露账户存在性 |
| POST `auth/password/reset/` | A | challenge_id,code,new_password→null | 200；无效/消费过/过期400；撤销已有会话 |
| POST `users/me/phone/` | U | challenge_id,code→UserSummary | 200；验证target归属，号码已绑定409 |
| POST `auth/mini/login/` | 平台凭据 | code,accepted_terms_version→MiniSession | 200；code仅后端向平台校验；无效401，能力不可用503 |
| POST `auth/mini/refresh/` | mini refresh | refresh→MiniSession | 200；轮换/撤销401 |
| POST `auth/reauth/` | U | password或challenge_id+code（二选一）→reauth_proof,expires_at | 200；短期一次性、绑定本人及用途；错误401 |
| POST `auth/identities/proofs/` | U+近期再认证 | provider=wechat,code,reauth_proof→proof_id,expires_at | 201；后端验证平台身份，不向客户端返回裸平台标识；冲突409 |
| POST `auth/identities/bind/` | U | provider=wechat,proof_id→绑定摘要 | 200；proof来自后端近期平台验证，冲突409；不接受裸openid |
| POST `auth/identities/unbind/` | U+近期再认证 | identity_id,reauth_proof→null | 200；解绑唯一可登录凭据409 |
| GET/PATCH `users/me/` | U | GET无；PATCH nickname/avatar_media_id→UserSummary | 200；禁止改phone/roles/is_staff/is_active |
| GET/POST `users/me/addresses/` | U | 列表/AddressInput→Address列表或Address | 200/201；超过20条409 |
| PATCH/DELETE `users/me/addresses/{id}/` V | U | PATCH AddressInput部分字段+expected_version；DELETE带expected_version→Address/null | 200；他人404；并发编辑409 |
| POST `users/me/addresses/{id}/default/` | U | 空JSON→Address | 200；重复设置无副作用；他人404 |

绑定流程限定：登录已有商城账号→近期验证该账号→获得当前微信身份的服务端proof→显式绑定；身份已归属另一账号时拒绝自动合并。V1不自动搬迁两账号的订单/券，提供清晰冲突解释。proof短期、一次性、绑定操作与当前用户。平台临时code不作长期凭据。

登录/注册/刷新Cookie目标为同源部署，Secure/HttpOnly/SameSite=Lax，Path覆盖认证接口；跨站部署需要单独设计。当前骨架未实现此方案，I02需前后端一起改造。跨标签刷新必须协调轮换，不能因并发请求把有效会话误踢出。挑战purpose只允许register/phone_bind/password_reset/reauth，分别校验上下文，生产禁演示验证码。

## 4. 商品、购物车与交易

| 方法 / 路径 | 权限 | 输入 → data | 成功 / 异常 |
| --- | --- | --- | --- |
| GET `categories/tree/` | A | 无→分类树 | 200，只有启用分类 |
| GET `products/` | A | q,category_id,sort,page,page_size→ProductCard页 | 200；排序仅price_asc/price_desc/newest；非法400 |
| GET `products/{id}/` | A | 无→ProductDetail | 200；下架/不存在404 |
| GET/POST `carts/items/` K(POST) | U | POST sku_id,quantity→CartItem；GET→items,version | 200/201；加购累加；限量409 |
| PATCH/DELETE `carts/items/{id}/` V | U | PATCH quantity/selected+expected_version→CartItem；DELETE expected_version→null | 200；版本409，对象404 |
| POST `carts/merge/` K | U | items:[{sku_id,quantity}]→items,adjustments,requires_confirmation | 200；达到数量/种类上限返回未合入明细，用户确认后单独修改；不能吞掉数据 |
| POST `checkout/quote/` | U | QuoteInput→Quote | 200；无效券/库存/地址变化409或404；不占库存 |
| POST `orders/` K | U | intent_id,quote_id→OrderDetail | 201；过期/变化409；同键重放原结果 |
| GET `orders/` | U | status,created_before,page,page_size→OrderSummary页 | 200，固定本人过滤 |
| GET `orders/{order_no}/` | U | 无→OrderDetail | 200/404 |
| GET `orders/by-intent/{intent_id}/` | U | 无→OrderDetail | 200；未成功建单404；路由优先于通用order_no匹配 |
| GET `operations/{operation}/{key}/` | U | 无→status,resource_type,resource_id,retry_after_seconds | 200；处理中也200；无记录404不表示安全更换键 |
| POST `orders/{order_no}/cancel/` K | U | reason枚举user_changed_mind/other→OrderDetail | 200；已取消返回当前结果，paid/shipped/completed409 |
| POST `orders/{order_no}/receive/` K | U | 空JSON→OrderDetail | 200；completed可重复，非shipped409 |
| POST `payments/` K | U | order_no→pay_no,status,amount,mode,expires_at | 201；非pending/已过期409；服务端取金额 |
| GET `payments/{pay_no}/` | U | 无→支付尝试摘要+order_status | 200/404 |
| POST `payments/{pay_no}/simulate/` K | U+演示开关 | outcome=success/failed→支付尝试摘要+order_status | 200；金额和订单内部校验，非法状态409；环境禁用403 |

operations的operation为后端白名单（如order.create），只能读本人的幂等状态；不能查询任意actor。此接口不返回完整请求、地址、token或审计内部结构。新quote在确认变化后意味着新请求：明确确认原请求被拒且未建单，才能换新intent/key；结果未知先查询原请求，不能直接新建一套键。

报价示例（下列均为data，外层信封略）：

```json
{
  "quote_id": "6b6092a4-87b9-4bcd-8d64-151c4d986e49",
  "expires_at": "2026-11-06T04:05:00Z",
  "currency": "CNY",
  "items": [{"sku_id": "101", "quantity": 1, "unit_price": "129.00", "line_amount": "129.00", "discount_allocated": "20.00"}],
  "goods_amount": "129.00",
  "freight_amount": "0.00",
  "discount_amount": "20.00",
  "payable_amount": "109.00",
  "address_summary": {"id": "12", "version": 2, "recipient": "演示用户", "phone_masked": "138****0000", "region": "演示地区"},
  "selected_coupon": {"id": "208", "name": "满129减20"},
  "unavailable_coupons": []
}
```

订单请求不提交金额、库存或订单状态：

```http
POST /api/v1/orders/
Authorization: Bearer <access>
Idempotency-Key: 019a51e3-78f0-7ac1-a6c3-573f961320ae
Content-Type: application/json

{"intent_id":"019a51e3-78f0-7ac1-a6c3-573f961320ae","quote_id":"6b6092a4-87b9-4bcd-8d64-151c4d986e49"}
```

目标冲突响应示例：

```json
{
  "code": 40005,
  "message": "报价已变化，请重新确认",
  "data": null,
  "errors": [{"field": "quote_id", "detail": "请重新试算并确认商品、配送与优惠明细"}],
  "request_id": "trace-example-02",
  "timestamp": "2026-11-06T12:00:06+08:00"
}
```

## 5. 优惠券、评价、消息、CMS与客服

| 方法 / 路径 | 权限 | 输入 → data | 关键标准 |
| --- | --- | --- | --- |
| GET `coupons/` | A | page/page_size→可领取模板页 | 不暴露领取用户；登录后可附本人限领情况 |
| POST `coupons/{id}/claim/` K | U | 空JSON→UserCoupon，201 | 库存/时间/限领409，重复键同一张券 |
| GET `users/me/coupons/` | U | status,page/page_size→UserCoupon页 | 占用、过期、不可用原因区分 |
| POST `reviews/` K | U | order_item_id,rating,content→评价，201 | 本人已完成；唯一评价409；待审不公开 |
| GET `users/me/reviews/` | U | page/page_size→本人评价及审核理由 | 不泄漏他人拒审理由 |
| GET `products/{id}/reviews/` | A | page/page_size→公开评价页+评分摘要 | 仅approved；用户名脱敏 |
| GET `notifications/` | U | type,cursor,limit→Notice游标页+read_watermark | 只本人；返回水位供全部已读 |
| GET `notifications/unread-count/` | U | 无→total,by_type | 可由事实表重建 |
| POST `notifications/read/` | U | ids数组（最多100）或watermark（二选一）→updated_count,unread_count | 同请求重复安全；水位签名绑定用户/筛选/时间上界；新消息不误读 |
| POST `notifications/subscriptions/` | U | provider,template_key,result,client_event_id→记录摘要，201 | 同事件去重；不采信客户端声明为无限发送许可 |
| GET `cms/home/` | A | platform=web/mobile/mini→已发布内容块/推荐 | platform只选展示，不绕过权限；下架商品从推荐排除 |
| GET `cms/pages/{slug}/` | A | 无→内容块、版本 | 未生效/下线404 |
| GET `cms/announcements/{id}/` | A | 无→公告 | 未发布404 |
| GET/POST `conversations/` K(POST) | U | GET本人会话页；POST可选order_no→Conversation | 201新建/200已有活动会话；关联订单必须本人 |
| GET `conversations/{id}/messages/` | U | cursor,limit,direction=older/newer→ChatMessage游标页 | 默认older向历史查；轮询用newer；稳定升序呈现，去重ID |
| POST `conversations/{id}/messages/` K | U | client_message_id,body→ChatMessage，201 | 1–2000字纯文本；同消息ID同内容重放、异内容409；关闭409 |
| POST `conversations/{id}/read/` | U | last_message_id→读水位 | 必须属于该会话且水位只前进 |
| POST `conversations/{id}/close/` K | U | reason→Conversation | 关闭与活动映射删除同事务，重复安全 |

## 6. 运营接口

所有路径在`ops/`下，列表默认页码分页；权限codename见[08权限矩阵](08-product-and-experience-spec.md)。编辑接口带V，动作含K；资源可见范围由后端查询强制限定。以下聚合行中的各方法必须分别生成OpenAPI，不能仅提供一个模糊“运营CRUD”接口。

| 方法 / 路径 | 权限 | 输入与返回要点 |
| --- | --- | --- |
| GET `ops/dashboard/` | 已授权运营 | 仅各自有权限的待办计数，不伪造经营指标 |
| GET/POST `ops/categories/`；PATCH `ops/categories/{id}/` V | catalog.manage | parent_id,name,sort_order,enabled；防分类环 |
| GET/POST `ops/products/`；GET/PATCH `ops/products/{id}/` V | catalog.manage | title,category_id,subtitle,description_blocks,media_ids；POST为draft；返回version |
| POST `ops/products/{id}/skus/`；PATCH `ops/skus/{id}/` V | catalog.manage | sku_code,spec_values,price,enabled；直接库存字段禁止PATCH |
| POST `ops/skus/{id}/stock-adjustments/` K,V | catalog.manage | delta,reason,expected_version→调整后库存/流水ID；不能负库存 |
| POST `ops/products/{id}/publish/`、`unpublish/` K,V | catalog.manage | expected_version,reason；检查可售SKU/媒体/价格，记录审计 |
| POST `ops/media/` | catalog.manage或content.publish | multipart file→asset_id,status；类型/大小错误400/413，未ready禁止引用发布 |
| GET `ops/orders/`、`ops/orders/{order_no}/` | orders.fulfill | 状态/时间/订单号筛选；列表脱敏，详情按履约用途展示 |
| POST `ops/orders/{order_no}/ship/` K,V | orders.fulfill | carrier,tracking_no,expected_version→OrderDetail；仅paid，重复原请求成功 |
| GET/POST `ops/coupons/`；GET/PATCH `ops/coupons/{id}/` V | promotions.manage | 类型、额度、范围、总量、限领、时段；只有草稿可改经济条款 |
| POST `ops/coupons/{id}/publish/`、`stop-claiming/` K,V | promotions.manage | expected_version,reason；发布校验、停领不作废已领券 |
| GET `ops/reviews/` | reviews.moderate | status,product_id,page→原文与必要订单项证据 |
| POST `ops/reviews/{id}/moderate/` K,V | reviews.moderate | action=approve/reject/hide,reason,expected_version；不收content/rating修改 |
| GET/POST `ops/cms/`；GET `ops/cms/{id}/`；PATCH `ops/cms/{id}/draft/` V | content.publish | kind,slug,blocks,start_at,end_at；独立草稿版本，不覆盖公开版 |
| GET `ops/cms/{id}/preview/` | content.publish | revision,platform→私有预览，无公开绕权token |
| POST `ops/cms/{id}/publish/`、`unpublish/` K,V | content.publish | revision,expected_version,reason；校验三端内容块，切换公开指针 |
| GET/PATCH `ops/notification-templates/{id}/` V；GET `ops/notification-templates/` | content.publish | 版本化编辑；支持变量白名单；PATCH产生新版本 |
| POST `ops/notification-templates/{id}/activate/` K,V | content.publish | version,expected_version→启用模板；预览校验成功方可启用 |
| GET `ops/conversations/` | support.reply或support.assign | 客服只看本人已分配；主管可看待分配及授权范围 |
| POST `ops/conversations/{id}/assign/` K,V | support.assign | agent_id,expected_version,reason→Conversation |
| GET/POST `ops/conversations/{id}/messages/` K(POST) | support.reply | 同买家消息形状；必须当前分配客服/额外授权主管 |
| POST `ops/conversations/{id}/read/`、`close/` K(close) | support.reply | 同水位/关闭协议；不得越权接管会话 |
| GET `ops/roles/`、`ops/users/` | access.manage | 用户必要身份摘要与角色；不含完整电话/地址 |
| POST `ops/users/{id}/roles/` K,V | access.manage | role_ids,expected_version,reason；禁止自助升权；撤销相关会话以刷新权限 |
| GET `ops/audits/` | audit.view | object_type/object_id/action/time/page，按模块与对象范围过滤 |

## 7. 错误码、事件与契约验收

现有错误码以`backend/common/constants.py`为准。下列编号为待实现新增预留，实施时必须先检查冲突、增加集中常量与测试，不能只在文档中生效。

| 新增码 | HTTP | 语义 / 客户端动作 |
| --- | --- | --- |
| 10008 VERSION_CONFLICT | 409 | 编辑版本过期，刷新并比较，不静默覆盖 |
| 10009 OPERATION_IN_PROGRESS | 409 | 带Retry-After，查询原操作后再重试 |
| 10010 IDEMPOTENCY_CONFLICT | 409 | 同键异参，不自动换键掩盖冲突 |
| 40005 QUOTE_CHANGED | 409 | 重新试算并明确确认 |
| 40006 QUOTE_EXPIRED | 409 | 报价超时，重新试算 |
| 40007 ORDER_EXPIRED | 409 | 订单支付期限已过，展示最新订单状态 |
| 20006 IDENTITY_CONFLICT | 409 | 外部身份/手机号已绑定，禁止自动合并 |
| 90003 CONVERSATION_CLOSED | 409 | 会话已关，用户选择新建 |

其他按现有常量：库存30002、不可用商品30001、券不可用60002、订单状态40003等。未知错误统一10006，不返回堆栈；401保留WWW-Authenticate，429保留Retry-After。环境禁模拟支付403不暗示已真实扣款。

领域事件：order.created、order.paid、order.canceled、order.shipped、order.completed、review.moderated、cms.published、support.message_created。统一含event_id、schema_version、aggregate_id、occurred_at、必要业务引用；不放token/完整地址。消费者重试至少一次、按(event_id,consumer)唯一；发送平台消息失败不能回滚已成立订单。

每个接口实施验收至少包括请求字段、成功信封、业务异常、认证/对象范围、幂等或版本冲突、分页/边界、文档与运行响应一致。OpenAPI必须覆盖状态码与示例；前端不能通过硬编码成功响应绕过尚未实现接口。旧客户端遇到新增字段可忽略，遇未知状态显示可理解说明并重新查询，禁止默认当成功。

### I04 首批可用接口（2026-11-08）

当前实现的完整字段以生成的 openapi.yaml 为准。GET regions/ 返回登录用户可选的省/市/区字典。GET products/ 与 products/{id}/ 公开可售商品及规格，列表支持 q、page、page_size。POST ops/products/ 接收 title、category（平面分类名称）、description 和 skus（label、price、available_stock），事务创建草稿及初始规格。上架/下架动作校验 catalog.manage_catalog 权限与 expected_version，并记录审计。当前动作使用版本冲突防止重复写入，完整的幂等响应重放、独立 SKU 编辑和媒体接口属于后续任务。

### 商品维护接口（2026-11-08）

运营权限沿用 catalog.manage_catalog。GET/PATCH ops/products/{id}/ 获取或修改标题、分类、描述、cover_id，写入带商品 expected_version。POST ops/media/ 接收 multipart 的 file，返回 ready 资源标识与规范化主图 URL。公开商品的可选 cover_url 为空时使用原布局。每件商品本阶段展示一张主图。

PATCH ops/skus/{id}/ 接收 label 或 price，附 SKU expected_version 和 reason。POST ops/skus/{id}/stock-adjustments/ 使用 SKU 版本、整数 delta、reason 和 UUID 格式的 Idempotency-Key。成功201返回流水 id、sku_id、操作者快照、调整前后数量、原因与时间。同一操作者原键原参数重放首次流水，同键不同参数409。GET 同路径以页码分页倒序查看人工调整历史。起始库存可见创建草稿时的审计快照。

### I05 Web 购物车与试算（2026-11-09）

carts/items/、carts/items/{id}/、carts/merge/ 和 checkout/quote/ 已接入，字段见生成的 openapi.yaml。累加与游客合并以账号、操作类型和 UUID 幂等键定位首次结果；合并失败的 SKU 返回原请求数量与原因。PATCH/DELETE 使用购物项版本。试算按实时价格、库存及本人有效收货地区执行，演示运费8.00、商品小计满129.00免运，报价有效5分钟。试算时不占库存。非空券ID及客户端自填应付金额均拒绝。

### I06 Web 订单与演示支付（2026-11-09）

第4节列出的 orders、payments、operations 与第6节 ops/orders 接口已接入，具体请求/响应见 openapi.yaml。业务号、报价及 intent 使用 UUID。各写接口验证 Idempotency-Key。短事务按用户串行写入，GET operations 仅返回已提交记录，读到404时仍须使用原意图与原键重试。锁竞争重试耗尽返回409、10009及Retry-After。下单响应未知时可用 orders/by-intent 找回订单。取消/超时释放可售库存，成功付款仅消耗预占。订单事件及其消费记录分别与业务和投影写入同事务。GET ops/order-activities/ 返回授权履约人员最近20条已投递动态。

I06 的配送与金额从服务端重算。订单四项金额以Decimal(12,2)保存并校验应付公式。商品、单价、主图、配送地址与履约记录按订单展示。不同于未来含券版本，本阶段优惠额为0。Windows 使用同一管理命令持续扫描，Ubuntu 使用 systemd timer 扫描数据库 Outbox。Celery 投递与订阅通知留给后续消费者；当前演示运行无需新增消息代理。

### I07 优惠券（2026-11-09）

第5、6节的优惠券中心、领券、本人券包、运营草稿维护、发布和停领接口已接入。权限为 promotions.manage，运营组为 promotion_operator。领取、发布及停领带 Idempotency-Key；模板修改与发布动作校验 expected_version。领取接口依赖限流时遇到Redis连接失败返回503，可持原键重试。已提交领取的重放返回首次领取结果，当前状态以本人券包为准。券包可按 unused/reserved/used/expired 筛选，占用和已用券带本人关联订单号。

checkout/quote/ 接受一个可空 user_coupon_id。响应包含 available_coupons、unavailable_coupons、selected_coupon，金额及各行 discount_allocated 均为两位小数字符串。结算列表优先展示最早到期的100张未用券，完整券包分页可达。主动选择的券即使在该列表之外仍单独验证。不可用选择返回409；他人持有的券返回404。用户需重新选择并确认当前应付金额。原无券报价仍可按原快照校验。

### I08 评价（2026-11-09）

reviews/ 的 POST 验证登录买家、本人已完成订单项、1–5星及去首尾空白后的1–500字。重复业务提交409，同键同参重放201；该订单项有评价后不能再修改原文。users/me/reviews/ 可按 order_no 筛选本人记录。ops/reviews/ 要求 reviews.moderate，支持 status、product_id 与页码；队列仅返回核查所需商品、订单项、数量、状态与审核信息。moderate/ 要求 Idempotency-Key 和 expected_version，拒绝/隐藏的原因必填，冲突返回409。审核动作及版本同事务留痕。

products/{id}/reviews/ 公开在售商品已通过的评价，返回页码分页结构，data.rating_summary.count 和 average 计算自所有已公开项。average 为保留一位小数的字符串；无公开评价时为null。公开作者统一标识为“已购用户”，订单号、用户标识、收货资料与审核原因不进入公开响应。


### I09 站内通知（2026-11-09）

`notifications/`、`notifications/unread-count/`、`notifications/read/` 与 `notifications/subscriptions/` 已接入，实际信封和字段以重新生成的 `openapi.yaml` 为准。通知列表使用绑定用户与分类的签名游标，按 `(recipient_seq,id)` 倒序翻历史；响应同时给出有时效、带用户与分类签名的 `read_watermark`。全部已读只更新该水位以内的未读事实，按ID已读最多100项，接口不读取或返回他人的消息。

订单事件与评价审核事件分别保留独立消费回执，回执、通知与收件人序号在同一事务提交。`process_order_events` 的履约动态投递和通知投递互不复用完成标记；一个消费者失败不会撤销另一个投影。持续扫描与 Ubuntu timer 的目标间隔均为5秒，正常链路目标为10秒内到达，实测值登记在11。启用通知迁移前的历史订单事件只补消费回执，不 retroactive 建消息。

`ops/notification-templates/` 要求 `content.publish`（运营组 `content_operator`）。PATCH 以 `expected_version` 创建未启用的新版本，不改变当前线上模板；activate 同时校验目标版本和当前启用版本，并要求 `Idempotency-Key`。标题与正文只支持事件白名单变量，缺少变量时消费者显式失败并等待配置修复后补投，不发送半成品。

订阅结果接口按用户、平台和 `client_event_id` 去重，返回 `delivery_status=not_sent`。accept 只代表一次授权结果，不是永久许可或实际送达证明；当前没有真实微信模板配置、发送接口或送达回执。


### I10 CMS 内容发布（2026-11-09）

`ops/cms/`、`ops/cms/{id}/draft/`、`preview/`、`publish/`、`unpublish/` 以及公开的 `cms/home/`、`cms/pages/{slug}/`、`cms/announcements/{id}/` 已接入，实际请求与响应以 `openapi.yaml` 为准。权限为 `content.publish`，运营组为 `content_operator`。公开内容只取已发布指针且满足 `start_at <= now < end_at` 的版本，并按 web/mobile/mini 展示端过滤；预览仅返回授权运营的指定草稿或历史版本。

保存草稿新增不可变 revision 并推进内容版本，不能透传状态或发布指针。发布与下线要求 `Idempotency-Key`、revision、expected_version，动作回执和操作审计同事务保存。内容标识创建后不可修改，避免草稿编辑改变既有公开链接。首页内容缓存最长60秒，发布/下线在提交后主动失效；推荐商品每次重新查询，下架或无可售库存的项不返回。无已发布首页内容时，`fallback_products` 返回真实可售商品。

内容块支持 heading/text/rich_text/image/link/product_list。富文本使用 nh3 白名单清洗，危险标签、事件属性、javascript/data/协议相对链接等直接拒绝；链接仅允许站内路径或HTTPS。图片复用 `ops/media/` 的真实解码、静态图片、5MB、2000万像素及重编码校验，内容运营与商品运营均可按权限上传。

公告 revision 的 `notify_inbox=true` 时，发布事务同时写唯一公告事件；扫描进程为每个活跃用户生成一条系统通知并保留消费回执。同一公告版本重复发布不新增事件，非公告不能开启联动。该动作只代表站内消息，不产生微信订阅授权或实际送达。


### I11 客服会话（2026-11-09）

`conversations/`、`conversations/{id}/messages/`、`read/`、`close/` 和对应 `ops/conversations/`、`assign/` 接口已接入，实际字段见 `openapi.yaml`。买家仅能访问本人会话；`support.reply` 只能读写已分配给当前客服的会话，`support.assign` 额外开放待分配与授权范围。运营组为 `support_agent` 和 `support_supervisor`。对象越权返回404，功能无权返回403。

活动会话由独立一对一映射保证每位买家最多一个，创建、关闭与映射变更同事务。消息在会话锁内分配 `conversation_seq`，同一会话、发送者和 `client_message_id` 唯一；同键同正文重放返回原消息，异正文409，关闭后新发送409。写操作同时要求 `Idempotency-Key`，创建、分配和关闭另有永久命令回执。

历史以签名 `(conversation_seq,id)` 游标区分 older/newer，返回升序消息、历史游标和轮询游标。买家与客服分别有只前进读水位，`counterpart_read_seq` 才用于“对方已读”，发送成功不产生已读或在线假象。关联订单只返回订单号、状态、金额和商品摘要，不返回地址快照。

客服回复的唯一事件UUID由 `process_order_events` 消费，为买家生成一条 support 类站内通知；重复投递与重放均不重复创建消息或通知。首版Web使用5秒HTTP增量轮询，隐藏页面不发送轮询请求。
