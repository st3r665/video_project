# 潮汐视频 · 短视频推荐系统

本科毕业设计项目 —— **基于双塔模型与实时特征的多阶段短视频推荐系统**。

项目采用「Java 管业务、Python 管推荐」的双服务架构：Spring Boot 负责用户、视频、行为等业务数据，Python 负责推荐算法，两者通过 HTTP 协作，便于后续把推荐算法替换为双塔模型 + Faiss 向量召回。

## 目录结构

```
video/
├── video-platform/          # Python 端：可独立运行的短视频平台 MVP + 推荐引擎
│   ├── server.py            #   HTTP 服务（零第三方依赖，标准库实现）
│   ├── recommender.py       #   混合推荐引擎（热门 + ItemCF + 内容/实时兴趣）
│   ├── seed.py              #   演示数据初始化（ffmpeg 生成测试视频 + 种子行为）
│   └── static/              #   前端页面（推荐流 / 登录 / 上传）
├── video-platform-java/     # Java 端：Spring Boot 3 业务后端
│   ├── pom.xml
│   └── src/main/java/com/tide/video/
│       ├── entity/          #   User / Video / Behavior（JPA 实体）
│       ├── service/         #   AuthService、FeedService
│       ├── client/          #   RecClient（调用 Python 推荐服务）
│       ├── controller/      #   Auth / Feed / Behavior 接口
│       └── seed/            #   DataSeeder（首次启动写入演示数据）
├── 毕业设计方案-短视频推荐系统平台.md
└── 开题报告-短视频推荐系统平台.docx
```

## 快速开始（Python 端，零依赖）

```bash
cd video-platform
python seed.py        # 首次运行：生成 48 个测试视频并初始化演示数据（需 ffmpeg）
python server.py      # 启动 → http://localhost:8000
```

演示账号：`demo / demo123`（已预置篮球偏好）；`alice`、`bob`、`carol`、`dave` 密码均为 `123456`。

## 快速开始（Java 端）

前置：JDK 17 与 Maven（因体积原因未入库，需自行下载）。

```bash
cd video-platform-java
mvn spring-boot:run     # 启动 → http://localhost:8080
```

> 注意：Java 后端的推荐流依赖 Python 推荐服务（默认 `http://localhost:8000`），请先启动 Python 端。若 Python 未启动，Java 会自动降级为热门兜底。

## 架构与接口契约

Java 的 `FeedService` 把「全量视频 + 用户行为」打包成 JSON，POST 给 Python：

```
POST http://localhost:8000/api/recommend
{
  "user_id": 1,
  "count": 12,
  "videos":    [{"id":1,"title":"..","category":"篮球","tags":["扣篮"],"views":10,"likes":3,"created_at":1790000000.0}],
  "behaviors": [{"user_id":1,"video_id":1,"event":"view","watch_ratio":0.9,"created_at":1790000000.0}]
}
→ {"items": [{"video_id":3,"reason":"⚡ 看你最近在看「篮球」","score":0.87}, ...]}
```

Python 返回 `video_id + reason + score`，Java 再补全标题与媒体地址返回前端。推荐算法完全封装在 Python 侧，替换模型时 Java 无需改动。

## 推荐引擎说明

三路打分通道加权融合（`video-platform/recommender.py`）：

| 通道 | 权重 | 说明 |
|------|------|------|
| 热门 hot | 0.20 | 播放/点赞加权 + 时间衰减 |
| 兴趣 content | 0.50 | 分类/标签画像 + 最近 5 次观看的实时加权 |
| 协同 itemcf | 0.30 | 基于物品的协同过滤（共现余弦相似度） |

最近浏览过的分类会获得额外乘性加成，保证「连续刷同类视频后推荐流立刻倾斜」的可感知效果。

## 环境说明

仓库不包含 JDK、Maven 及测试媒体文件（体积过大 / 可自动生成）：

- JDK 17：https://adoptium.net/
- Maven：https://maven.apache.org/download.cgi
- 测试视频：运行 `python seed.py` 自动生成（需本机安装 ffmpeg）