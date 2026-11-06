> 历史记录：本文件对应旧版计划。新版任务编号、验证结果和待审核结论见 [本轮验证登记](05-review-validation-2026-11-06.md)。原文验收状态不替代人工签字。

# 迭代一（基础框架）验收登记表

| 项 | 内容 |
| --- | --- |
| 迭代 | 迭代一 · 基础框架（F01） |
| 对应需求 | `docs/01-architecture.md` F01；`docs/02-iteration-plan.md` §2 |
| 交付日期 | 2026-11-05 |
| 交付人 | AI 生成（待人工审核） |
| 验收环境 | Windows 11 / Python 3.12 / Node 24 / Django 5.2 / DRF 3.16 / **MariaDB 11.8.3（本机实例，已迁移）** / Redis 7 |
| 验收结论 | **待人工审核**（14 项通过，1 项待补验：A01-15 Ubuntu 24.04 预发部署） |

---

## 1. 交付物清单

| 类别 | 路径 | 说明 |
| --- | --- | --- |
| 后端工程 | `backend/` | Django 5.2 + DRF，`config/settings/{base,dev,prod,test}.py` 分环境 |
| 公共基座 | `backend/common/` | 统一响应、异常、分页、request_id、日志、健康检查、错误码 |
| 前端工程 | `frontend/` | Vue 3 + Vite 7 + Router + Pinia + Element Plus + Axios |
| 部署样例 | `deploy/` | Nginx、Gunicorn systemd、生产环境变量、Win11 启动脚本 |
| 说明文档 | `README.md` | 开发启动、接口一览、生产部署、迭代边界 |

---

## 2. 任务完成情况

| 任务 | 状态 | 证据 |
| --- | --- | --- |
| T01-01 后端工程初始化 | 已验收 | `python manage.py check` → `System check identified no issues (0 silenced)` |
| T01-02 环境与连接配置 | 已验收 | 已用本机 MariaDB 11.8.3 实例完成连接与迁移；dev/prod/test 三套配置可加载；生产强制校验 `SECRET_KEY`/`ALLOWED_HOSTS`；无硬编码密钥 |
| T01-03 统一响应与异常 | 已验收 | 见 §3 实测记录；`common/tests/test_response.py`、`test_exceptions.py` |
| T01-04 分页与基础模型 | 已验收 | `page_size=500` 被钳制为 100；`BaseModel` 提供 `created_at/updated_at/is_deleted` |
| T01-05 request_id 与日志 | 已验收 | 响应头与响应体 `request_id` 一致；日志为 JSON 单行且含 `path/method/status/duration_ms` |
| T01-06 JWT 基座 | 已验收 | 黑名单表迁移成功；非法 refresh 返回 401 + `code=20004`（非 500） |
| T01-07 健康检查接口 | 已验收 | DB/Redis 正常 → 200 + `status=ok`；注入故障 → 503 + `status=degraded` |
| T01-08 接口文档 | 已验收 | `/api/v1/docs/` 200、`/api/v1/schema/` 200 |
| T01-09 前端工程初始化 | 已验收 | `npm install` + `npm run build` 成功产出 `dist/` |
| T01-10 请求层与布局骨架 | 已验收 | token 注入、`code≠0` 统一提示、401 单次刷新重放、布局与 404 页 |
| T01-11 前后端联调 | 已验收 | `http://localhost:5173/api/v1/health/` 200 且返回 `status=ok`（Vite 代理生效） |
| T01-12 部署与启动说明 | **待验收** | Win11 已按 README 跑通；Ubuntu 24.04 预发环境未实测（见 L1） |

---

## 3. 验收清单实测记录

| 序号 | 验收项 | 标准 | 实测结果 | 结论 |
| --- | --- | --- | --- | --- |
| A01-01 | 后端可启动 | 启动成功、无 error | `runserver` 启动成功，访问接口正常 | 通过 |
| A01-02 | 数据库连通 | `migrate` 全部成功、库为 utf8mb4 | MariaDB 11.8.3 上 `mall_db`（utf8mb4_unicode_ci）迁移全部 OK，库内 12 张表 | 通过 |
| A01-03 | 缓存连通 | `redis.status=ok` 且 SET/GET 成功 | 本机 Redis 7 实测 `status=ok`（健康检查内部完成 SET/GET/DEL） | 通过 |
| A01-04 | 统一响应 | 成功/失败结构符合规范 | 成功 5 字段；失败含 `code≠0` 与 `errors`（字段缺失场景实测） | 通过 |
| A01-05 | 异常处理 | 未捕获异常 → 500/10006，无堆栈 | `handler500` 单测通过；响应体不含堆栈/SQL | 通过 |
| A01-06 | 参数校验 | 404→10004、405→10007 | 405 实测 `code=10007`；404 统一 JSON 仅在 `DEBUG=False` 生效（见 L2） | 部分通过 |
| A01-07 | request_id | 透传/生成一致、可检索 | 传入 `selfcheck123456` → 响应头与 `request_id` 相同；非法值 → 生成 16 位十六进制 | 通过 |
| A01-08 | 日志规范 | 按天 JSON、含 request_id/path | `logs/app.log` 单行 JSON：`level/time/logger/request_id/message/path/method/status/duration_ms` | 通过 |
| A01-09 | 健康检查 | 正常 200/ok；故障 503/degraded | 实测 200 + `status=ok`；`database` 18.74ms、`redis` 17.58ms，均 ok | 通过 |
| A01-10 | 接口文档 | docs 可访问并能调用 | `/api/v1/docs/` 返回 200；OpenAPI JSON 可生成 | 通过 |
| A01-11 | 前端可构建 | build 成功、产物存在 | `vite build` 成功；`dist/index.html` 存在；产物无 `localhost` 硬编码（baseURL 走 `/api/v1`） | 通过 |
| A01-12 | 前端联调 | 状态卡片与后端一致 | 浏览器实测：首页「服务状态」卡片显示整体状态「正常」，数据库与 Redis 均「正常」 | 通过 |
| A01-13 | 代码规范 | ruff/eslint 零 error | `ruff check .` → All checks passed；`eslint .` 无输出（0 error） | 通过 |
| A01-14 | 测试 | 三类接口测试通过、覆盖率 ≥70% | `pytest` → **14 passed**，`common` 覆盖率 **97%** | 通过 |
| A01-15 | 独立部署 | Win11 + Ubuntu 各一次 | Win11 已完成；Ubuntu 24.04 未执行 | **待补验** |

