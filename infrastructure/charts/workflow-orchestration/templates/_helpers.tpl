{{- define "workflow-orchestration.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{- define "workflow-orchestration.fullname" -}}
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- $name := default .Chart.Name .Values.nameOverride }}
{{- if contains $name .Release.Name }}
{{- .Release.Name | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}
{{- end }}

{{- define "workflow-orchestration.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{- define "workflow-orchestration.labels" -}}
helm.sh/chart: {{ include "workflow-orchestration.chart" . }}
{{ include "workflow-orchestration.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{- define "workflow-orchestration.selectorLabels" -}}
app.kubernetes.io/name: {{ include "workflow-orchestration.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{- define "workflow-orchestration.serviceAccountName" -}}
{{- if .Values.serviceAccount.create }}
{{- default (include "workflow-orchestration.fullname" .) .Values.serviceAccount.name }}
{{- else }}
{{- default "default" .Values.serviceAccount.name }}
{{- end }}
{{- end }}
