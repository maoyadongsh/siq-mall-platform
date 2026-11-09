# Ubuntu 24.04 原生部署与回滚

目标拓扑为 Nginx 提供 Vue 构建产物、媒体与 HTTPS 入口，Gunicorn 运行 Django，systemd 管理应用及订单扫描任务。Windows 已验证迁移、扫描和隔离数据库恢复，Ubuntu 实机结果由发布负责人登记在[验收台账](11-readiness-and-acceptance.md)。

## 准备系统与应用

选定并记录 MariaDB 系列，先用预发实例核对迁移及事务行为。准备专用域名、有效证书、数据库账户，以及数据库与媒体的可恢复副本。

```bash
sudo apt update
sudo apt install -y nginx mariadb-server redis-server python3.12 python3.12-venv git
id mall >/dev/null 2>&1 || sudo useradd -r -U -s /usr/sbin/nologin mall
sudo install -d -o mall -g mall /opt/mall /var/log/mall /var/lib/mall/media
sudo install -d -o root -g root -m 700 /etc/mall
```

将已审核代码发布至 /opt/mall（首次空目录可使用git clone；已有目录按版本发布流程处理）。创建数据库专用账号、启用Redis认证，限制两者监听本机；不要直接运行未替换密码的SQL示例。

```bash
cd /opt/mall/backend
sudo -u mall python3.12 -m venv .venv
sudo -u mall .venv/bin/pip install -r requirements.txt
if ! sudo test -e /etc/mall/backend.env; then
  sudo install -o root -g root -m 600 ../deploy/backend.env.example /etc/mall/backend.env
fi
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

## 启动应用并验证流量入口

在域名解析完成、有效TLS证书已安装后，编辑并安装部署模板：

```bash
sudo cp /opt/mall/deploy/mall-gunicorn.service.example /etc/systemd/system/mall-gunicorn.service
if ! sudo test -e /etc/nginx/sites-available/mall.conf; then
  sudo cp /opt/mall/deploy/nginx.mall.conf.example /etc/nginx/sites-available/mall.conf
fi
sudoedit /etc/nginx/sites-available/mall.conf
if [ ! -e /etc/nginx/sites-enabled/mall.conf ]; then
  sudo ln -s /etc/nginx/sites-available/mall.conf /etc/nginx/sites-enabled/mall.conf
fi
sudo nginx -t
sudo systemctl daemon-reload
sudo systemctl enable --now mariadb redis-server mall-gunicorn
sudo systemctl reload nginx
curl -f https://你的域名/api/v1/health/
sudo journalctl -u mall-gunicorn -n 100 --no-pager
```

证书路径必须真实存在，否则nginx -t不会通过；证书签发、续期和防火墙按部署环境配置并记录。验证 /admin/、首页深链接、HTTP重定向和503降级；生产 schema/docs应404。

## 启用扫描与验证业务恢复

Ubuntu 预发安装订单扫描单元。它与 Gunicorn 使用同一套代码、迁移、账号和环境文件。从项目根目录执行，先核对模板的代码路径和服务账号。

```bash
cd /opt/mall
sudo install -m 644 deploy/mall-orders.service.example /etc/systemd/system/mall-orders.service
sudo install -m 644 deploy/mall-orders.timer.example /etc/systemd/system/mall-orders.timer
sudo systemctl daemon-reload
sudo systemctl enable --now mall-orders.timer
systemctl list-timers mall-orders.timer
journalctl -u mall-orders.service -n 30
```


订单扫描命令逐批处理到期订单、履约动态与站内通知。核对 timer 的下次触发时间和 service 最近退出状态，在隔离库演练停机后补扫，核对释放的预占库存和消费回执。生产设置固定关闭模拟支付。Windows 的演示开关只用于隔离环境。

## 发布验收与回滚

| 检查 | 记录的证据 |
| --- | --- |
| 入口 | HTTP 跳转 HTTPS，证书链与续期，首页及前端深链接，静态文件及已上传媒体可读，生产模式下开发文档入口返回 404。 |
| 依赖与权限 | 健康探针正常为 HTTP 200，在隔离预发中模拟依赖中断时为 503。应用和扫描进程均使用同一配置、专用账号和版本。 |
| 数据恢复 | 同时备份 MariaDB 和持久媒体，在另一实例恢复。对照订单金额、库存、券状态、通知去重、媒体文件及权限，记录恢复点和耗时。 |
| 版本回退 | 记录旧代码与对应 dist、迁移清单和待处理事件。先暂停新写入口和相关消费者，确认旧版本兼容当前表结构，再切换代码及静态资源、启动扫描并复查积压。 |

保留订单、支付、券、客服和审计事实。历史迁移需要的数据回填及模块级注意事项见[总验收报告](12-final-acceptance.md)。Windows 上的四表计数抽查详见[独立验收](13-independent-acceptance.md)，异机恢复时间与媒体完整性仍需现场测量。
