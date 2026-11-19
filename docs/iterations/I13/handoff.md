# I13 交易异常恢复与可靠性收口 · 开发交接

- 交接日期：2026-11-19
- 当前状态：人工验收通过，待基线提交与标签
- 上一迭代基线：`iter-i12` → `60cbe64`，已闭环
- 本轮起始提交：`e8c81a0`
- 迭代计划：[plan.md](plan.md)
- 归档证据：[handoff 截图](screenshots/handoff.png)

## 1. 本轮要解决的问题

项目已有交易异常恢复实现与多层测试，本轮需要将这些能力转化为当轮可复验的证据，并检查尚未覆盖的异常边界。核心不是重复点击几个成功路径，而是确认响应未知、重复请求、状态竞争和 worker 异常时不会产生第二单、重复扣减/释放或错误状态。

## 2. 代码与业务边界

| 项目 | 本轮约定 |
| --- | --- |
| 后端 | 优先读取并验证 orders、cart、promotions、catalog 和通知事件实现；仅在确认缺陷时修改。 |
| Web / 小程序 | 可调整结果未知恢复、旧响应隔离和必要的回归断言；不改变交易语义。 |
| API / OpenAPI | 默认不变更；若缺陷修复涉及契约，必须同步 serializer、错误码、OpenAPI、客户端与测试。 |
| 数据 | 使用临时 MariaDB 和隔离账号；不重置现有开发库，不删除迁移。 |
| 实时与异步 | 保留数据库 Outbox 和现有扫描命令，不引入 Celery 或第二事件总线。 |
| 外部能力 | 不包含真实支付、微信工具/真机、Ubuntu 或规定性能验收。 |

## 3. 主要核对入口

- `backend/orders/services.py`、`backend/orders/models.py`、`backend/orders/tests/`
- `backend/cart/`、`backend/promotions/`、`backend/catalog/` 的事务与竞争测试
- `backend/orders/management/commands/process_order_events.py`
- `frontend/src/views/cart/CheckoutView.vue`、`frontend/src/views/orders/OrderDetail.vue`
- `frontend/e2e/acceptance.cjs`、`qa/windows/smoke.py`
- `qa/acceptance/mini-boundaries.cjs`：仅用于核对共享恢复语义，不作为微信真机证据

## 4. 故障注入清单

| 场景 | 故障/竞争 | 必须保持的结果 |
| --- | --- | --- |
| 报价 | 地址或券切换后旧报价迟到 | 旧响应不得覆盖当前选择；未匹配当前报价不能提交 |
| 下单 | 服务端已 201 创建，但客户端收到连接重置 | 查询原操作并找回同一订单，不创建第二单 |
| 幂等 | 同键同参重试、同键异参、新报价替换未知提交 | 同操作恢复；异参 409；未知提交不被新报价覆盖 |
| 支付 | 首次模拟失败、成功后重放、响应超时 | 失败可重试；成功只生效一次；超时查询原支付单 |
| 关单与取消 | 支付和超时/取消竞争、重复释放 | 只有一个合法状态转移；库存和券最多归还一次 |
| 履约 | 过期 `expected_version`、非法状态发货/收货 | 409 或明确拒绝，不产生错误履约记录 |
| Outbox | 消费失败、重复投递、worker 超时和重启 | 回执去重、后续补扫，不重复通知或释放 |

## 5. 验证命令

后端质量门禁：

```powershell
Push-Location backend
.\.venv\Scripts\python.exe manage.py check
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m black --check .
Pop-Location
```

客户端与完整隔离回归：

```powershell
npm --prefix frontend run lint
npm --prefix frontend run typecheck
npm --prefix frontend test
npm --prefix frontend run build
npm --prefix mini test
node --test qa/acceptance/mini-boundaries.cjs
.\backend\.venv\Scripts\python.exe qa/windows/smoke.py
```

若新增专项测试，应同时记录精确测试路径、环境、故障点和输出；SQLite 通过不能代替 MariaDB 竞争结论。

## 6. 缺陷与新增回归记录

| 编号 | 实际观测 / 覆盖缺口 | 处理 | 复验 |
| --- | --- | --- | --- |
| I13-01 | Web 支付成功响应丢失未覆盖 | 增加断连与原回执恢复，断言只 POST 一次 | 通过 |
| I13-02 | Web 取消响应丢失未覆盖 | 增加断连与原回执恢复，断言只 POST 一次 | 通过 |
| I13-03 | 支付成功×人工取消的 MariaDB 竞争未覆盖 | 新增 Barrier 并发测试，检查终态、Settlement 与库存流水 | 通过 |

中间失败：首次基线回归的客服分配提示等待超时；已增加诊断输出，第二次完整回归通过且未复现。未宣称修复客服生产缺陷，详见[验收记录](acceptance.md)。

## 7. 交接与回滚

接手人应先阅读 plan、验收记录和最终基线标签，再复现故障注入。若本轮引入回归，优先用新的 revert 提交恢复；不得清库、强推或移动已发布标签。

## 8. 当前交接状态

- plan、handoff、故障注入与新增回归已完成，详见[验收记录](acceptance.md)。
- 后端 99 passed/15 skipped、95.01% 行覆盖率；MariaDB 21 项、Web 20 项、mini 4+9 项及完整隔离回归通过。
- 人工验收人：项目用户（Trae 会话确认）；日期：2026-11-19；结论：通过。
- `iter-i13`：尚未创建；现在进入提交、推送和标签留证步骤。
