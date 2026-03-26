#!/bin/bash
NEO4J_HOME="C:/Users/AlToma/Desktop/Thesis/Neo4j/neo4j-community-2026.01.4-windows/neo4j-community-2026.01.4"

# Setting JAVA_HOME to JDK 21 as required by Neo4j
export JAVA_HOME="C:/Users/AlToma/Tools/java21/OpenJDK21U-jdk_x64_windows_hotspot_21.0.10_7/jdk-21.0.10+7"
export PATH="$JAVA_HOME/bin:$PATH"

if [ ! -d "$NEO4J_HOME" ]; then
    echo "[ERROR] Neo4j directory not found at: $NEO4J_HOME"
    exit 1
fi

echo "Starting Neo4j Server (using JDK 21)..."
# Using the Windows script for best compatibility
"$NEO4J_HOME/bin/neo4j-admin.bat" server console
