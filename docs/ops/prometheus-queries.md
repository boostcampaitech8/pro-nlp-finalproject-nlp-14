# Prometheus 쿼리 가이드

MIT 프로젝트용 복붙 가능한 PromQL 쿼리 모음.

---

## 1. HTTP 요청 수

> Grafana Query Options에서 **Min interval: 1m** 설정 권장

### 전체 요청 횟수 (구간별)
```
round(sum(increase(http_server_duration_milliseconds_count[$__interval])))
```

### 엔드포인트별 요청 횟수 (구간별, health 제외)
```
round(sum by (http_target) (increase(http_server_duration_milliseconds_count{http_target!="/health"}[$__interval])))
```

### 상태 코드별 요청 횟수 (구간별)
```
round(sum by (http_status_code) (increase(http_server_duration_milliseconds_count[$__interval])))
```

### 특정 엔드포인트 요청 횟수 (구간별)
```
round(sum(increase(http_server_duration_milliseconds_count{http_target="/api/v1/agent/meeting/call"}[$__interval])))
```

### 선택한 전체 기간 총합 (Stat 패널용)
```
round(sum(increase(http_server_duration_milliseconds_count[$__range])))
```

---

## 2. HTTP 에러율

### 5xx 에러율 (%)
```
sum(rate(http_server_duration_milliseconds_count{http_status_code=~"5.."}[5m])) / sum(rate(http_server_duration_milliseconds_count[5m])) * 100
```

### 4xx + 5xx 에러율 (%)
```
sum(rate(http_server_duration_milliseconds_count{http_status_code=~"4..|5.."}[5m])) / sum(rate(http_server_duration_milliseconds_count[5m])) * 100
```

---

## 3. HTTP 응답 시간

### 평균 응답 시간 (ms)
```
sum(rate(http_server_duration_milliseconds_sum[5m])) / sum(rate(http_server_duration_milliseconds_count[5m]))
```

### P50 응답 시간 (ms)
```
histogram_quantile(0.50, sum by (le) (rate(http_server_duration_milliseconds_bucket[5m])))
```

### P95 응답 시간 (ms)
```
histogram_quantile(0.95, sum by (le) (rate(http_server_duration_milliseconds_bucket[5m])))
```

### P99 응답 시간 (ms)
```
histogram_quantile(0.99, sum by (le) (rate(http_server_duration_milliseconds_bucket[5m])))
```

### 엔드포인트별 P95 응답 시간 (health 제외)
```
histogram_quantile(0.95, sum by (http_target, le) (rate(http_server_duration_milliseconds_bucket{http_target!="/health"}[5m])))
```

### 느린 엔드포인트 TOP 5 (P95 기준)
```
topk(5, histogram_quantile(0.95, sum by (http_target, le) (rate(http_server_duration_milliseconds_bucket{http_target!="/health"}[5m]))))
```

### 가장 많이 호출되는 엔드포인트 TOP 5
```
topk(5, sum by (http_target) (rate(http_server_duration_milliseconds_count{http_target!="/health"}[5m])))
```

### 특정 엔드포인트 에러율 (예: /api/v1/meetings)
```
sum(rate(http_server_duration_milliseconds_count{http_target=~"/api/v1/meetings.*", http_status_code=~"5.."}[5m])) / sum(rate(http_server_duration_milliseconds_count{http_target=~"/api/v1/meetings.*"}[5m])) * 100
```

---

## 4. ARQ 태스크

> Grafana Query Options에서 **Min interval: 1m** 설정 권장

### 태스크 enqueue 수 (구간별)
```
round(sum(increase(mit_arq_task_enqueue_total[$__interval])))
```

### 태스크별 enqueue 수 (구간별)
```
round(sum by (task_name) (increase(mit_arq_task_enqueue_total[$__interval])))
```

### 태스크 성공/실패 수 (구간별)
```
round(sum by (status) (increase(mit_arq_task_result_total[$__interval])))
```

### 태스크 평균 실행 시간 (초)
```
sum(rate(mit_arq_task_duration_seconds_sum[5m])) / sum(rate(mit_arq_task_duration_seconds_count[5m]))
```

