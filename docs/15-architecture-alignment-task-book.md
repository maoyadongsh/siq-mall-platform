# SIQ优选商城技术架构对齐改造任务书

编制日期 2026-11-15 · 依据《3. 技术架构 / 3.1 技术栈》截图 · 对照代码基线 `17f5b91` · 执行后基线 `c323fbc`
性质：任务书，规定范围、任务、验收标准、风险与回滚；不是验收记录，不替代[11 验收台账](11-readiness-and-acceptance.md)与人工签收。

## 1. 背景与目标

目标技术栈截图（下称“目标栈”）与当前仓库在多数后端选型上已一致，但存在四类差异：

1. **功能级缺失**：目标栈要求 Channels + Daphne 承担客服聊天，当前为 HTTP 增量轮询。
2. **工程基线缺失**：目标栈要求前端全量 TypeScript、OpenAPI 3.1、Node 版本固定、CI 门禁；当前为纯 JS、OpenAPI 3.0.3、无 CI。
3. **选型不同但可用**：异步任务用数据库 Outbox 而非 Celery；数据库驱动用 PyMySQL 而非 mysqlclient；列表过滤手写而非 django-filter。
4. **部署与媒体形态不同**：静态/媒体由 Nginx 直接指向本机目录，无 WhiteNoise 与对象存储抽象。

本任务书的目标是：**把“不一致”变成“已实现”或“有 ADR 依据的明确偏离”**，每项改造独立可部署、可回滚、可复验，不重做已验收业务。

## 2. 改造原则与边界

- 遵守 [AGENTS.md](../AGENTS.md)：模块化单体、无 Docker/K8s、MariaDB 为事实源、迁移不清库、演示支付隔离。
- 不改变 F01–F11 的业务规则与对外语义；契约变化必须同步 serializer、错误常量、OpenAPI、三端客户端与测试。
- 每项任务沿用 [02](02-iteration-plan.md) 的状态流：待开始 → 开发中 → 自动验证通过 → 待人工验收 → 已验收，并逐项填写 G1–G6。
- “自动测试通过”不写成“人工验收通过”；Ubuntu、TLS、真机、性能与安全评审分别留证。
- **不在本次范围**：真实支付/退款/物流/对账、微信平台账号与真机接入、秒杀、多商户、微服务拆分。这些仍按 11/13 的独立待验项处理。

## 3. 差异台账

### 3.1 已对齐，无需改造

| 目标栈项 | 目标版本 | 当前实现 | 结论 |
| --- | --- | --- | --- |
| Python | 3.12.x | 3.12.8（项目 venv 实测） | 一致 |
| Django | 5.2 LTS | `>=5.2,<5.3` | 一致 |
| DRF | 3.16 | `>=3.16,<3.17` | 一致 |
| SimpleJWT | 5.5 | `>=5.5,<6.0`，含刷新轮换与黑名单 | 一致 |
| redis-py / django-redis | 5.x / 6.0 | `redis>=5,<7`、`django-redis>=6,<7` | 一致 |
| drf-spectacular | 0.28 | `>=0.28,<0.29` | 版本一致；规范版本待改，见 TA01-04 |
| Gunicorn | 23.x | `>=23,<24` | 一致（仅 WSGI；WS 另行部署，见 TA03-06） |
| pytest 系 | 8.x / 4.11 | `pytest>=8.3`、`pytest-django>=4.9`、`pytest-cov` | 一致 |
| Vue / Router / Pinia | 3.5 / 4.4 / 3.0 | 3.5.13 / 4.5 / 3.0.1 | 一致或更高 |
| Element Plus | 2.9 按需 | `^2.9.1`，按组件+样式手工引入 | 一致 |
| UI 策略 | 自研 + Element Plus | 商城品牌组件与运营组件分离 | 一致 |

### 3.2 改造项总表

