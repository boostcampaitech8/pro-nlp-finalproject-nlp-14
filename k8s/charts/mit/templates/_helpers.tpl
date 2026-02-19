{{/*
공통 헬퍼 템플릿
*/}}

{{/*
이미지 경로 생성
사용법: {{ include "mit.image" (dict "Values" .Values "name" "backend") }}
*/}}
{{- define "mit.image" -}}
{{- $imageName := printf "mit-%s" .name -}}
{{- $tag := index .Values.images .name "tag" | default "latest" -}}
{{- if .Values.global.registry -}}
{{ .Values.global.registry }}/{{ $imageName }}:{{ $tag }}
{{- else -}}
{{ $imageName }}:{{ $tag }}
{{- end -}}
{{- end -}}

{{/*
imagePullSecrets 설정
*/}}
{{- define "mit.imagePullSecrets" -}}
{{- if .Values.images.pullSecret }}
imagePullSecrets:
  - name: {{ .Values.images.pullSecret }}
{{- end }}
{{- end -}}

{{/*
앱 Secret 이름
*/}}
{{- define "mit.secretName" -}}
{{ .Values.secrets.name | default "mit-secrets" }}
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