### 태스크 P95 실행 시간 (초)
```
histogram_quantile(0.95, sum by (le) (rate(mit_arq_task_duration_seconds_bucket[5m])))
```

### 태스크별 P95 실행 시간 (초)
```
histogram_quantile(0.95, sum by (task_name, le) (rate(mit_arq_task_duration_seconds_bucket[5m])))
```

### 태스크 성공률 (%)
```
sum(rate(mit_arq_task_result_total{status="success"}[5m])) / sum(rate(mit_arq_task_result_total[5m])) * 100
```

### 태스크별 성공률 (%)
```
sum by (task_name) (rate(mit_arq_task_result_total{status="success"}[5m])) / sum by (task_name) (rate(mit_arq_task_result_total[5m])) * 100
```

### 실패한 태스크 수 (구간별)
```
round(sum(increase(mit_arq_task_result_total{status!="success"}[$__interval])))
```

### 태스크 대기 시간 P95 (초)
```
histogram_quantile(0.95, sum by (le) (rate(mit_arq_task_wait_duration_seconds_bucket[5m])))
```

---

## 5. Realtime Worker (STT/VAD/TTS/Agent)

> **Note**: 이 메트릭들은 실제 회의가 진행되어야 데이터가 쌓입니다. Job 종료 후에도 데이터는 유지됩니다.
> Grafana Query Options에서 **Min interval: 1m** 설정 권장

### VAD → STT 평균 레이턴시 (초)
```
sum(rate(mit_vad_to_stt_latency_seconds_sum[5m])) / sum(rate(mit_vad_to_stt_latency_seconds_count[5m]))
```

### VAD → STT P95 레이턴시 (초)
```
histogram_quantile(0.95, sum by (le) (rate(mit_vad_to_stt_latency_seconds_bucket[5m])))
```

### Wake word → Agent 첫 토큰 평균 레이턴시 (초)
```
sum(rate(mit_wakeword_to_agent_latency_seconds_sum[5m])) / sum(rate(mit_wakeword_to_agent_latency_seconds_count[5m]))
```

### Wake word → Agent P95 레이턴시 (초)
```
histogram_quantile(0.95, sum by (le) (rate(mit_wakeword_to_agent_latency_seconds_bucket[5m])))
```

### Wake word → TTS 첫 오디오 평균 레이턴시 (초)
```
sum(rate(mit_wakeword_to_tts_latency_seconds_sum[5m])) / sum(rate(mit_wakeword_to_tts_latency_seconds_count[5m]))
```

### Wake word → TTS P95 레이턴시 (초)
```
histogram_quantile(0.95, sum by (le) (rate(mit_wakeword_to_tts_latency_seconds_bucket[5m])))
```

### STT 처리 평균 시간 (초)
```
sum(rate(mit_stt_processing_duration_seconds_sum[5m])) / sum(rate(mit_stt_processing_duration_seconds_count[5m]))
```

### TTS 합성 평균 시간 (초)
```
sum(rate(mit_tts_synthesis_duration_seconds_sum[5m])) / sum(rate(mit_tts_synthesis_duration_seconds_count[5m]))
```

### Agent 응답 생성 평균 시간 (초)
```
sum(rate(mit_agent_response_duration_seconds_sum[5m])) / sum(rate(mit_agent_response_duration_seconds_count[5m]))
```

### Wake word 감지 횟수 (구간별)
```
round(sum(increase(mit_wakeword_detected_total[$__interval])))
```

### Agent 호출 횟수 (구간별)
```
round(sum(increase(mit_agent_response_duration_seconds_count[$__interval])))
```

### STT 세그먼트 수 (구간별)
```
round(sum(increase(mit_stt_segment_total[$__interval])))
```

### 총 Realtime Worker Job 수
```
round(sum(increase(mit_realtime_worker_jobs_total{status="created"}[$__interval])))
```

---

## 6. 사용자 활동 로그