| 编号 | 目标栈要求 | 当前实现与证据 | 差异性质 | 对应任务 |
| --- | --- | --- | --- | --- |
| D01 | Channels 4.2 + Daphne，Redis Channel Layer，仅客服聊天 | 客服为 5 秒轮询 [SupportChat.vue](../frontend/src/components/support/SupportChat.vue)，见 `setInterval(poll, 5000)`；[asgi.py](../backend/config/asgi.py) 仅占位；生产 WSGI Gunicorn | 功能缺失 | TA03 |
| D02 | Celery 5.5 + Beat 定时任务 | 数据库 Outbox + [process_order_events.py](../backend/orders/management/commands/process_order_events.py) + systemd timer；ADR05/09 已定 | 选型偏离 | TA01-01（决策）、TA05-01（文档） |
| D03 | TypeScript 5.6 全量，禁 any | 无 `tsconfig.json`、无 `vue-tsc`，源码全为 `.js/.vue`；ADR07 为“逐步引入” | 工程基线缺失 | TA02 |
| D04 | OpenAPI 3.1 | [openapi.yaml](openapi.yaml) 为 `3.0.3`；drf-spectacular 默认 3.0.3 | 规范版本差异 | TA01-04 |
| D05 | mysqlclient 2.2 连 MariaDB | PyMySQL 1.1 + `install_as_MySQLdb()`，[base.py](../backend/config/settings/base.py) 数据库段 | 选型不同 | TA04-01 |
| D06 | django-filter 25.x | 未安装，列表参数在 [catalog/views.py](../backend/catalog/views.py) 中手工解析 | 选型不同 | TA04-02 |
| D07 | WhiteNoise + 对象存储（可选） | 开发由 Django/Vite 代理，生产 Nginx `alias` 本机 `staticfiles`、`media`，[nginx 模板](../deploy/nginx.mall.conf.example) | 部署形态不同 | TA04-03、TA04-04 |
| D08 | Node 20 LTS + `.nvmrc` | 无 `.nvmrc`、无 `engines`；[01](01-architecture.md) §2 写 Node 24；Vite 7 要求 20.19+/22.12+ | 基线未固定 | TA01-03（含 Node 20 已 EOL 的决策） |
| D09 | Vite 6.x | Vite 7（更高，非缺陷） | 版本领先 | TA01-01（口径统一，不降级） |
| D10 | Pillow 11.x | Pillow 12（更高，非缺陷） | 版本领先 | TA01-01（口径统一，不降级） |
| D11 | factory_boy 8.x | 未安装，测试用 fixture | 工具缺失（可选） | TA04-05 |
| D12 | 单元/接口测试 | 已有 pytest、Vitest、Node Test、Playwright 冒烟 | 已具备 | 无需新增，仅接入 CI：TA01-05 |

## 4. 开工前必须锁定的决策

以下决策影响多个任务，未锁定不进入编码。建议值括号内。

| 决策 | 选项 | 影响 | 任务书默认 |
| --- | --- | --- | --- |
| **K1 异步与定时任务** | A. 保留 Outbox + systemd timer；B. 引入 Celery 5.5 + Beat；C. Outbox 继续承担交易事件，Celery 仅做非交易任务 | 交易可靠性、部署组件、测试面、监控 | **A（推荐）**，把 Celery 写成显式偏离；若选 C，需先证明两套投递不重复消费 |
| **K2 前端语言** | A. 全量 TS（ADR07 改为强制）；B. 仅新代码 TS，存量 JS 冻结 | 迁移工作量、契约类型收益 | **A（推荐）**，按 TA02 分批执行，不一次性重写 |
| **K3 Node / Vite 基线** | A. 保留 Vite 7 + Node 22/24 LTS，更新目标栈文档；B. 按截图降到 Vite 6 + Node 20 | 构建兼容、安全支持期 | **A（推荐）**：本机为 Node 24.13.1，Node 20 维护期已于 2026-04 结束，不降级；统一写 Node 24 LTS |
| **K4 数据库驱动** | A. 迁移 mysqlclient 2.2；B. 保留 PyMySQL 并写入偏离说明 | Windows 安装、MariaDB 回归成本 | **A**，但仅在 TA04-01 独立回归通过后合并 |
| **K5 媒体存储** | A. 仅做存储抽象，默认本地；B. 直接接入 S3/OSS | 部署复杂度、备份恢复目标 | **A**，生产切云存储另立任务 |
| **K6 OpenAPI 3.1** | A. 升级并接受 nullable/enum 表达变化；B. 维持 3.0.3 并记录偏离 | 客户端类型生成、文档工具兼容 | **A**，与 TA02-02 同期，避免二次生成 |

