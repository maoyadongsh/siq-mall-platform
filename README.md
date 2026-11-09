# SIQ优选商城（siq-mall-platform）

Vue 3 + Django 5.2/DRF + JWT + MariaDB + Redis 在线电商工程。
Web 已接入身份、地址、商品运营、购物车、订单履约、优惠券、评价与站内通知。商城首页为商品列表，服务状态页位于 `/status`。授权运营人员可在 `/ops/products` 保存多规格商品草稿并上下架。环境为 Windows 11 开发、Ubuntu 24.04 原生部署。

买家可以从商品详情加购，在 `/cart` 合并游客选择、改量、移除和选中商品，再到 `/checkout` 选择地址并试算。游客清单使用当前标签页的 sessionStorage；账号购物车由服务端保存。首次启用前在目标开发库核对并应用 `cart.0001_initial` 迁移。报价有效5分钟。买家确认后创建订单，可从 /orders 找回待付款订单或查看履约进度。

开发入口见[设计交付总览](docs/07-predevelopment-handoff.md)和[AGENTS](AGENTS.md)。验收进度见[开发登记](docs/11-readiness-and-acceptance.md)。

商品管理页的“维护商品”支持替换主图、调整规格售价，以及按原因增减库存并查看流水。安装后端依赖后，应用 catalog.0002 迁移。Ubuntu 以 MALL_MEDIA_ROOT 指向持久媒体目录，随库备份并核对 Nginx 的 /media/ 目录映射。已有媒体的环境先迁移文件，再切换配置。

首次启用商品功能时，在目标开发库备份并核对迁移后执行下文的 migrate 步骤。通过受信任的管理员为运营账号分配 `catalog_operator` 组，重新登录后即可看到商品管理入口。

在 Windows 项目根目录运行 `backend\.venv\Scripts\python.exe qa/windows/smoke.py` 可复验地址并发、双标签刷新、商品上下架、购物车合并重试及结算变价。先完成前端 npm ci 与后端开发依赖安装。本机需装 Chrome 和 MariaDB 11.8，可用 SIQ_CHROME_PATH 与 SIQ_MARIADB_BIN 指定安装位置。脚本使用随机端口和临时数据目录。

| 文档 | 用途 |
| --- | --- |
| [开发架构](docs/01-architecture.md) | 需求、架构、API、字段、体验、测试与运维标准 |
| [迭代计划](docs/02-iteration-plan.md) | 11个可部署阶段、逐任务验收标准、登记模板 |
| [移动H5与微信小程序设计](docs/06-mobile-wechat-design.md) | 三端范围、平台差异、账号与生命周期、真机验收要求（设计阶段） |
| [设计交付总览](docs/07-predevelopment-handoff.md) | 开发前文件入口、范围决策与审核边界 |
| [页面、交互与权限](docs/08-product-and-experience-spec.md) | 三端功能、设计token、买家/运营页面及权限矩阵 |
| [规则与数据模型](docs/09-domain-and-data-spec.md) | 金额、状态机、事务、字段与唯一约束 |
| [目标接口契约](docs/10-target-api-contract.md) | 未来业务接口、字段、错误、联调样例，尚未实现 |
| [开发准备与验收台账](docs/11-readiness-and-acceptance.md) | 决策、准备任务、验收用例与逐任务登记 |
| [审查与优化建议](docs/04-project-review.md) | 代码证据、优先级、商业化缺口 |
| [本轮验证登记](docs/05-review-validation-2026-11-06.md) | 2026-11-06实际执行与待验收项 |
| [历史验收记录](docs/03-iteration-01-acceptance.md) | 旧版记录，不能替代本轮验证 |
| [OpenAPI](docs/openapi.yaml) | 按当前实际路由生成并校验；未实现目标契约见10 |

## 评价与审核

买家从已完成订单进入“评价商品与查看审核结果”，对每个订单项提交一次星级与文字。本人可在 `/account/reviews` 查阅待审状态和审核说明。公开的评价及平均星级出现在商品详情页。

升级前备份数据库并核对 `reviews.0001_initial` 后运行 migrate。由管理员将指定审核员加入 `review_moderator` 组，重新登录后进入 `/ops/reviews`。拒绝与隐藏需填写给买家的原因。回滚代码时先停用新入口并保留原始评价和审核记录，反向迁移会删除这些业务数据。

## 站内消息与通知模板

