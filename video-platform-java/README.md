# 潮汐视频 · 业务后端（Spring Boot 3）

短视频推荐平台的 Java 业务后端，与 Python 推荐服务（`../video-platform`）通过 HTTP 协作，形成「Java 管业务、Python 管推荐」的双服务架构。

## 技术栈

- Java 17 + Spring Boot 3.3 + Spring Web + Spring Data JPA
- 数据库：H2（文件模式，零安装；后续可一键切 MySQL）
- 推荐服务调用：RestTemplate → Python `http://localhost:8000/api/recommend`

## 启动

前置：JDK 17 已解压到 `../jdk-17`，Maven 已解压到 `../apache-maven-3.9.16`。

```powershell
# 1. 先启动 Python 推荐服务（在 video-platform 目录）
cd ..\video-platform
python server.py

# 2. 再启动 Java 后端（在 video-platform-java 目录）
.\run.ps1        # 已内置 JAVA_HOME 与 Maven 路径
# 或手动：
$env:JAVA_HOME = "..\jdk-17"
..\apache-maven-3.9.16\bin\mvn.cmd spring-boot:run
```

首次运行 Maven 会从中央仓库下载依赖（约几分钟，之后走缓存）。启动后：

- 后端：http://localhost:8080
- H2 控制台：http://localhost:8080/h2-console（JDBC URL 填 `jdbc:h2:file:./data/tide`，用户名 sa，密码空）

## 验证流程

```powershell
# 登录 demo（预置了篮球偏好）
$t = (Invoke-RestMethod -Method POST -Uri http://localhost:8080/api/auth/login -ContentType application/json -Body '{"username":"demo","password":"demo123"}').token

# 拉个性化推荐流（Java 内部会调 Python 推荐服务）
Invoke-RestMethod -Uri http://localhost:8080/api/feed?count=8 -Headers @{ Authorization = "Bearer $t" }

# 上报行为（看完 3 条美食再拉 feed，推荐会向美食倾斜）
Invoke-RestMethod -Method POST -Uri http://localhost:8080/api/behaviors -Headers @{ Authorization = "Bearer $t" } -ContentType application/json -Body '{"video_id":5,"event":"view","watch_ratio":0}'
```

## Java ↔ Python 接口契约

Java 的 `FeedService` 把「全量视频 + 用户行为」打包成 JSON，POST 给 Python：

```
POST http://localhost:8000/api/recommend
{
  "user_id": 1,
  "count": 12,
  "videos": [{"id":1,"title":"..","category":"篮球","tags":["扣篮"],"views":10,"likes":3,"created_at":1790000000.0}],
  "behaviors": [{"user_id":1,"video_id":1,"event":"view","watch_ratio":0.9,"created_at":1790000000.0}]
}
→ {"items": [{"video_id":3,"reason":"⚡ 看你最近在看「篮球」","score":0.87}, ...]}
```

Python 返回 `video_id + reason + score`，Java 再补全视频标题、封面与媒体 URL 返回给前端。推荐算法（热门 + ItemCF + 内容/实时兴趣，以后换双塔模型）完全封装在 Python 侧，Java 无需改动。

## 代码结构

```
src/main/java/com/tide/video/
├── VideoApplication.java      # 启动类 + RestTemplate + CORS
├── entity/                    # User / Video / Behavior（JPA 实体）
├── repository/                # Spring Data JPA 仓库
├── service/
│   ├── AuthService.java       # 注册/登录（PBKDF2 + 内存 Token）
│   └── FeedService.java       # 组装特征 → 调 Python → 返回推荐
├── client/RecClient.java      # Python 推荐服务客户端（含降级）
├── controller/                # Auth / Feed / Behavior 控制器
└── seed/DataSeeder.java       # 首次启动写入演示数据
```

## 已知简化（后续微调）

- Token 存内存（重启失效），正式可换 JWT
- 数据库用 H2，正式切 MySQL 只需改 `application.yml` 的 datasource
- 视频文件仍由 Python 侧 `/media/` 提供；Java 只存元数据
- 未实现文件上传（Java 侧），暂由 Python 侧承担