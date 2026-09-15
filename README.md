# Student Helper

Student Helper 是一个面向北航学生的轻量化成绩计算工作台。它把软件学院 2024 级推免平均学分绩点规则录成结构化规则，并提供北航统一认证、本人历史成绩同步、成绩筛选、手工修正、方向课选择、情景测算和响应式界面。

未连接学校账户时默认使用脱敏演示数据。用户主动连接后，密码只用于当次 SSO 交换；学校 Cookie 只保存在后端内存，不写入浏览器或数据库。

## 已完成

- 软件学院 2024 级推免规则 A–F 分组和全部课程代码。
- 百分制、五级制、两级制的绩点换算。
- 平均学分绩点、加权平均分、算术平均分和计入学分统计。
- 方向课超过 6 学分时的显式人工选择与可选区间计算。
- 可扩展规则注册表、规则列表接口和按用户持久化的规则切换。
- 课程搜索、筛选、手工修改和来源标记。
- 未修课程的非持久化情景测算。
- SQLite 本地持久化、FastAPI 接口、Windows 启动脚本和 Docker Compose。
- 北航 SSO 预登录、验证码、密码过期继续、用户中心身份校验和退出流程。
- 2024 秋季至 2027 春季的逐学期成绩同步、原始响应审计快照和手工修正保护。

## 本地运行

Python 3.11 或更高版本：

```powershell
./scripts/start-windows.ps1
```

然后打开 [http://127.0.0.1:8000](http://127.0.0.1:8000)。首次启动会创建 `.venv`、安装依赖，并在 `data/student-helper.db` 写入脱敏演示数据。

也可以直接运行：

```powershell
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --reload
```

## Docker Compose

```bash
docker compose up --build
```

服务运行在 [http://localhost:8000](http://localhost:8000)，SQLite 数据保存在 `student-helper-data` 卷中。

## 验证

```powershell
python -m pytest
```

健康检查为 `GET /health`，接口文档为 [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)。

## 重要边界

- 学院规则没有说明方向课修超 6 学分后的自动选取顺序，因此系统不冒充官方规则自动取最高分，而是要求人工确认。
- UBAA 当前公开实现的成绩接口只返回当前学生的课程、成绩和学分。班级均分、排名等数据必须走管理员授权的数据接口，不能使用学生会话横向抓取。
- 学校登录与成绩接口属于非官方公开稳定 API，页面或字段变化时系统会停止同步并提示重新登录/升级，不会静默猜测。
- 生产部署必须启用 HTTPS，并设置 `STUDENT_HELPER_COOKIE_SECURE=1`；当前内存会话会在服务重启后失效，这是刻意的隐私取舍。
- 学号只能用于访问当前登录者本人的数据。系统不提供批量账号、他人成绩或绕过验证码的能力。

详细方案见 [系统设计](docs/system-design.md) 和 [学校接口调研](docs/ubaa-integration-notes.md)。

## 项目结构

```text
app/
  calculation.py       纯计算规则引擎
  database.py          SQLite 存储与演示数据
  main.py              FastAPI 路由
  integrations/buaa.py 北航 SSO 与成绩接口适配器
  rules.py             版本化默认规则
  static/              响应式前端
docs/                  架构与接口调研
scripts/               Windows 启动脚本
tests/                 规则边界测试
```