买家在 `/messages` 按订单、客服和系统分类查看通知，单条点击后标记已读，也可按当前服务端水位执行全部已读。水位之后提交的新消息保持未读，历史使用稳定游标加载。订单创建、模拟支付、取消、发货、收货及新评价审核结果由 `process_order_events` 独立消费投递；重复事件不会重复建消息，消费失败可在后续扫描补投。

授权内容运营进入 `/ops/notification-templates` 编辑模板。保存会产生未启用的新版本，只有核对服务端示例预览并启用后，后续事件才使用新模板。管理员为账号分配 `content_operator` 组后重新登录获得入口。`notifications/subscriptions/` 只登记一次微信订阅申请结果，不表示永久授权或实际送达；当前未接入微信发送。

升级前备份并核对 `content.0001_initial`、`reviews.0002_reviewaction_event_id` 和 `notifications.0001_initial`。通知迁移会将启用前的历史订单事件标记为已消费，避免集中补发旧消息；新审核动作才有通知事件标识。回滚代码时先停用消息入口和扫描器，保留消息、序号、模板、订阅结果及消费回执；反向迁移会删除这些记录，不应作为常规代码回滚步骤。

## 优惠券使用与运营

买家在 `/coupons` 领券，在 `/account/coupons` 查看券包。结算页显示可减金额与不可用原因；每单最多使用一张，仅抵商品金额。取消待付款订单后，仍在有效期内的券可再次使用。

在已有环境启用 I07 前先备份，核对并应用 `orders.0002_order_coupon_snapshot` 与 `promotions.0001_initial`。由受信任的管理员为营销人员分配 `promotion_operator` 组，重新登录后进入 `/ops/coupons`。先保存草稿，再核对时段、门槛、范围、总量及每人限领数后发布。停止领取只影响后续发放。订单扫描任务同时处理过期未用券。回滚前须处理占券中的待付款订单，保留券账、模板历史、订单快照与幂等回执。

## 订单演示与关单任务

首次启用 I06 前，在目标开发库备份并核对 `catalog.0003_sku_reserved_stock` 和 `orders.0001_initial` 后运行 migrate。在隔离的开发环境中设置 `DEMO_PAYMENT_ENABLED=1` 并重启后端即可演示付款成功或失败。生产 settings 始终禁用模拟支付。通过受信任的管理员为履约人员分配 `order_operator` 组，重新登录后进入 `/ops/orders`。买家在用户中心进入“我的订单与交易记录”。

待付款期限30分钟。Windows 一键启动脚本会另外启动扫描进程；手工启动时在 backend 目录运行：

```powershell
.\.venv\Scripts\python.exe manage.py process_order_events --watch
```

Ubuntu 预发安装订单扫描单元。它与 Gunicorn 使用同一套代码、迁移、账号和环境文件。路径与服务账号按实际环境核对：

```bash
sudo install -m 644 deploy/mall-orders.service.example /etc/systemd/system/mall-orders.service
sudo install -m 644 deploy/mall-orders.timer.example /etc/systemd/system/mall-orders.timer
sudo systemctl daemon-reload
sudo systemctl enable --now mall-orders.timer
systemctl list-timers mall-orders.timer
journalctl -u mall-orders.service -n 30
```

每次扫描先关闭到期订单，再分别投递履约动态、订单通知和评价审核通知。Windows 持续进程与 Ubuntu timer 均按5秒间隔扫描，正常链路目标10秒内到达；高负载与 Ubuntu 实机延时另行登记。异常记录保留并在后续扫描重试，履约投影与通知消费互不回滚。停机恢复后执行一次 `manage.py process_order_events` 即可补扫。回滚应用前先处理待付款订单和已预占库存，备份订单、支付及流水，再停用对应任务；反向迁移会丢失业务记录。

## Windows 11 启动

