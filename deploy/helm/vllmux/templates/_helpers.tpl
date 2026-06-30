{{/* Common name + label helpers */}}
{{- define "vllmux.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{- define "vllmux.fullname" -}}
{{- if .Values.fullnameOverride -}}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- $name := include "vllmux.name" . -}}
{{- if contains $name .Release.Name -}}
{{- .Release.Name | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" -}}
{{- end -}}
{{- end -}}
{{- end -}}

{{- define "vllmux.labels" -}}
app.kubernetes.io/name: {{ include "vllmux.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
helm.sh/chart: {{ printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" }}
{{- end -}}

{{- define "vllmux.secretName" -}}
{{- if .Values.secrets.existingSecret -}}
{{- .Values.secrets.existingSecret -}}
{{- else -}}
{{- printf "%s-secrets" (include "vllmux.fullname" .) -}}
{{- end -}}
{{- end -}}

{{- define "vllmux.configMapName" -}}
{{- if .Values.config.existingConfigMap -}}
{{- .Values.config.existingConfigMap -}}
{{- else -}}
{{- printf "%s-config" (include "vllmux.fullname" .) -}}
{{- end -}}
{{- end -}}

{{- define "vllmux.postgresHost" -}}
{{- printf "%s-postgres" (include "vllmux.fullname" .) -}}
{{- end -}}

{{/*
DB URL: bundled Postgres builds a DSN from the postgres.* values + the password
Secret key; otherwise the externalDbUrl is used verbatim. Emits nothing when neither
is configured (SQLite single-pod — not recommended on k8s).
*/}}
{{- define "vllmux.dbUrl" -}}
{{- if .Values.postgres.enabled -}}
postgresql://{{ .Values.postgres.user }}:$(POSTGRES_PASSWORD)@{{ include "vllmux.postgresHost" . }}:5432/{{ .Values.postgres.database }}
{{- else -}}
{{- .Values.externalDbUrl -}}
{{- end -}}
{{- end -}}
