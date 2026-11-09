# siq-mall-platform 项目协作约定

本文件适用于仓库根目录及子目录。先遵守当前系统、开发者和用户指令，再应用本文件；更具体的子目录AGENTS在其范围内补充约定。用户后续明确授权实现时，按任务范围执行，不因本文件重复请求常规编辑许可。

## 1. 项目与当前状态

- 自营单商家电商演示产品，PC商城、移动H5、买家微信小程序共用后端；运营后台以PC为主。
- 当前已实现Web身份、地址管理及首批商品上架/展示流程。复验命令见README，当前证据见11§12，商品主图、SKU调价、库存调整与重放证据见11§13。I05 Web购物车与无券试算已实现，验证见11§14。I06 Web订单与模拟支付实现见11§15，下一开发批次为I07优惠券。I04分类、规模测试与人工审核仍待处理。
- 当前授权为按计划持续完成I02–I11后续开发，从I02开始逐迭代实施；缺外部条件的Ubuntu/微信平台/真机项目单独登记，不伪造通过。设计/评审任务只改相关文档，不擅自部署生产资源。
- 不上传作业系统；不发送邮件/消息、不发布或操作外部生产资源，除非用户明确要求。
- 不自动把自动测试通过写成人工验收通过，不伪造平台/真机/部署结果。

## 2. 先读哪些文件

1. `README.md`：目录、启动和验证命令。
2. `docs/07-predevelopment-handoff.md`：设计入口与实施边界。
3. `docs/01-architecture.md`：需求与技术约束，不包含迭代排期。
4. `docs/08-product-and-experience-spec.md`：三端页面、视觉与权限。
5. `docs/09-domain-and-data-spec.md`、`docs/10-target-api-contract.md`：规则、字段和目标契约。
6. `docs/02-iteration-plan.md`、`docs/11-readiness-and-acceptance.md`：当前任务、验收清单和台账。
7. 涉及移动/小程序时读`docs/06-mobile-wechat-design.md`；基础框架历史证据看`docs/05-review-validation-2026-11-06.md`。

按任务读取相关部分，不为简单改字遍历全部代码。文档与代码矛盾时先确定现状/目标，记录并同步修正；不得暗改公共协议。`docs/openapi.yaml`按当前实际路由生成并校验；10是包含未实现能力的目标契约，不能作为实现证明。

## 3. 固定技术与环境

- 开发Windows 11、PowerShell；生产Ubuntu 24.04，Nginx + Gunicorn + systemd原生部署。不要添加Docker/Kubernetes或容器依赖。
- 后端Python 3.12、Django 5.2、DRF、SimpleJWT、MariaDB/MySQL协议、Redis。MariaDB系列须在开发/预发明确验证；不能把协议兼容说成MySQL已测试。
- Web为Vue3、Vite、Router、Pinia、Axios、SCSS，Element Plus按需导入。现有JS保持可用，新业务按工具链准备逐步引入TS，不顺手全量重写。
- 小程序独立构建；原生或跨端框架须依据X01决策，不默认Vue DOM能复用。
- 异步业务需要时使用Celery/Redis和Outbox；Windows worker按已验证的WSL2方案，不能声称Gunicorn在原生Windows验证过。
- 保留`auth.User`并扩展Profile，不直接改AUTH_USER_MODEL，不清库/删迁移以解决用户模型问题。

## 4. 实施方式与命名

- 先定位任务ID、相关规则R/页面B/O/验收AT，再做最小完整变更。读取实际文件与最近状态，不凭文档猜测代码存在。
- HTTP视图/serializer处理输入输出；service承载权限内的业务命令和事务；selector负责查询。不要用signal隐藏下单、扣库存和支付核心动作。
- Python/JSON/DB字段snake_case，类PascalCase，常量UPPER_SNAKE_CASE；Vue组件PascalCase.vue，composable用useXxx，JS/TS内部camelCase。
- 新业务ID对外字符串；金额Decimal(12,2)，JSON两位字符串；业务时间UTC带时区，展示按用户时区。禁止浮点数计算最终应付。
- 不是所有表都继承带软删除的BaseModel；交易/流水/审计按数据模型保留。is_deleted不等于自动过滤，不依赖MariaDB部分唯一索引。
- 每次改契约同步serializer、错误常量、OpenAPI、客户端与相关测试。新增错误码先查重；未知可写字段拒绝，角色/价格/金额不能任意透传。
- 不引入未要求的微服务、搜索集群、AI功能或全套重构。依赖升级应有任务目的、兼容检查与锁文件；不只为“最新”升级。

## 5. 交易必须保持的不变量