## 5. 任务分解

任务编号新增 `TA` 前缀，不复用 T/X/A/P/AT，避免与既有台账冲突。状态统一填在 11 新增登记节（TA05-02）。

### 5.1 M0 基线与依赖收敛（TA01）

| 任务ID | 工作内容与产物 | 依赖 | 通过标准 |
| --- | --- | --- | --- |
| TA01-01 | 版本矩阵与文档口径：按 K1–K6 结论更新 [01](01-architecture.md) §2、[README](../README.md)、ADR06/07/09；明确 Celery/Outbox 与 Node/Vite 的最终表述 | 决策锁定 | 文档中每个版本/选型与 `requirements.txt`、`package-lock.json`、实际运行版本逐项一致；偏离项均有 ADR 编号 |
| TA01-02 | 后端依赖锁定：生成可复现的锁文件（含哈希），区分开发/生产；固定 MariaDB 系列与驱动版本 | 无 | Windows 与 Ubuntu 干净环境按锁文件安装成功；`python -m pip check` 通过；不在锁文件外隐式升级 |
| TA01-03 | Node 工具链固定：`.nvmrc` 或 `engines`、README/01 同步；`npm ci` 在固定版本可复现 | K3 | 固定版本下 `npm ci && npm run build` 通过；`npm ls` 无 peer 冲突；文档不再出现两个 Node 基线 |
| TA01-04 | OpenAPI 3.1：设置 `OAS_VERSION=3.1.0`，重生成并用 `--validate --fail-on-warn` 校验；记录 nullable、枚举、`type` 数组等差异对客户端的影响 | K6 | `docs/openapi.yaml` 头部为 3.1.x；spectacular 校验零告警；差异清单附在任务记录；旧客户端兼容结论明确 |
| TA01-05 | CI 门禁：后端 `check/pytest/ruff/black/spectacular`，前端 `lint/typecheck/test/build`，小程序 `npm --prefix mini test` 与 `node --test qa/acceptance/mini-boundaries.cjs`；MariaDB 集成用自托管或临时实例单独 job | TA01-02、TA02-01 | 流水线可复现；失败即阻断；不含真实业务库凭据；缓存不掩盖锁文件变更 |

### 5.2 M1 前端全量 TypeScript（TA02）

| 任务ID | 工作内容与产物 | 依赖 | 通过标准 |
| --- | --- | --- | --- |
| TA02-01 | 工具链：TypeScript 5.6+、`vue-tsc`、`tsconfig.json`（`strict: true`、`noImplicitAny`）、ESLint TS 解析器；初期限定 `allowJs: true` 增量迁移 | TA01-03 | `npm run typecheck` 可运行；现有 19 项 Vitest、lint、build 全绿；严格模式无新增豁免 |
| TA02-02 | 契约类型：由 OpenAPI 生成 `src/types/api.d.ts`（`openapi-typescript` 或等价），加 `gen:api-types` 脚本；CI 校验生成结果与 `docs/openapi.yaml` 无漂移 | TA01-04 | 契约变更未重新生成时 CI 失败；API 层不再手写重复响应类型 |
| TA02-03 | 分层迁移：`utils`/`api`/`stores`/`router` → 布局与客服等公共组件 → `views`；每批独立提交，附行为回归结论 | TA02-01、TA02-02 | 每批 `lint + typecheck + test + build` 通过；不改变运行时行为；不顺手重构交易逻辑 |
| TA02-04 | 收口：关闭 `allowJs`，清理 `src` 下 `.js`（配置文件除外），启用 `no-explicit-any` | TA02-03 | `vue-tsc --noEmit` 0 错误；`src` 无 `.js`；`any` 仅为 0 或经批准的 `unknown` 收窄；构建产物体积记录并与改造前对比 |
| TA02-05 | 文档与 ADR：ADR07 改为“全量 TS”；补充类型边界（Decimal 金额为字符串、时间为 ISO 字符串、ID 为字符串）与生成流程 | TA02-04 | 新人可按文档从 OpenAPI 生成类型并通过 typecheck |

