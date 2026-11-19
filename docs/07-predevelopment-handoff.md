# 项目设计与开发交接

首次建立 2026-11-09；架构对齐更新 2026-11-15。当前基线 `c323fbc`。适用于首次接手项目的开发、测试与评审人员。

先按[根 README](../README.md)启动应用。了解设计决策时查本页，将功能编号映射到实际代码、联调契约和验收记录。支付和物流履约使用隔离演示数据。

## 1. 阅读顺序与文档职责

| 文件 | 回答的问题 |
| --- | --- |
| [开发架构](01-architecture.md) | 系统需求、技术边界、命名、环境与质量标准是什么？不放排期 |
| [范围、页面与权限](08-product-and-experience-spec.md) | 谁在哪个端使用什么功能，页面如何操作，失败后怎么办？ |
| [规则与数据模型](09-domain-and-data-spec.md) | 金额、库存、订单、券如何保持一致，数据如何约束？ |
| [目标接口契约](10-target-api-contract.md) | 前后端按什么请求、响应和异常分工？字段与操作对照生成的 OpenAPI，平台扩展单列 |
| [开发准备与验收登记](11-readiness-and-acceptance.md) | 开工前解决什么、开发后如何验收、哪些外部条件尚缺？ |
| [迭代计划](02-iteration-plan.md) | 各阶段依赖、任务、部署验证和验收标准 |
| [移动端专项](06-mobile-wechat-design.md) | H5与小程序平台差异、授权、生命周期、真机要求 |
| [架构对齐任务书](15-architecture-alignment-task-book.md) | 本轮技术栈对齐的范围、决策、任务与验收标准是什么？ |
| [独立复验](13-independent-acceptance.md) · [原生部署](14-native-deployment.md) | 已有证据边界、Ubuntu/Daphne 部署与回滚怎么做？ |
| [项目AGENTS](../AGENTS.md) | 后续开发代理和协作者必须遵循的工程约定 |

架构管技术原则，08管产品范围与体验，09管业务语义与字段，10管HTTP边界，02/11管实施与证据，15记录本轮改造的范围与决策。修改规则时同步更新引用该规则的契约、任务和测试，不用“最新文件自动覆盖”掩盖矛盾。发生未解释的冲突应记录并解决后再实现相关部分。

`openapi.yaml`按当前实际路由生成并校验（OpenAPI 3.1，95 个路径、113 个操作），已包含客服 `ws-ticket`；前端 `src/types/api.d.ts` 由同一契约生成，禁止手写重复响应类型。10 继续作为目标设计与实现注记，不能据目标文档单独认定API存在；实现以路由、序列化器、测试和OpenAPI共同核对。

## 2. 已采用的设计决策

| 决策 | 本版设计基线 | 变更影响 |
| --- | --- | --- |
| 产品 | 单商家、人民币、实物商品、一个订单一次发货 | 多商户/拆单/售后另立设计 |
| 客户端 | PC商城、移动H5、买家小程序，共用后端；运营后台PC主用 | 小程序不是缩小的网页，也不承载完整运营后台 |
| 首版范围 | F01–F11全部纳入V1，按I01–I11逐步可部署 | 尚未进入对应迭代的功能隐藏入口，不放无效按钮 |
| 视觉 | 暖白、深松绿、低饱和辅助色；优先信息层次与可操作性 | 不以大面积金色、低对比灰字或装饰动效替代品质 |
| 用户 | 保留auth.User，一对一Profile；外部身份显式关联 | 不重建现有库、不直接替换AUTH_USER_MODEL |
| 交易 | 后端试算、数据库事务、订单快照、幂等与Outbox | Redis或前端状态不能决定交易成功 |
| 支付 | 仅隔离演示环境模拟；常规生产默认关闭 | 真实支付和退款不计入本轮完成度 |
| 部署 | Windows 11开发；Ubuntu 24.04原生部署 | 无Docker/Kubernetes |
| 前端 | 全量TypeScript（strict，禁止显式any），契约类型由OpenAPI生成 | 新增页面与接口必须通过`typecheck`；不退回JS |
| 实时客服 | Channels + Daphne + Redis Channel Layer；一次性`ws-ticket`子协议鉴权 | 发送、已读、历史仍走HTTP；断线回退轮询，`SUPPORT_WS_ENABLED=0`可回滚 |
| 数据访问 | mysqlclient 2.2；列表参数使用django-filter FilterSet | 驱动或过滤变更需重跑MariaDB并发与迁移用例 |
| 媒体与静态 | Django STORAGES可切换云存储；Nginx服务静态与`/ws/` | Gunicorn处理HTTP，Daphne处理WebSocket；媒体迁移另立任务 |

优惠券运营、CMS 发布、评价审核、消息中心与客服已接入各自业务接口。人工体验走查从真实路由进入；原型只用于追溯早期选择。

## 3. 已有原型与代码证据的边界

已有独立HTML原型：交易闭环V2、运营商品/履约V3、移动H5/小程序模拟V4。它们位于用户本机可视化目录，未纳入本仓库交付依赖；08/09/10给出可独立阅读的设计语义。原型示例数据不与真实数据库同步，原型中的平台授权不是微信实际能力测试。

