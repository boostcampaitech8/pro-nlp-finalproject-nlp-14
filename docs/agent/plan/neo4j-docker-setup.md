# Neo4j Docker Setup

Neo4j 그래프 데이터베이스를 Docker Compose로 실행하는 방법

## 1. docker-compose.yml 설정

`docker/docker-compose.yml`의 services 섹션에 추가:

```yaml
  neo4j:
    image: neo4j:5-community
    container_name: mit-neo4j
    environment:
      # 인증 설정 (neo4j/비밀번호)
      NEO4J_AUTH: neo4j/${NEO4J_PASSWORD:-neo4jpassword}
      # 메모리 설정 (소규모 데이터용 - 10,000건 이하)
      NEO4J_server_memory_heap_initial__size: 256m
      NEO4J_server_memory_heap_max__size: 512m
      NEO4J_server_memory_pagecache_size: 128m
    ports:
      - "7474:7474"   # Browser UI
      - "7687:7687"   # Bolt protocol (애플리케이션 연결)
    volumes:
      - neo4j_data:/data
      - neo4j_logs:/logs
      # CSV import용 볼륨 (data/augment/nodes/, relationships/ 마운트)
      - ../data/augment:/var/lib/neo4j/import:ro
    healthcheck:
      test: ["CMD-SHELL", "wget --no-verbose --tries=1 --spider http://localhost:7474 || exit 1"]
      interval: 10s
      timeout: 5s
      retries: 5
    restart: unless-stopped
```

volumes 섹션에 추가:

```yaml
volumes:
  postgres_data:
  redis_data:
  minio_data:
  neo4j_data:      # 추가
  neo4j_logs:      # 추가
```

## 2. 환경변수 설정

`.env` 파일에 추가:

```bash
# Neo4j
NEO4J_PASSWORD=your-secure-password
```

## 3. Backend 환경변수

`docker/docker-compose.yml`의 backend 서비스 environment에 추가:

```yaml
  backend:
    environment:
      # ... 기존 설정 ...
      # Neo4j 설정
      NEO4J_URI: bolt://neo4j:7687
      NEO4J_USER: neo4j
      NEO4J_PASSWORD: ${NEO4J_PASSWORD:-neo4jpassword}
```

## 4. 실행

```bash
# 인프라 실행 (Neo4j 포함)
make infra-up

# 또는 직접 실행
docker compose -f docker/docker-compose.yml up -d neo4j

# 로그 확인
docker logs -f mit-neo4j
```

## 5. 접속 확인

### Browser UI
```
http://localhost:7474
```
- Username: neo4j
- Password: .env에 설정한 NEO4J_PASSWORD (기본값: neo4jpassword)

### Bolt Protocol (애플리케이션용)
```
bolt://localhost:7687
```

## 6. 메모리 설정 가이드

| 데이터 규모 | heap_initial | heap_max | pagecache |
|------------|--------------|----------|-----------|
| 10,000건 이하 | 256m | 512m | 128m |
| 100,000건 이하 | 512m | 1g | 256m |
| 1,000,000건 이하 | 1g | 2g | 512m |

현재 설정은 10,000건 이하 소규모 데이터에 최적화됨.

## 7. 트러블슈팅

### CSV Import 경로 오류
CSV 파일은 `/var/lib/neo4j/import/` 경로에 마운트됨.
Cypher에서는 `file:///경로/파일명.csv` 형식으로 접근.

```cypher
// 테스트 (노드 CSV)
LOAD CSV WITH HEADERS FROM 'file:///nodes/teams.csv' AS row
RETURN row LIMIT 1;

// 테스트 (관계 CSV)
LOAD CSV WITH HEADERS FROM 'file:///relationships/member_of.csv' AS row
RETURN row LIMIT 1;
```

### 연결 거부
```bash
# healthcheck 확인
docker inspect mit-neo4j | jq '.[0].State.Health'

# 포트 확인
docker port mit-neo4j
```