### 5.3 M2 客服实时化（TA03）

| 任务ID | 工作内容与产物 | 依赖 | 通过标准 |
| --- | --- | --- | --- |
| TA03-01 | 依赖与 ASGI：`channels` 4.2、`channels-redis`、`daphne`；配置 `CHANNEL_LAYERS`（独立 Redis DB/前缀）；`asgi.py` 改为 `ProtocolTypeRouter`（HTTP + WebSocket） | TA01-02 | `manage.py check` 零问题；Redis 不可用时健康探针与 WS 均给出明确失败，不静默降级为假在线 |
| TA03-02 | 握手鉴权：新增一次性 `ws-ticket`（Redis 短期有效，绑定用户、会话、来源），禁止 URL 携带 access token；校验 Origin；未授权用 4401/4403 关闭码 | TA03-01 | 过期/复用/跨用户 ticket 被拒；Web 与小程序各自取得 ticket；日志不含 ticket 与 token |
| TA03-03 | Consumer 与会话：复用 [support/services.py](../backend/support/services.py) 的 `authorize`/`conversation_data`；按会话 group 订阅；消息入库后 `transaction.on_commit` 投递；沿用 `conversation_seq` 单调 | TA03-01、TA03-02 | 越权订阅 404/关闭；关闭会话不可发送；重复 message id 只出现一条；事务回滚不投递 |
| TA03-04 | 一致性：保留 HTTP 历史接口与 `poll_cursor` 作为补拉与降级；客户端按 seq 去重；断线重连先补拉再订阅 | TA03-03 | 断线期间消息重连后无漏无重；乱序到达按 seq 归并；HTTP 与 WS 混用不产生重复气泡 |
| TA03-05 | 客户端接入：Web [SupportChat.vue](../frontend/src/components/support/SupportChat.vue) 与小程序 [support.js](../mini/pages/support/support.js)；指数退避、心跳、页面可见性暂停、错误态与“重连中”提示 | TA02-03（Web 侧）、TA03-04 | PC/H5/mini 三端收发自测通过；切后台/锁屏/弱网恢复有记录；失败保留输入 |
| TA03-06 | 部署与回退：Nginx `/ws/` Upgrade 与超时；Daphne 独立 systemd unit 或 ASGI worker；`SUPPORT_WS_ENABLED` 配置开关回退轮询；连接数、异常与关闭码指标 | TA03-05 | 预发环境实际建立 WS；关闭开关后 5 秒轮询正常工作；回滚步骤在 [14](14-native-deployment.md) 可执行 |
| TA03-07 | 验收扩展：AT19 增补实时场景，新增 AT25（见 §6） | 全部前置 | G1–G6 逐项记录；弱网与并发证据可复现 |

### 5.4 M3 数据访问、驱动与媒体（TA04）