---

## 4. 关键命令与输出摘录

```text
> python manage.py check
System check identified no issues (0 silenced).

> python -m pytest
14 passed  —  common 覆盖率 97%

> mysql -u root -p -e "CREATE DATABASE mall_db ..."
version: 11.8.3-MariaDB
mall_db | utf8mb4 | utf8mb4_unicode_ci

> python manage.py migrate --noinput      （DB_ENGINE=mysql，指向本机 MariaDB）
Applying contenttypes.0001_initial... OK
...
Applying token_blacklist.0013_alter_blacklistedtoken_options_and_more... OK
（mall_db 内共 12 张表）

> ruff check .
All checks passed!

> npm run build
✓ built in ...  (dist/index.html 已生成)

> curl http://127.0.0.1:8000/api/v1/health/
HTTP 200
{"code":0,"message":"ok","data":{"service":"mall-api","version":"1.0.0",
 "environment":"development","status":"ok",
 "checks":{"database":{"status":"ok","latency_ms":18.74,"detail":""},
           "redis":{"status":"ok","latency_ms":17.58,"detail":""}},
 "server_time":"2026-11-05T10:06:05+08:00",
 ...}}

> POST /api/v1/auth/refresh/  {"refresh":"bad-token"}
HTTP 401  {"code":20004,"message":"refresh 已失效，请重新登录", ...}

> POST /api/v1/auth/refresh/  {}
HTTP 400  {"code":10001,"message":"参数校验失败","errors":[{"field":"refresh", ...}]}

> curl http://localhost:5173/api/v1/health/     （Vite 代理 → Django）
HTTP 200  status=ok
```

---

## 5. 遗留问题与整改项

| 编号 | 问题 | 影响 | 整改方式 | 复验 |
| --- | --- | --- | --- | --- |
| L1 | Ubuntu 24.04 预发环境尚未部署 | A01-15 未闭环 | 在预发按 README §4 执行一次 Nginx + Gunicorn 部署并访问健康检查 | 待复验 |
| L1-a | ~~本机无 MariaDB，迁移只在 SQLite 自检库验证~~ | ~~A01-02 未闭环~~ | **已整改**：本机 MariaDB 11.8.3 建库 `mall_db`（utf8mb4_unicode_ci），`migrate` 全部通过，健康检查 `database.status=ok` | **已复验** |
| L2 | 开发环境 `DEBUG=True` 时，未匹配路由返回 Django 技术 404 页面而非统一 JSON | 仅影响开发体验，生产 `DEBUG=False` 已统一 | 保持现状；如需开发期统一，可在 dev 中覆写 `handler404` 行为 | 已记录 |
| L3 | Element Plus 全量引入，产物体积偏大（构建有 chunk 体积提示） | 首屏加载可优化 | 迭代三引入商品页时改为按需引入（`unplugin-vue-components`） | 迭代三 |
| L4 | 前端暂无登录页，`401` 刷新失败时仅提示"登录已过期" | 迭代一不含业务，无影响 | 迭代二补登录页后跳转登录 | 迭代二 |

---

## 6. 人工审核意见

| 审核环节 | 审核人 | 结论 | 意见/整改要求 | 日期 |
| --- | --- | --- | --- | --- |
| R1 代码评审 | 　 | ☐ 通过 ☐ 整改 ☐ 不通过 | 　 | 　 |
| R2 安全审核 | 　 | ☐ 通过 ☐ 整改 ☐ 不通过 | 　 | 　 |
| R3 接口联调 | 　 | ☐ 通过 ☐ 整改 ☐ 不通过 | 　 | 　 |
| R4 数据审核（迁移/索引/字符集） | 　 | ☐ 通过 ☐ 整改 ☐ 不通过 | 　 | 　 |
| R5 测试审核 | 　 | ☐ 通过 ☐ 整改 ☐ 不通过 | 　 | 　 |
| R6 上线评审 | 　 | ☐ 通过 ☐ 整改 ☐ 不通过 | 　 | 　 |

> 依据 `docs/02-iteration-plan.md` §13.1：**未登记 = 未验收**；L1 复验通过后，本迭代方可标记为「通过」并进入迭代二。

