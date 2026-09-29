# 潮汐视频 Java 后端启动脚本
# 用法：在 video-platform-java 目录下执行 .\run.ps1
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$env:JAVA_HOME = "$root\..\jdk-17"
$env:Path = "$env:JAVA_HOME\bin;$root\..\apache-maven-3.9.16\bin;$env:Path"
mvn spring-boot:run