| 任务ID | 工作内容与产物 | 依赖 | 通过标准 |
| --- | --- | --- | --- |
| TA04-01 | mysqlclient 迁移：替换 PyMySQL 与 `install_as_MySQLdb()`；补充 Windows 安装与 Ubuntu 构建说明 | K4、TA01-02 | 目标 MariaDB 全量集成用例通过（含并发/事务）；不再有“协议兼容等于已测 MySQL”的表述 |
| TA04-02 | django-filter 接入：`catalog/orders/reviews/audit` 列表改 FilterSet；保留现有错误结构与非法值 400；OpenAPI 查询参数同步 | TA01-04 | 现有列表筛选/排序/分页行为不变；非法 `min_price>/max_price` 等仍返回 400；前端错误提示回归通过；参数文档与实现一致 |
| TA04-03 | 媒体存储抽象：定义存储接口与本地实现，云存储作为可选实现；上传校验（类型/像素/大小/重编码）不变；签名 URL 与迁移脚本 | K5 | 本地与至少一个测试后端行为一致；草稿媒体不公开；历史路径可迁移；备份恢复步骤更新 |
| TA04-04 | 静态资源策略：在 WhiteNoise 与 Nginx alias 之间做 ADR，明确压缩、缓存头、部署命令与目录归属 | TA04-03 | 生产静态资源 404 为 0；缓存头符合版本化文件名；systemd/nginx 配置与文档一致 |
| TA04-05 | 测试工厂（可选）：引入 factory_boy，统一核心模型工厂；不改变业务语义 | TA04-02 | 新工厂可替代重复 fixture；现有测试不改断言仍通过 |
| TA04-06 | 回归与性能：驱动/过滤/媒体改动后执行 `qa/windows/smoke.py` 与 `qa/windows/scale.py`，与基线数字对比 | TA04-01–TA04-05 | 交易、运营、消息、客服路径冒烟通过；P95 不出现无解释回退；差异写入 11 |

### 5.5 M4 文档、登记与发布（TA05）

| 任务ID | 工作内容与产物 | 依赖 | 通过标准 |
| --- | --- | --- | --- |
| TA05-01 | 文档同步：01（技术架构、异步、客服）、06（客服实时状态机与降级）、08（客服体验）、09/10（契约）、11（ADR）、14（Daphne/WS/媒体/回滚）、README、openapi.yaml | 各里程碑完成 | 文档与实现无矛盾；所有偏离均有 ADR；不暗改公共协议 |
| TA05-02 | 验收登记：11 新增“架构对齐”登记节；12 总表补行；13 仅在复验时补记；逐项 G1–G6 | TA05-01 | 每项状态可追溯；自动结果与人工签收分开；证据含命令、环境、版本 |
| TA05-03 | 发布演练：Ubuntu 24.04 预发实际部署（TLS、Daphne、静态/媒体、回滚），记录 RPO/RTO 与失败复测 | TA03-06、TA04-04 | 报告而非配置截图；回滚到上一版本可执行；不宣称未测的负载指标 |
| TA05-04 | 人工签收：负责人、日期、结论、遗留项 | TA05-03 | 只有完成签收才把里程碑标为“已验收” |

## 6. 验收标准与公共门禁

### 6.1 新增/扩展验收用例

| 用例 | 覆盖 | 判定 |
| --- | --- | --- |
| AT25 实时客服 | TA03-01–06 | 双端实时收发；断线 30 秒内重连并补拉无漏重；越权订阅被拒；关闭会话不可发送；关闭开关后轮询可用；Redis 故障有明确错误态 |
| AT26 前端类型与契约 | TA02-01–05 | `vue-tsc` 0 错误；`any` 为 0；OpenAPI 变更未生成类型时流水线失败；构建与交互回归通过 |
| AT27 驱动与过滤 | TA04-01–02 | 目标 MariaDB 并发/事务用例通过；筛选/排序/分页与错误码不回归 |
| AT28 媒体与静态 | TA04-03–04 | 上传校验不变；草稿媒体不可公开；静态资源缓存头与 404 检查通过；恢复演练成功 |

### 6.2 公共门禁（每项均适用 G1–G6）

```powershell
# 后端（工作目录 backend）
.\.venv\Scripts\python.exe manage.py check
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m black --check .
.\.venv\Scripts\python.exe manage.py spectacular --validate --fail-on-warn --file ../docs/openapi.yaml

# 前端（工作目录 frontend）
npm ci
npm run lint
npm run typecheck   # TA02-01 起新增
npm test
npm run build

# 小程序与端到端（仓库根目录）
npm --prefix mini test
node --test qa/acceptance/mini-boundaries.cjs
.\backend\.venv\Scripts\python.exe qa/windows/smoke.py
```

