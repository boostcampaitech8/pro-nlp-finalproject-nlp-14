{{/*
공통 헬퍼 템플릿
*/}}

{{/*
이미지 경로 생성
*/}}
{{- define "mit.image" -}}
{{- if .Values.global.registry -}}
{{ .Values.global.registry }}/{{ .image }}:{{ .tag | default "latest" }}
{{- else -}}
{{ .image }}:{{ .tag | default "latest" }}
{{- end -}}
{{- end -}}

{{/*
Database URL 생성
*/}}
{{- define "mit.databaseUrl" -}}
postgresql+asyncpg://{{ .Values.database.user }}:{{ .Values.database.password }}@{{ .Values.database.host }}:{{ .Values.database.port }}/{{ .Values.database.name }}
{{- end -}}

{{/*
Redis URL 생성
*/}}
{{- define "mit.redisUrl" -}}
redis://{{ .Values.redis.host }}:{{ .Values.redis.port }}
{{- end -}}

{{/*
LiveKit 내부 URL 생성
*/}}
{{- define "mit.livekitWsUrl" -}}
ws://{{ .Values.livekit.host }}:{{ .Values.livekit.port }}
{{- end -}}

{{/*
MinIO 엔드포인트 생성
*/}}
{{- define "mit.minioEndpoint" -}}
{{ .Values.minio.host }}:{{ .Values.minio.port }}
{{- end -}}

{{/*
Backend 내부 URL
*/}}
{{- define "mit.backendUrl" -}}
http://backend:8000
{{- end -}}

{{/*
CORS origins JSON 배열
*/}}
{{- define "mit.corsOrigins" -}}
{{ .Values.app.corsOrigins | toJson }}
{{- end -}}
