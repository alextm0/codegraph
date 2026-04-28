@echo off
set "NEO4J_HOME=C:\Users\AlToma\Tools\Neo4j\neo4j-community-2026.01.4-windows\neo4j-community-2026.01.4"

set "JAVA_HOME=C:\Users\AlToma\Tools\java21\OpenJDK21U-jdk_x64_windows_hotspot_21.0.10_7\jdk-21.0.10+7"
set "PATH=%JAVA_HOME%\bin;%PATH%"

if not exist "%NEO4J_HOME%" (
    echo [ERROR] Neo4j directory not found at: %NEO4J_HOME%
    pause
    exit /b 1
)

echo Starting Neo4j Server (using JDK 21)...
"%NEO4J_HOME%\bin\neo4j-admin.bat" server console