[05验证报告](05-review-validation-2026-11-06.md)仅作为历史证据。I01可执行补验见11§8，I02 Web身份权限实现与验证见§10，后续业务证据见§12–22。I01–I11的可本地实现已累积完成，未删除既有用户模型或清库；Ubuntu、微信平台/真机、规定性能与人工验收仍待完成。

当前基线 `c323fbc` 已纳入架构对齐改造：前端全量 TypeScript、OpenAPI 3.1 与生成类型、客服 WebSocket、mysqlclient/django-filter、MariaDB CI 作业。自动验证结果见[11 §25](11-readiness-and-acceptance.md)；GitHub Actions 四作业（backend/frontend/mini/mariadb）通过，但 Ubuntu、真实微信设备、规定负载与人工签收仍未完成，不能把自动结果当作上线许可。

2026-11-19 从 `eb5d526` 启动 I12 商城体验与可访问性收口，独立交接见[I12 handoff](iterations/I12/handoff.md)，计划与验收入口见[I12 plan](iterations/I12/plan.md)。本轮实现、自动验证和用户人工验收已完成，当前进入基线提交与标签留证步骤；闭环前不启动后续迭代。

## 4. 从现有实现接手

1. **改页面**：先从 [Vue 路由](../frontend/src/router/index.ts) 或 [mini 页面清单](../mini/app.json) 找实际入口，再查 08 对应页面 ID 与 06 的生命周期要求。前端为 strict TypeScript，禁止显式 `any`；接口响应类型从 `src/types/api.d.ts` 引用，不要手写重复类型。
2. **改规则或接口**：从 [API 清单](openapi.yaml) 找方法与请求体，在对应 Django app 核对 serializer、service、模型约束。修改库存/金额/券规则时，同时验证下单、付款、取消与重放；接口变更后重新生成 OpenAPI 与前端类型，并同步 10 与相关测试。
3. **复验或发布**：以 [11 台账](11-readiness-and-acceptance.md) 对应任务为起点，核对 [13 独立复验](13-independent-acceptance.md)。Ubuntu 用 [原生部署手册](14-native-deployment.md)（Gunicorn + Daphne + Nginx `/ws/`），微信工具和真机用 [mini 指南](../mini/README.md) 登记。
4. **剩余工作**：对接微信身份与真实订阅渠道，执行设备和 Ubuntu 验收，按规定数据规模与负载补测，最后由相应负责人签收。

最小本地复验命令（仓库根目录）：

```powershell
Push-Location backend
.\.venv\Scripts\python.exe manage.py check
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m black --check .
Pop-Location
npm --prefix frontend run typecheck
npm --prefix frontend run lint
npm --prefix frontend test
npm --prefix frontend run build
npm --prefix mini test
node --test qa/acceptance/mini-boundaries.cjs
```

涉及 MariaDB 并发、事务或浏览器全流程时，再运行 `.\backend\.venv\Scripts\python.exe qa/windows/smoke.py`。该脚本使用临时 MariaDB 和本机 Chrome，不触碰现有业务库。

人工审核记录：产品负责人____；设计负责人____；技术负责人____；测试负责人____；日期____；结论/修改项____。

## 5. 需求到实施的追溯表

页面ID见08，规则见09，接口路径见10，验收用例见11；F01基础框架无需虚构买家业务页面。

| 需求 | 页面 | 核心规则 | API资源 | 实施任务 | 验收用例 |
| --- | --- | --- | --- | --- | --- |
| F01基础 | 框架/状态页/404 | 协议、追踪、部署 | health、auth/refresh | T01-01–10、X01 | AT01、AT21、AT23–24 |
| F02身份 | B08、O09 | R01、R17 | auth、users/me、ops/roles | T02-01–05、X02 | AT02–03、AT20 |
| F03商品 | B01–03、O02 | R03、R17 | categories、products、ops/products/skus | T04-01–05、X04 | AT05、AT21 |
| F04购物车 | B04–05 | R04、R06、R08 | carts、checkout/quote | T05-01–04、X04 | AT06–08 |
| F05交易 | B05–07、O03 | R05–09、R12、R17 | orders、payments、operations、ops/orders | T06-01–06、X05 | AT07–13、AT22 |
| F06用户中心 | B07、B09–10 | R01–02 | users/me、addresses、orders | T03-01–04、T06-06、X03 | AT03–04、AT13 |
| F07优惠券 | B05、B11、O04 | R10–12 | coupons、users/me/coupons、ops/coupons | T07-01–04、X05 | AT07–08、AT14–15 |
| F08评价 | B03、B12、O05 | R13 | reviews、products/id/reviews、ops/reviews | T08-01–04、X06 | AT16 |
| F09消息 | B13、O07 | R14 | notifications、ops/notification-templates | T09-01–04、X06 | AT17、AT20、AT22 |
| F10CMS | B01、B15、O06 | R15、R17 | cms、ops/cms | T10-01–04、X06 | AT18、AT21 |
| F11客服 | B14、O08 | R16–17 | conversations、ops/conversations | T11-01–05、X07 | AT19–24 |

F11 的实时推送通过一次性 `ws-ticket` 子协议连接 `/ws/support/{id}/`，发送、已读和历史仍走 HTTP；验收需覆盖断线重连、消息补拉与轮询回退。

O01工作台汇总已有权限内待办，随相关模块逐步接入；没有对应模块时不展示虚构待办。O09审计基础从I02建立，业务模块按R17补齐各自事件，不等到最终迭代再补交易审计。
