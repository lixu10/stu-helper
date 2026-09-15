# UBAA 与学校接口调研

调研基于 [BUAASubnet/UBAA](https://github.com/BUAASubnet/UBAA) `dev` 分支提交 `1f4b8f8412272b6a423d4ad92b396e3db721e6f3`，以及其[技术文档](https://www.buaa.team/tech/architecture)。该项目和本项目都不是学校官方系统，上游页面与字段可能变化，真实上线前必须在授权环境重新抓包和回归。

## 1. 成绩查询

UBAA 的服务端和本地模式目前都访问：

```text
GET  https://app.buaa.edu.cn/buaascore/wap/default/index
POST https://app.buaa.edu.cn/buaascore/wap/default/index
Content-Type: application/x-www-form-urlencoded

year=2025-2026&xq=2
```

GET 用于激活成绩应用会话，POST 带 `X-Requested-With: XMLHttpRequest` 查询某一学期。响应核心字段包括：

| 上游字段 | 含义 |
| --- | --- |
| `kcmc` | 课程名称 |
| `kch` | 课程代码 |
| `xf` | 学分 |
| `kccj` | 成绩文本 |
| `fslx` | 分数/认定类型 |
| `kclx` | 课程类型 |

UBAA 对外提供 `GET /api/v1/grade/list?termCode=2025-2026-2`，返回当前登录用户指定学期的 `GradeData`。当前新接口没有直接返回绩点；Student Helper 应依据版本化规则自行计算，不能假设上游 `JD` 字段始终存在或与目标规则一致。

## 2. 统一认证与会话复用

UBAA 当前流程包含：

1. 访问 `https://sso.buaa.edu.cn/login`，解析隐藏字段 `execution`，检测验证码。
2. 使用用户名、密码、execution 和可选验证码提交 CAS 表单。
3. 跟随重定向，并处理密码过期提示页的“本次忽略”。
4. 激活 `https://uc.buaa.edu.cn/api/login?...`，再用 `https://uc.buaa.edu.cn/api/uc/status` 验证身份并获取姓名、学号。
5. 服务端按学号维护 Cookie 会话，签发自身访问/刷新令牌；有效会话可以复用，避免同一用户反复向学校登录。
6. 成绩请求如果返回 401、跳回 SSO 或正文出现统一认证表单，则把学校会话判定为过期。

Student Helper 的 Web 模式只能采用服务器中转：浏览器把密码提交给本站登录接口，本站与学校完成交换后立即丢弃密码，之后使用服务器端学校会话。要满足“不保存密码”，不得实现浏览器 localStorage 记住密码，也不得把 Cookie jar 返回前端。

## 3. 与 UBAA 的差异

UBAA 是校园服务聚合客户端，支持直连、WebVPN 和服务器中转；Student Helper 是多用户 Web 服务，核心资产是历史成绩快照、规则版本和可复现计算。因此建议复用接口知识，不直接把 UBAA 服务当作生产依赖：

- 将登录和成绩抓取放进独立 `BuaaStudentProvider` 适配器。
- 保存上游响应摘要和标准化快照，以便接口变更时重放。
- 对 UBAA 的字段解析样例建立契约测试，但不复制其 Token/Redis 体系到轻量 MVP。
- 上游 URL、表单字段和过期识别集中配置，不散落在业务代码中。

## 4. 全班成绩、均分与排名

在本次检出的 UBAA 服务端、共享模型和文档中，没有发现返回全班成绩、课程均分、百分位或排名的成绩接口。现有成绩应用响应是当前登录学生维度。课程和博雅模块中虽然存在班级代码，但它不是成绩名册。

结论：不能从现有学生接口安全推出全班统计能力，也不应循环使用学生或管理员网页登录会话抓取他人成绩。

推荐新增一条完全独立的管理员数据链：

```text
学校授权数据服务 / 受控导出
    -> AdminStatisticsProvider
    -> 内存中校验、去标识化、聚合
    -> AggregateStat（n、均值、中位数、分位数、直方图）
    -> 学生仅查询自己课程对应的聚合结果
```

如果学校能提供正式数据中心接口，应优先申请以下最小字段：学年学期、课程代码、教学班或专业年级口径、有效成绩、成绩制、样本状态。Student Helper 不需要保存姓名、学号和完整班级名单即可完成均分及百分位分析。

## 5. 接入前验证清单

- 校内网、WebVPN 与服务器部署网络是否都能完成 SSO 重定向。
- 验证码、密码过期提示、多身份账户、毕业年级和教师账户分支。
- 成绩接口是否包含未发布/无效/补考/重修/替代课程，正考成绩的字段如何标识。
- 学期代码与夏季学期的映射。
- 两级制、五级制成绩在 `kccj` 与 `fslx` 中的真实组合。
- 学校会话有效期、并发登录限制和退出语义。
- 获得校方对管理员统计数据用途、保留期限和展示粒度的书面确认。
