# 潮汐视频 · 短视频推荐系统

> 本科毕业设计 —— **基于双塔模型与实时特征的多阶段短视频推荐系统设计与实现**

![Python](https://img.shields.io/badge/Python-3.8%2B%20%C2%B7%20零第三方依赖-3776AB?logo=python&logoColor=white)
![Java](https://img.shields.io/badge/Java-17-007396?logo=openjdk&logoColor=white)
![Spring Boot](https://img.shields.io/badge/Spring%20Boot-3.3.5-6DB33F?logo=springboot&logoColor=white)
![Database](https://img.shields.io/badge/SQLite%20%7C%20H2-embedded-003B57?logo=sqlite&logoColor=white)

一个可完整运行、可现场演示的短视频推荐平台。跑通 **注册登录 → 上传视频 → 竖屏刷流 → 行为埋点 → 个性化推荐 → 推荐理由可视化** 的完整闭环，并在此之上验证多阶段推荐链路。

**设计思路：平台是载体，推荐系统是核心。** 业务后端用 Java（Spring Boot），推荐算法用 Python，两者通过 HTTP 解耦——算法换模型时 Java 一行不用改。

---

## 项目状态

当前是 **v0.1 可运行 MVP**：推荐链路的最小闭环已经打通，属于设计方案中的「阶段 0 + 阶段 1」。

| 设计方案阶段 | 内容 | 状态 |
|---|---|---|
| 阶段 0 | 热门推荐基线（时间衰减） | ✅ 已实现 |
| 阶段 1 | ItemCF 协同过滤 | ✅ 已实现 |
| 阶段 1.5 | 实时行为特征（最近 N 次观看加权） | ✅ 已实现（规则版） |
| 阶段 2 | 双塔召回模型 + Faiss 向量检索 | ⬜ 待开发（论文主创新点） |
| 阶段 3 | DNN 精排 / 多任务排序 | ⬜ 待开发 |
| — | 离线评测（Recall@K / NDCG@K / HitRate） | ⬜ 待开发 |

已实现的部分是**规则化的混合推荐**；双塔模型上线后，Python 侧只需替换打分逻辑，Java 侧接口契约保持不变。

---

## 它能演示什么

打开首页就是一条 TikTok 式竖屏推荐流，**每条视频左上角带推荐理由标签**：

| 标签 | 触发条件 |
|---|---|
| ⚡ 看你最近在看「篮球」 | 该分类出现在你最近 5 次观看里 |
| 🎯 匹配你的「美食」兴趣 | 命中你的历史分类画像 |
| 👤 看过《XX》的人也再看 | ItemCF 共现相似度贡献 |
| 🔥 热门视频 | 热门通道兜底 / 新用户冷启动 |
| 🔁 再看一遍 · … | 已看过的视频回填（推荐池不足时） |

**核心演示效果**：连续刷 3 条「美食」视频 → 点「换一批」→ 推荐流立刻向美食倾斜，且刚看过的视频不再出现。这是实时特征机制的直观体现，也是答辩现场的重点。

---

## 系统架构

```
┌──────────────────────────────┐
│        浏览器前端             │
│  index / login / upload      │
│  IntersectionObserver 自动播放│
└───────────┬──────────────────┘
            │ HTTP
     ┌──────┴───────┐
     │              │
┌────▼─────────┐  ┌─▼──────────────────────────┐
│ Python 服务   │  │ Spring Boot 3 业务后端      │
│ video-platform│  │ video-platform-java        │
│              │  │                            │
│ · 用户/鉴权    │  │ · 用户 / 视频 / 行为（JPA）  │
│ · 上传/媒体流  │◀─┤ · FeedService 组装特征      │
│ · SQLite      │  │ · RecClient 调用推荐服务    │
│ · 推荐引擎 ◀───┼──┤ · 推荐不可用时热门兜底       │
│   (recommender│  │ · H2 数据库                 │
│    .py)       │  └────────────────────────────┘
└───────────────┘
```

两端都能独立运行：

- **Python 端**是完整的可演示系统（自带前端、鉴权、上传、推荐），零第三方依赖。
- **Java 端**是正式架构的业务后端，推荐流依赖 Python 推荐服务；Python 未启动时自动降级为热门排序，服务不会挂。

推荐算法完全封装在 Python 的 `recommender.py` 里。Java 只负责把「全量视频 + 用户行为」打包成 JSON 发过去，拿回 `video_id + reason + score` 再补全视频信息。**这个边界是刻意守住的：Java 里不写算法，Python 里不写业务。**

---

## 推荐引擎（核心）

三条打分通道加权融合，最终得分：

```
total = 0.20 × hot + 0.50 × content + 0.30 × itemcf
```

| 通道 | 权重 | 实现 |
|---|---|---|
| **hot** 热门 | 0.20 | `(播放量 + 3×点赞) / (小时龄 + 2)^0.3`，Hacker News 风格时间衰减 |
| **content** 兴趣 | 0.50 | 分类画像（0.7）+ 标签命中率（0.3）；行为权重按 7 天半衰期衰减 |
| **itemcf** 协同 | 0.30 | 物品共现余弦相似度 `c / √(pop_a · pop_b)`，再乘行为权重与近因系数 |

**实时兴趣机制**（论文创新点之一的雏形）：

- 取用户最近 **5 次观看**的分类作为「实时兴趣集合」；
- 该集合内的行为权重 **×2** 参与画像计算；
- 候选视频若属于这些分类，最终得分再 **×1.7**（乘性加成）。

**冷启动**：没有任何行为的用户（含新注册）直接走热门通道，不做强行个性化。

**可解释性**：每条推荐都带 `reason` 字段给前端展示，同时带 `debug` 字段输出 `hot / content / itemcf / total` 四个分值，方便写论文时做分数构成分析。

**去重与回填**：已看过（view / progress / finish）的视频排到队尾，推荐池被刷空时才回填并标注「🔁 再看一遍」。

---

## 快速开始

### 方式一：只跑 Python 端（推荐先试这个）

环境要求：**Python 3.8+，无需安装任何第三方包**。`ffmpeg` 只在首次生成测试视频时需要。

```bash
cd video-platform
python seed.py        # 首次运行：生成 48 条测试视频（6 分类 × 8 条）+ 演示账号与行为
python server.py      # 启动 → http://localhost:8000
```

端口冲突时：`set PORT=8001` 再启动。

### 方式二：Python + Java 双服务

前置：JDK 17 与 Maven（因体积原因未入库，需自行下载，参见文末「环境说明」）。

```powershell
# 1. 先启动 Python 推荐服务
cd video-platform
python server.py          # → http://localhost:8000

# 2. 再启动 Java 业务后端
cd ..\video-platform-java
.\run.ps1                 # 已内置 JAVA_HOME 与 Maven 路径
# 或手动：mvn spring-boot:run
```

Java 端启动后：

- 业务接口：http://localhost:8080
- H2 控制台：http://localhost:8080/h2-console（JDBC URL `jdbc:h2:file:./data/tide`，用户名 `sa`，密码空）

首次运行 Maven 会从中央仓库下载依赖，约几分钟，之后走本地缓存。

### 验证推荐链路确实通了

```powershell
# 登录 demo（预置了篮球偏好）
$t = (Invoke-RestMethod -Method POST -Uri http://localhost:8080/api/auth/login `
      -ContentType application/json -Body '{"username":"demo","password":"demo123"}').token

# 拉个性化推荐流（Java 内部会调 Python 推荐服务）
Invoke-RestMethod -Uri http://localhost:8080/api/feed?count=8 -Headers @{ Authorization = "Bearer $t" }

# 上报一条行为，再拉一次，推荐会变化
Invoke-RestMethod -Method POST -Uri http://localhost:8080/api/behaviors `
  -Headers @{ Authorization = "Bearer $t" } -ContentType application/json `
  -Body '{"video_id":5,"event":"view","watch_ratio":0}'
```

---

## 演示账号

| 账号 | 密码 | 预置偏好 |
|---|---|---|
| `demo` | `demo123` | 篮球（仅 3 条观看记录，专为演示实时倾斜保留） |
| `alice` | `123456` | 美食、音乐 |
| `bob` | `123456` | 篮球、科技 |
| `carol` | `123456` | 旅行、搞笑 |
| `dave` | `123456` | 篮球、美食 |

### 答辩演示剧本

1. 用 `demo / demo123` 登录 —— 首页推荐流已经明显偏向「篮球」；
2. 指出每条视频左上角的**推荐理由标签**，说明推荐是可解释的；
3. 注册一个**新账号**（体验冷启动，先给热门），连续看完并点赞 3 条「美食」视频；
4. 点右上角「↻ 换一批」—— 推荐流立刻向美食倾斜，刚看过的视频不再出现；
5. 点「＋ 上传」发布一条自己的视频（mp4 / webm / mov），走完创作流程。

---

## 接口

### Java 端（Spring Boot，:8080）

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/auth/register` | 注册 |
| POST | `/api/auth/login` | 登录，返回 token |
| GET | `/api/auth/me` | 当前用户 |
| GET | `/api/feed?count=8` | 推荐流（需 token；无 token 走热门） |
| POST | `/api/behaviors` | 行为上报 `{video_id, event, watch_ratio}` |
| GET | `/api/health` | 健康检查 |

### Python 端（标准库 HTTP 服务，:8000）

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/register` `/api/login` `/api/logout` | 注册 / 登录 / 退出 |
| GET | `/api/me` | 当前用户 |
| GET | `/api/feed?count=12` | 推荐流（登录后个性化，否则热门） |
| POST | `/api/behavior` | 行为埋点 `{video_id, event, watch_ratio}` |
| POST | `/api/upload` | 上传视频（multipart：`title` / `category` / `tags` / `file`） |
| GET | `/api/videos/mine` | 我上传的视频 |
| POST | `/api/recommend` | **无状态推荐接口**，供 Java 调用（见下） |
| GET | `/media/<filename>` | 视频流（支持 Range 断点续传） |

页面路由：`/` 推荐流、`/login` 登录、`/upload` 上传。

### Java ↔ Python 契约

Java 的 `FeedService` 把全量视频与用户行为打包后 POST 给 Python：

```jsonc
// POST http://localhost:8000/api/recommend
{
  "user_id": 1,
  "count": 12,
  "videos": [
    { "id": 1, "title": "篮球 · 精选片段 1", "category": "篮球",
      "tags": ["扣篮", "NBA", "集锦"], "views": 10, "likes": 3, "created_at": 1790000000.0 }
  ],
  "behaviors": [
    { "user_id": 1, "video_id": 1, "event": "view", "watch_ratio": 0.9, "created_at": 1790000000.0 }
  ]
}
// → {"items": [{"video_id": 3, "reason": "⚡ 看你最近在看「篮球」", "score": 0.87}]}
```

契约设计成**无状态**的：Python 不查库、不依赖会话，全部特征由 Java 传进来。好处是推荐服务可以随时水平扩容，也便于用离线数据集直接回放调用。

---

## 技术栈

| 层次 | 技术 |
|---|---|
| 推荐引擎 | Python 3（标准库实现，无 numpy / 无 pandas / 无 Web 框架） |
| 业务后端 | Java 17 + Spring Boot 3.3.5 + Spring Web + Spring Data JPA |
| 数据库 | Python 端 SQLite；Java 端 H2（文件模式，可一键切 MySQL） |
| 前端 | 原生 HTML / CSS / JavaScript，零构建步骤 |
| 媒体 | `http.server` 直出，支持 HTTP Range |
| 密码安全 | PBKDF2-HMAC-SHA256 + 随机盐 |
| 视频生成 | FFmpeg（`seed.py` 调用，生成带文字的测试视频） |

---

## 目录结构

```
video_project/
├── video-platform/                    # Python 端：可独立运行的完整平台 + 推荐引擎
│   ├── server.py                      #   HTTP 服务（零依赖）：路由/鉴权/上传/媒体流
│   ├── recommender.py                 #   混合推荐引擎（热门 + ItemCF + 内容/实时兴趣）
│   ├── seed.py                        #   演示数据初始化（ffmpeg 生成视频 + 种子行为）
│   ├── static/                        #   前端：index / login / upload + 样式脚本
│   ├── java-bridge/RecClientDemo.java #   Java 调用推荐服务的独立示例
│   └── README.md                      #   Python 端详细文档
├── video-platform-java/               # Java 端：Spring Boot 3 业务后端
│   ├── pom.xml
│   ├── run.ps1                        #   一键启动脚本（内置 JAVA_HOME / Maven 路径）
│   ├── README.md                      #   Java 端详细文档
│   └── src/main/java/com/tide/video/
│       ├── VideoApplication.java      #   启动类 + RestTemplate + CORS
│       ├── entity/                    #   User / Video / Behavior（JPA 实体）
│       ├── repository/                #   Spring Data JPA 仓库
│       ├── service/                   #   AuthService、FeedService
│       ├── client/RecClient.java      #   Python 推荐服务客户端（含降级）
│       ├── controller/                #   Auth / Feed / Behavior 接口
│       └── seed/DataSeeder.java       #   首次启动写入演示数据
├── 毕业设计方案-短视频推荐系统平台.md      # 完整设计方案（架构、算法、排期、实验）
└── 开题报告-短视频推荐系统平台.docx
```

---

## 数据表

`users`（用户）、`tokens`（登录态）、`videos`（视频）、`behaviors`（**行为日志，整个系统的命脉**——推荐、训练、评测的数据全部来自它）。

行为的 `event` 类型：`view`（开始播放）、`progress`（观看进度心跳）、`finish`（播完）、`like` / `unlike`（点赞 / 取消）。

---

## 已知限制

- 视频**不做转码**，原文件直出，依赖浏览器原生解码（mp4 / webm）
- 推荐模型是**规则化混合打分**，尚未引入深度学习；双塔召回与精排仍是设计方案里的待办
- 单机演示级并发，未做写并发优化；Java 端 Token 存内存，重启失效（正式可换 JWT）
- Java 端未实现文件上传，视频仍由 Python 侧 `/media/` 提供，Java 只存元数据
- 尚无离线评测脚本，`Recall@K` / `NDCG@K` / `HitRate` 指标待补

---

## 环境说明

仓库刻意不包含体积过大的二进制与工具链，需要时自行准备：

| 依赖 | 说明 |
|---|---|
| JDK 17 | https://adoptium.net/ （Java 端需要） |
| Maven | https://maven.apache.org/download.cgi （Java 端需要） |
| FFmpeg | 首次运行 `seed.py` 生成测试视频时需要；`media/` 下已有视频则不需要 |

数据库文件（`data/`）、生成的测试视频（`video-platform/media/*.mp4`）、构建产物（`target/`）均已在 `.gitignore` 中忽略。

---

## 后续路线

对齐设计方案，按递进顺序推进：

1. **双塔召回模型**（主创新点）——用户塔 / 视频塔各 64 维输出，内积 + sampled softmax 负采样训练，Faiss 建索引，线上毫秒级取 top-500；
2. **DNN 精排**——输入用户 + 候选视频 + 交叉统计特征，预测完播概率排序；时间充裕则升级为共享底层的多目标模型（`α·p(点击) + (1-α)·p(完播)`）；
3. **离线评测**——接入 MovieLens-1M，按时间切分 8:2，跑消融实验矩阵（热门 / ItemCF / 双塔仅 ID 特征 / 双塔完整特征 / 双塔+精排）；
4. **工程完善**——FFmpeg 异步转 HLS、Redis 实时特征、Kafka 行为日志流、MySQL + MinIO 替换 SQLite + 本地文件。