- 交易/并发类改动必须使用目标 MariaDB 与 Redis 集成测试；SQLite 只证明隔离单测。
- 覆盖率维持公共模块 ≥80%、交易服务分支 ≥90%；不以覆盖率替代权限、幂等、状态机用例。
- 每项记录“通过/失败/不适用（原因）”，不得只写“完成”。

## 7. 交付物清单

| 类别 | 交付物 |
| --- | --- |
| 代码 | `backend/config/asgi.py` 与客服 consumer、`backend/common/` 存储抽象、前端 TS 源码与 `tsconfig`、`mini/pages/support/` 实时客户端 |
| 依赖 | 后端锁文件与新增依赖、前端 `package.json`/`package-lock.json`、`.nvmrc` |
| 契约 | `docs/openapi.yaml`（3.1）、生成的 TS 类型、错误码与过滤参数说明 |
| 部署 | `deploy/` 下 Daphne、Nginx WS、媒体/静态配置示例与回滚步骤 |
| 测试 | 新增/扩展 pytest、Vitest、Node Test、浏览器弱网与并发证据 |
| 文档 | 01、06、08、09/10、11（ADR 与登记）、12、14、README、本任务书状态更新 |

## 8. 风险与回滚

| 风险 | 触发点 | 缓解与回滚 |
| --- | --- | --- |
| WS 进程模型改变导致部署失败 | TA03-06 | 保留 `SUPPORT_WS_ENABLED` 回退轮询；Daphne 独立 unit 不影响现有 Gunicorn；Nginx 配置保留旧 `location /api/` |
| 消息重复或丢失 | TA03-03/04 | 以 `conversation_seq` 与 message id 去重；保留 HTTP 补拉；故障注入用例先行 |
| TS 迁移引入行为变化 | TA02-03 | 分批提交、每批回归；不夹带业务重构；保留改造前构建产物与测试基线 |
| OpenAPI 3.1 表达变化影响客户端 | TA01-04、TA02-02 | 先生成差异清单；同批更新生成类型与前端；校验旧客户端兼容 |
| mysqlclient 在 Windows 安装失败 | TA04-01 | 先验证 wheel 与编译路径；失败则回退 PyMySQL 并记录偏离，不半途合并 |
| django-filter 改变 400 语义 | TA04-02 | 保留自定义异常映射与契约测试；逐端点切换 |
| 媒体存储抽象引入回归 | TA04-03 | 默认仍为本地实现；云存储仅在测试后端验证；保留旧目录读取路径 |
| 无 CI 时门禁靠手工 | TA01-05 | CI 未落地前，每项交付附命令输出与版本；不得以“本地通过”替代流水线结论 |

## 9. 里程碑与放行

| 里程碑 | 任务 | 放行条件 | 状态 |
| --- | --- | --- | --- |
| M0 基线收敛 | TA01 | 决策锁定、锁文件、Node 基线、OpenAPI 3.1、CI 可用 | 自动验证通过；CI 托管实跑待验 |
| M1 前端 TS | TA02 | 全量 TS、类型生成接入、AT26 通过 | 自动验证通过；浏览器人审待验 |
| M2 客服实时 | TA03 | 三端实时与降级、部署回滚、AT25 通过 | 自动验证通过；真实 Redis/Daphne 联调与真机待验 |
| M3 数据与媒体 | TA04 | 驱动/过滤/媒体回归、AT27/AT28 通过 | 自动验证通过；MariaDB 专项与云存储待验 |
| M4 文档与发布 | TA05 | 文档同步、登记完整、预发演练、人工签收 | 文档与登记完成；预发与签收待验 |

里程碑之间可并行，但 **M0 的 OpenAPI 3.1 与 M1 的类型生成必须先于 M2 客户端改造完成**，否则 WS 客户端会基于过时契约实现。
