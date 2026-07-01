{{/* Common labels */}}
{{- define "bchat.labels" -}}
app.kubernetes.io/name: bchat
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
environment: {{ .Values.environment }}
{{- end }}

{{- define "bchat.selectorLabels" -}}
app.kubernetes.io/name: bchat
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{- define "bchat.appSelector" -}}
app.kubernetes.io/name: bchat
app.kubernetes.io/component: app
{{- end }}

{{- define "bchat.litellmSelector" -}}
app.kubernetes.io/name: bchat
app.kubernetes.io/component: litellm
{{- end }}

{{- define "bchat.mcpSelector" -}}
app.kubernetes.io/name: bchat
app.kubernetes.io/component: mcp
{{- end }}

{{- define "bchat.serviceAccountName" -}}
bchat-app
{{- end }}

{{- define "bchat.secretPrefix" -}}
bchat-{{ .Values.environment }}-
{{- end }}

{{- define "bchat.appConfigName" -}}
app-env
{{- end }}
