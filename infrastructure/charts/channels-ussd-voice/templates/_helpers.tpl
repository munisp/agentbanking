{{- define "channels-ussd-voice.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{- define "channels-ussd-voice.fullname" -}}
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

{{- define "channels-ussd-voice.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{- define "channels-ussd-voice.labels" -}}
helm.sh/chart: {{ include "channels-ussd-voice.chart" . }}
{{ include "channels-ussd-voice.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{- define "channels-ussd-voice.selectorLabels" -}}
app.kubernetes.io/name: {{ include "channels-ussd-voice.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{- define "channels-ussd-voice.serviceAccountName" -}}
{{- if .Values.serviceAccount.create }}
{{- default (include "channels-ussd-voice.fullname" .) .Values.serviceAccount.name }}
{{- else }}
{{- default "default" .Values.serviceAccount.name }}
{{- end }}
{{- end }}
