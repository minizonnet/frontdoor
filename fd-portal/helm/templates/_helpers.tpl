{{/*
Common labels
*/}}
{{- define "fd-portal.labels" -}}
app: {{ .Chart.Name }}
helm.sh/chart: {{ .Chart.Name }}-{{ .Chart.Version }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
Selector labels
*/}}
{{- define "fd-portal.selectorLabels" -}}
app: {{ .Chart.Name }}
{{- end }}