- 数据库是库存、订单、券事实源，Redis不能单独防超卖/超发。
- 下单重读商品/地址/券/配送并试算；价格或履约信息变化要求用户重新确认；历史订单使用快照。
- 事务、锁顺序、条件更新和唯一约束遵循09；异常回滚无残留。支付不二次扣库存，取消只归还一次。
- Idempotency-Key与X-Request-ID分开。同键异参409；结果未知先查原操作；永久intent/业务流水唯一约束兜底，不能因短期幂等记录过期多建单。
- 订单仅pending→paid/canceled→相应后续合法状态；paid→shipped→completed。禁止暴露通用改状态/改金额接口。
- 仅隔离演示环境允许模拟支付，常规生产默认关闭；所有支付对象归属校验。不得开放无鉴权mock callback或宣称真实扣款/退款。
- Outbox与业务同事务，消费者业务与消费去重同事务；至少一次重试有扫描兜底，不仅靠on_commit唤醒。

## 6. 权限、敏感数据与平台边界

- Group/Permission与对象范围同时校验，is_staff不代表业务全权；对象越权404，功能无权403。前端隐藏按钮不是授权。
- Web目标access内存、refresh HttpOnly/Secure Cookie，配套CSRF/Origin与轮换；当前Web已接入该协议，旧token兼容路径需独立验证。小程序使用独立商城会话，平台登录态不是商城JWT。
- 密码、token、验证码、平台密钥不进日志/审计/分享链接。不要读取或打印真实`.env`，排障只检查必要变量是否设置并脱敏。
- 不按昵称/头像合并用户，外部身份绑定须验证账号与平台proof；拒绝地址/订阅等非必要能力应有回退路径。
- 上传校验真实内容、解码尺寸与大小；富文本白名单清洗，跨端只用允许的内容块。公开预览不得泄漏草稿。
- 不把浏览器模拟称为微信API、工具/体验版或真机测试；平台接口/权限接入前核查官方文档与实际账号能力。

## 7. 体验要求

- 沿用08中的暖白/深松绿token、字号、间距、状态色与44px触控目标；商城品牌组件与高密度运营布局分别设计。
- 同步检查PC/H5/小程序任务路径；移动端考虑安全区、键盘、页面恢复、分享冷启动，不能只缩小桌面布局。
- 每页有加载、空、失败、禁用/无权限、成功状态。失败保留输入；未知提交结果明确查询中；无虚构在线、已读、销量与经营指标。
- 消费者页面不暴露数据库/Redis/框架版本等实现细节。功能未开发时控制入口，不摆无法完成的购买动作。

## 8. 命令与验证

在根目录使用PowerShell，从对应目录执行；不覆盖已有`.env`，依赖安装遵循现有锁文件。先确认命令目标环境，不让测试命中业务生产库。

后端（工作目录`backend`）：

```powershell
.\.venv\Scripts\python.exe manage.py check
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m black --check .
.\.venv\Scripts\python.exe manage.py spectacular --validate --fail-on-warn --file ../docs/openapi.yaml
```

前端（工作目录`frontend`）：

```powershell
npm ci
npm run lint
npm run build
```

- 只改文档时检查内容、链接、任务映射；无需为文案跑全套业务测试或重生成OpenAPI。
- 后端变更运行相关测试和质量检查；契约变更重新生成/验证OpenAPI；前端变更lint/build并按风险验证交互。不要给可逆文案/样式改动增加只镜像实现的测试。
- 并发/事务必须目标MariaDB与Redis集成测试；SQLite/内存缓存只证明隔离单测。覆盖率公共模块≥80%，交易服务分支目标≥90%；覆盖率不替代状态/权限/幂等用例。
- 前端行为/E2E工具按计划引入；当前没有脚本就明确未建立，不编造`npm test`已通过。
- Ubuntu部署、TLS、备份恢复、版本回滚与真实设备验收分开记录。性能目标尚未实测，不以build成功宣称LCP/吞吐达标。
- 检查通过后不无理由反复扩测；新失败/新变更再补充。记录命令、环境、结果、限制和证据版本。

## 9. 工作区与交付

- 搜索优先rg；先查Git/文件状态，保留用户已有改动。无Git时用文件哈希记录基线，不声称有commit。
- Windows文件操作用原生PowerShell LiteralPath；递归移动/删除前验证绝对路径在目标范围内，不跨shell拼接删除命令。
- 不重置数据库、不删除迁移/用户文件、不强推、不部署真实环境来“验证修复”，除非任务明确包含并具备恢复方案。
- 代码实现后更新02/11中对应任务与验收证据；“设计完成”“实现完成”“自动验证通过”“人工验收通过”分别填写。
- 交付用中文说明改了什么、验证结果、未完成项；链接实际文件。重大设计变更记录ADR，并同步上下游契约；不用不必要的确认请求中断已经授权的可逆工作。