从项目根目录执行；Python 3.12，Node 24（Vite 7最低20.19+/22.12+）。

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
Copy-Item .env.example .env
```

编辑 backend/.env 的数据库和 Redis 连接。不要覆盖已有 .env。MariaDB 为原生 Windows 服务；Redis 可使用 WSL2 原生安装。先在数据库客户端创建 mall_db 和专用用户，参考 deploy/init_db.sql，执行前替换示例密码。PowerShell 不支持 bash 风格的 `< script.sql` 输入重定向，可在 MariaDB 客户端执行 `source E:/siq-mall-platform/deploy/init_db.sql`。

```powershell
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py runserver 127.0.0.1:8000
```

另一个终端从项目根目录执行：

```powershell
cd frontend
npm ci
npm run dev
```

打开 http://127.0.0.1:5173/ 。Vite 把 /api 代理至 8000。依赖正常 health 返回200；DB/Redis异常返回503且页面显示降级详情。SQLite仅供隔离单测，不能当作MariaDB集成验收。

## 验证

```powershell
cd backend
.\.venv\Scripts\python.exe manage.py check
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m black --check .
.\.venv\Scripts\python.exe manage.py spectacular --validate --fail-on-warn --file ../docs/openapi.yaml
cd ..\frontend
npm run test
npm run lint
npm run build
```

覆盖率排除测试/迁移代码，common 门槛80%。现有单测使用SQLite与内存缓存，真实DB/Redis及Ubuntu部署需另验。requirements为版本范围，生产发布前补精确锁文件与依赖审计。

## Ubuntu 24.04 原生部署

以下是待预发实测的部署步骤；域名、证书、密码、路径需要按实际环境填写。默认 apt 安装的 MariaDB 为10.11系列，若选11.4/11.8需使用匹配的官方仓库并在开发/预发统一验证，不能假设默认apt安装11.4。

```bash
sudo apt update
sudo apt install -y nginx mariadb-server redis-server python3.12 python3.12-venv git
sudo useradd -r -s /usr/sbin/nologin mall
sudo install -d -o mall -g mall /opt/mall /var/log/mall /var/lib/mall/media
sudo install -d -o root -g root -m 700 /etc/mall
```

将已审核代码发布至 /opt/mall（首次空目录可使用git clone；已有目录按版本发布流程处理）。创建数据库专用账号、启用Redis认证，限制两者监听本机；不要直接运行未替换密码的SQL示例。

```bash
cd /opt/mall/backend
sudo -u mall python3.12 -m venv .venv
sudo -u mall .venv/bin/pip install -r requirements.txt
sudo install -o root -g root -m 600 ../deploy/backend.env.example /etc/mall/backend.env
sudoedit /etc/mall/backend.env
```

环境文件是 systemd EnvironmentFile 格式，替换全部占位符；DJANGO_SETTINGS_MODULE=config.settings.prod，DJANGO_ENV=production。不要同时保留含生产凭据的 backend/.env。systemd由root读取600配置，再以mall运行程序。

迁移、静态收集和应用服务使用同一个环境文件，避免manage.py默认加载dev配置：

```bash
sudo systemd-run --wait --pipe --collect --uid=mall --working-directory=/opt/mall/backend --property=EnvironmentFile=/etc/mall/backend.env /opt/mall/backend/.venv/bin/python manage.py check --deploy
sudo systemd-run --wait --pipe --collect --uid=mall --working-directory=/opt/mall/backend --property=EnvironmentFile=/etc/mall/backend.env /opt/mall/backend/.venv/bin/python manage.py migrate --noinput
sudo systemd-run --wait --pipe --collect --uid=mall --working-directory=/opt/mall/backend --property=EnvironmentFile=/etc/mall/backend.env /opt/mall/backend/.venv/bin/python manage.py collectstatic --noinput
```

check --deploy 的告警逐条登记；SSL重定向由Nginx完成的应用层告警需以实际HTTP→HTTPS检查证明。前端在经过验证的构建机用 npm ci && npm run build，将 frontend/dist 上传同一路径；服务器不必安装Node。

在域名解析完成、有效TLS证书已安装后，编辑并安装部署模板：

```bash
sudo cp /opt/mall/deploy/mall-gunicorn.service.example /etc/systemd/system/mall-gunicorn.service
sudo cp /opt/mall/deploy/nginx.mall.conf.example /etc/nginx/sites-available/mall.conf
sudoedit /etc/nginx/sites-available/mall.conf
sudo ln -s /etc/nginx/sites-available/mall.conf /etc/nginx/sites-enabled/mall.conf
sudo nginx -t
sudo systemctl daemon-reload
sudo systemctl enable --now mariadb redis-server mall-gunicorn
sudo systemctl reload nginx
curl -f https://你的域名/api/v1/health/
sudo journalctl -u mall-gunicorn -n 100 --no-pager
```

证书路径必须真实存在，否则nginx -t不会通过；证书签发、续期和防火墙按部署环境配置并记录。验证 /admin/、首页深链接、HTTP重定向和503降级；生产 schema/docs应404。基础阶段不启动尚未实现的Celery服务。

发布前备份数据库与媒体，并在隔离库实测恢复；保留上一版代码与dist。数据库采用兼容迁移，回滚前核对迁移兼容性，不能仅切换代码后声称回滚成功。详细RPO/RTO与审查门槛见架构文档。
