# 2026-11-06 基础框架复验登记

执行者：AI。时区：Asia/Shanghai。人工验收人：待填写。
结论：本机自动检查和真实依赖探针通过；Ubuntu预发、浏览器交互及人工审核待补，不得登记为商业上线通过。

## 与后续验收的关系

本次证据用于 I01 的依赖探针、HTTP 协议、请求追踪和构建基线。下表的测试数量及 JS 体积均属于当日版本。后来加入商品、订单、运营页面和原生小程序后，测试集、路由和构建内容均已变化，比较构建体积时须固定入口及版本。后端、Web、MariaDB 和微信页面控制流的最近一次业务复验见[独立验收](13-independent-acceptance.md)，Ubuntu 部署演练入口见[发布手册](14-native-deployment.md)。

## 1. 本轮执行结果

| 检查 | 实测结果 | 范围 |
| --- | --- | --- |
| 基线pytest | 14 passed，原覆盖率97% | 旧口径包含测试代码 |
| 基线black | 7个文件需格式化，失败 | 已修正 |
| 修订后pytest | 20 passed in 0.82s；common 97.38% | 267语句、7未覆盖；排除测试/迁移，门槛80%；SQLite+内存缓存 |
| Django check | 0 issues | 本机开发配置 |
| ruff check . | All checks passed | 后端 |
| black --check . | 31 files would be left unchanged | 后端 |
| spectacular --validate --fail-on-warn | 退出0，无告警，输出openapi.yaml | 基础接口 |
| npm run lint | 退出0，无error | 前端 |
| npm run build | 成功，7.38秒，无500KB chunk告警 | 没有测量浏览器体验指标 |
| 真实数据库探针 | ok，11.84ms；MariaDB 11.8.3，utf8mb4 | 本机现有库，未代表Ubuntu/MySQL验证 |
| 真实Redis探针 | ok，69.41ms | 临时独立键SET/GET/DEL |
| manage.py migrate --check | 退出0 | 无待应用迁移；未执行新增迁移 |
| Git检查 | 当前目录不是Git仓库 | 无commit/diff基线 |

## 2. 前端构建体积

Vite日志单位KB，未压缩；不是网络测速。

| 项目 | 修改前 | 修改后 |
| --- | --- | --- |
| 入口JS | 1033.13 | 111.42 |
| 首页分块JS | 63.34 | 231.00 |
| 共享按钮JS | 包含于入口 | 59.93 |
| 全部JS分块合计（含404） | 1096.99 | 404.19 |
| 全部CSS合计（含404） | 362.82 | 79.80 |

全部JS减少约63.2%，CSS减少约78.0%。首页仍需加载页面与共享分块，不能声称整页只有111KB。未测真实LCP/INP。

## 3. 回归测试新增内容

backend/common/tests/test_foundation_regressions.py覆盖：并发探针独立键、异常信息不泄露连接凭据、429保留Retry-After、请求结束清除上下文、refresh轮换与旧token复用、OpenAPI健康503与refresh请求体。

新增测试初次执行的线程局部缓存代理和schema mock request夹具问题已修正，最终20项通过。

## 4. 新版任务验收登记

| 任务 | 已有证据 | 待补项 | 人工结论 |
| --- | --- | --- | --- |
| T01-01 配置 | check通过 | 生产启动 | 待验收 |
| T01-02 DB/Redis | 真实依赖探针、并发单测 | 目标生产系列与真实故障注入 | 待验收 |
| T01-03 API规范 | pytest通过 | 完整前端消费与401行为 | 待验收 |
| T01-04 日志 | request_id回归、生产日志配置 | 多worker与journald保留策略实机验证 | 待验收 |
| T01-05 JWT | 轮换与复用回归 | 登录注册属于I02 | 待验收 |
| T01-06 OpenAPI | 生成验证通过 | 预发路由404验证 | 待验收 |
| T01-07 Vue工程 | lint/build通过 | 并发401前端测试 | 待验收 |
| T01-08 状态页 | 保留已有界面，收紧HTTP状态范围 | 浏览器交互与移动视口复验 | 待验收 |
| T01-09 部署 | 模板/README修订 | 无Ubuntu目标，nginx/TLS/systemd未实测 | 待验收 |
| T01-10 交付登记 | 本文及设计文档 | G4/G5/G6未全部完成，不能关闭I01 | 待验收 |

## 5. 人工复验清单

1. Windows干净环境启动；访问首页/404/Swagger；测试环境停止Redis确认503后恢复。
2. 浏览器375/768/1440视口、键盘、控制台、断网重试，保留截图。
3. Ubuntu24.04验证nginx -t、systemd、真实HTTPS健康检查、Admin与前端深链接。
4. 生产schema/docs关闭、JSON日志、数据库备份恢复、代码回滚；逐条登记check --deploy告警。
5. 架构和新版迭代顺序人工审核，填写每项验收人、日期、结论。

人工验收人：____；日期：____；结论：____；整改复验：____。
用户明确无需代为上传作业系统，本轮仅交付本地文件。
