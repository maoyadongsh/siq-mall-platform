# SIQ优选商城（siq-mall-platform）

Vue 3 + Django 5.2/DRF + JWT + MariaDB + Redis 在线电商工程。
当前交付：I01基础框架及I02 Web身份权限实现，尚无已验收业务模块或小程序客户端。Windows 11 开发，Ubuntu 24.04 直接部署，不使用 Docker。

开发前先读[设计交付总览](docs/07-predevelopment-handoff.md)与[AGENTS.md](AGENTS.md)。I01/I02自动验证结果见[准备与验收登记](docs/11-readiness-and-acceptance.md)，历史测试报告不作为当前通过证据；后续按迭代计划实施I03–I11。

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
sudo install -d -o mall -g mall /opt/mall /var/log/mall
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