> 메트릭: `mit_activity_events_total` (labels: `event_type`, `page_path`)
> Grafana Query Options에서 **Min interval: 1m** 설정 권장

### 전체 활동 이벤트 수 (구간별)
```
round(sum(increase(mit_activity_events_total[$__interval])))
```

### 이벤트 타입별 추이
```
sum by (event_type) (rate(mit_activity_events_total[$__rate_interval]))
```

### 페이지별 방문 수 (구간별)
```
round(sum by (page_path) (increase(mit_activity_events_total[$__interval])))
```

### 특정 이벤트만 (예: click)
```
round(sum(increase(mit_activity_events_total{event_type="click"}[$__interval])))
```

### 선택한 전체 기간 총합 (Stat 패널용)
```
round(sum(increase(mit_activity_events_total[$__range])))
```

### 가장 많이 방문한 페이지 TOP 5
```
topk(5, sum by (page_path) (increase(mit_activity_events_total[$__range])))
```

> **Loki 로그 조회**: 개별 이벤트 원본은 Grafana > Explore > Loki에서 확인
> ```
> {pod=~"backend.*"} |= "activity_log"
> ```

---

## 7. Pod 리소스

### Pod별 CPU 사용량
```
sum by (pod) (rate(container_cpu_usage_seconds_total{namespace="mit"}[5m]))
```

### Pod별 메모리 사용량 (MB)
```
sum by (pod) (container_memory_working_set_bytes{namespace="mit"}) / 1024 / 1024
```

### Pod 재시작 횟수
```
sum by (pod) (kube_pod_container_status_restarts_total{namespace="mit"})
```

---

## 8. Node 리소스

> `node_exporter` 메트릭 기준입니다.
> 누적값이 아닌 현재값을 보려면 Prometheus/Grafana에서 `Instant` 쿼리 사용을 권장합니다.

### 노드별 메모리 사용량 (bytes, 현재값)
```
sum by (instance) (node_memory_MemTotal_bytes - node_memory_MemAvailable_bytes)
```

### 노드별 메모리 사용량 (GiB, 현재값)
```
sum by (instance) ((node_memory_MemTotal_bytes - node_memory_MemAvailable_bytes) / 1024 / 1024 / 1024)
```

### 노드별 메모리 사용률 (%, 현재값)
```
sum by (instance) (100 * (1 - node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes))
```

> `MemFree`보다 `MemAvailable` 기준이 실제 사용 가능 메모리를 반영하기에 더 적합합니다.

---

## 9. Grafana 대시보드용

### 활성 요청 수 (Stat 패널)
```
sum(http_server_active_requests)
```

### 요청 수 추이 (Time series)
```
sum(rate(http_server_duration_milliseconds_count[1m]))
```

### 에러율 추이 (Time series, %)
```
sum(rate(http_server_duration_milliseconds_count{http_status_code=~"5.."}[1m])) / sum(rate(http_server_duration_milliseconds_count[1m])) * 100
```

### P95 응답 시간 추이 (Time series)
```
histogram_quantile(0.95, sum by (le) (rate(http_server_duration_milliseconds_bucket[1m])))
```

---

## 주의사항

1. **Histogram 메트릭**: `http_server_duration_milliseconds` 같은 기본 이름은 존재하지 않습니다. 반드시 `_count`, `_sum`, `_bucket` suffix를 붙여야 합니다.

2. **rate() 필수**: Counter/Histogram 메트릭은 `rate()` 또는 `increase()` 없이 사용하면 의미 없는 누적값만 나옵니다.

3. **시간 범위**: `[5m]`은 5분 평균입니다. 더 세밀하게 보려면 `[1m]`, 더 안정적으로 보려면 `[15m]` 사용.

4. **구간 겹침 방지**: 횟수를 구간별로 정확히 보려면 `increase([$__interval])` + Min interval 설정 사용.

---

## 참고

- 메트릭 정의: `backend/app/core/telemetry.py`, `backend/worker/src/telemetry.py`
- Alloy 설정: `k8s/argocd/applicationsets/prod-observability.yaml` (`grafana/alloy` inline values)
