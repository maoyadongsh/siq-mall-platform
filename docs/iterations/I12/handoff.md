# I12 商城体验与可访问性收口 · 开发交接

- 交接日期：2026-11-19
- 当前状态：已闭环
- 起始基线：`eb5d526`
- 最终基线：`60cbe64`（`iter-i12`，已推送远端）
- 迭代计划：[plan.md](plan.md)
- 归档证据：[handoff 截图](screenshots/handoff.png)

## 1. 本轮要解决的问题

既有前端已完成整体视觉升级，但仍需用统一、可复现的走查矩阵验证 PC/H5 的响应式与可访问性，而不能仅凭构建成功或截图认定体验达标。本轮以“实际观测 → 最小修复 → 原路径复验 → 验收登记 → Git 基线标签”为唯一推进顺序。

## 2. 代码与业务边界

| 项目 | 本轮约定 |
| --- | --- |
| Web | 可修改 Vue 模板、SCSS/CSS、可访问名称和必要的浏览器断言。 |
| 后端 | 原则上不修改；若走查发现后端缺陷，先记录并重新评估范围，不夹带交易改造。 |
| API / OpenAPI | 不变更路径、字段、错误码或鉴权协议。 |
| 数据 | 不新增迁移，不重置业务库；集成验证使用隔离环境。 |
| 小程序 / 真机 | 不属于 I12，继续沿用现有待验状态。 |
| 后续迭代 | I12 人工签收、标签和截图闭环前不得启动 I13。 |

## 3. 预计涉及的入口

- `frontend/src/layouts/DefaultLayout.vue`
- `frontend/src/views/content/`、`frontend/src/views/catalog/`
- `frontend/src/views/cart/`、`frontend/src/views/orders/`
- `frontend/src/styles/` 与必要的页面 scoped 样式
- `frontend/e2e/`：仅在 DOM 或可访问名称变化时同步必要断言
- `docs/02-iteration-plan.md`、`docs/11-readiness-and-acceptance.md`
- `docs/iterations/I12/`：本轮独立档案

以上是需要核对的方向，不代表必须全部修改。先记录实际缺陷，再做最小变更。

## 4. 本地启动

```powershell
Push-Location backend
.\.venv\Scripts\python.exe manage.py runserver 127.0.0.1:8000
Pop-Location

Push-Location frontend
npm run dev -- --host 127.0.0.1
Pop-Location

Push-Location backend
.\.venv\Scripts\python.exe manage.py process_order_events --watch
Pop-Location
```

三个进程应分别在独立终端运行。需要模拟支付时，只在隔离开发环境启用 `DEMO_PAYMENT_ENABLED=1`；不得命中生产库或宣称真实扣款。

## 5. 走查与验证

### 浏览器矩阵

| 视口 | 重点 |
| --- | --- |
| 320 / 375px | 最窄布局、筛选项、金额与按钮换行、横向溢出 |
| 390 / 430px | 移动底栏、安全区、商品单列、固定操作栏遮挡 |
| 768px | 紧凑导航、双列内容与表格局部横滚 |
| 1440px | 桌面网格、信息层级、运营工作区和键盘路径 |

### 关键路径

1. 首页 → 商品列表 → 商品详情 → 选择规格 → 加购 → 购物车。
2. 登录合并 → 地址/优惠券 → 报价变化 → 提交结果找回。
3. 订单列表 → 订单详情 → 模拟支付/履约状态与异常恢复。
4. 运营工作台 → 商品管理 → 订单履约，检查权限内导航和窄屏操作。
5. 使用键盘检查主导航、表单、规格、数量、加购、结算与对话框焦点。

### 自动命令

```powershell
npm --prefix frontend run lint
npm --prefix frontend run typecheck
npm --prefix frontend test
npm --prefix frontend run build
```

涉及交易回归时，在仓库根目录运行：

```powershell
.\backend\.venv\Scripts\python.exe qa/windows/smoke.py
```

## 6. 缺陷与修复记录

走查后按“编号、环境、实际结果、期望结果、修复文件、复验结果”登记。没有实际观测的问题不写为已修复。

| 编号 | 环境与现象 | 处理 | 复验 |
| --- | --- | --- | --- |
| I12-01 | 390px 触控环境：认证输入容器 32px、输入本体 30px、协议复选框 32px | `AuthForm.vue` 补齐 44/42/44px 最小高度 | 通过 |
| I12-02 | 768px 紧凑导航：注册按钮 40px | `DefaultLayout.vue` 提升为 44px | 通过 |
| I12-03 | 认证输入框焦点外框被组件样式覆盖，按钮焦点色不统一 | `AuthForm.vue` 使用品牌 token 补充 3px 可见焦点 | 通过 |

## 7. 交接与回滚

接手人应先阅读 plan 和验收记录，再核对最终 commit。若本轮引入回归，优先用新的 revert 提交恢复；不得清库、删除迁移、强推或移动已发布基线标签。

## 8. 当前交接状态

- plan、handoff、走查和修复已完成，详见[验收记录](acceptance.md)。
- 前端 lint、typecheck、20 项 Vitest、生产构建及完整 Windows 隔离回归通过。
- 人工验收人：项目用户（Trae 会话确认）；日期：2026-11-19；结论：通过。
- `iter-i12` 已指向 `60cbe64` 并推送远端；[标签截图](screenshots/tag.png)已归档，I12 闭环。
