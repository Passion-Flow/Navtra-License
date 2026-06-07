{{/*
Expand the name of the chart.
*/}}
{{- define "forge.name" -}}
{{- default .Chart.Name | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name. Truncated at 63 chars (DNS limit). If the release name
already contains the chart name it is used as the full name.
*/}}
{{- define "forge.fullname" -}}
{{- $name := default .Chart.Name }}
{{- if contains $name .Release.Name }}
{{- .Release.Name | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}

{{/*
Chart name and version, for the helm.sh/chart label.
*/}}
{{- define "forge.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels (added to every object).
*/}}
{{- define "forge.labels" -}}
helm.sh/chart: {{ include "forge.chart" . }}
{{ include "forge.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
Selector labels.
*/}}
{{- define "forge.selectorLabels" -}}
app.kubernetes.io/name: {{ include "forge.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/* Extra pod labels (global.podLabels), applied to pod templates only — not selectors. */}}
{{- define "forge.podExtraLabels" -}}
{{- if .Values.global.podLabels }}
{{- toYaml .Values.global.podLabels }}
{{- end }}
{{- end }}

{{/*
A component's image reference, from its own image.{repository,tag} block (tag defaults to appVersion).
Usage: {{ include "forge.componentImage" (dict "comp" .Values.api "ctx" .) }}
*/}}
{{- define "forge.componentImage" -}}
{{- printf "%s:%s" .comp.image.repository (.comp.image.tag | default .ctx.Chart.AppVersion) -}}
{{- end }}

{{/* ---- custom CA (private/self-signed CA for 信创 enterprise intranets) ---- */}}
{{- define "forge.customCA.enabled" -}}
{{- if and .Values.global.customCA.enabled .Values.global.customCA.existingSecret }}true{{- end }}
{{- end }}

{{- define "forge.customCA.volume" -}}
- name: custom-ca-secret
  secret:
    secretName: {{ .Values.global.customCA.existingSecret | quote }}
    items:
      - key: {{ .Values.global.customCA.key | quote }}
        path: {{ .Values.global.customCA.key | quote }}
- name: custom-ca-combined
  emptyDir: {}
{{- end }}

{{- define "forge.customCA.volumeMount" -}}
- name: custom-ca-combined
  mountPath: {{ .Values.global.customCA.mountPath | quote }}
  readOnly: true
{{- end }}

{{- define "forge.customCA.env" -}}
{{- $bundle := printf "%s/ca-bundle.crt" .Values.global.customCA.mountPath -}}
- name: SSL_CERT_FILE
  value: {{ $bundle | quote }}            {{- /* Python ssl / httpx / asyncpg / aiomysql TLS */}}
- name: REQUESTS_CA_BUNDLE
  value: {{ $bundle | quote }}            {{- /* requests / urllib3 */}}
- name: AWS_CA_BUNDLE
  value: {{ $bundle | quote }}            {{- /* boto3 (S3-compatible object storage) */}}
- name: CURL_CA_BUNDLE
  value: {{ $bundle | quote }}            {{- /* libcurl-based clients */}}
{{- end }}

{{- define "forge.customCA.initContainer" -}}
- name: init-custom-ca
  image: {{ .Values.global.customCA.initImage | default "alpine:3.20" }}
  imagePullPolicy: IfNotPresent
  command:
    - sh
    - -c
    - |
      if [ -f /etc/ssl/certs/ca-certificates.crt ]; then
        cp /etc/ssl/certs/ca-certificates.crt /custom-ca-combined/ca-bundle.crt
      elif [ -f /etc/ssl/cert.pem ]; then
        cp /etc/ssl/cert.pem /custom-ca-combined/ca-bundle.crt
      else
        touch /custom-ca-combined/ca-bundle.crt
      fi
      echo >> /custom-ca-combined/ca-bundle.crt
      cat /custom-ca-secret/{{ .Values.global.customCA.key }} >> /custom-ca-combined/ca-bundle.crt
  volumeMounts:
    - name: custom-ca-secret
      mountPath: /custom-ca-secret
      readOnly: true
    - name: custom-ca-combined
      mountPath: /custom-ca-combined
{{- end }}

{{/*
Resolve the active datasource by database.type, picking the matching external<Type> block (or the
bundled postgresql subchart when it is enabled and type=postgres). Returns a JSON object:
{ "type", "host", "port", "username", "password", "name", "sslMode" }
Usage: {{- $db := include "forge.datasource" . | fromJson }}
*/}}
{{- define "forge.datasource" -}}
{{- $ds := dict -}}
{{- $type := .Values.database.type | default "postgres" -}}
{{- if and .Values.postgresql.enabled (eq $type "postgres") -}}
  {{- $_ := set $ds "type" "postgres" -}}
  {{- $_ := set $ds "host" (printf "%s-postgresql" .Release.Name) -}}
  {{- $_ := set $ds "port" "5432" -}}
  {{- $_ := set $ds "username" (.Values.postgresql.global.postgresql.auth.username | default "forge_app") -}}
  {{- $_ := set $ds "password" (.Values.postgresql.global.postgresql.auth.password | default "") -}}
  {{- $_ := set $ds "name" (.Values.postgresql.global.postgresql.auth.database | default "forge_main") -}}
  {{- $_ := set $ds "sslMode" "disable" -}}
{{- else -}}
  {{- $blockMap := dict
        "postgres" "externalPostgres" "mysql" "externalMysql" "tidb" "externalTidb"
        "oracle" "externalOracle" "dameng" "externalDameng" "opengauss" "externalOpengauss"
        "kingbase" "externalKingbase" "oceanbase" "externalOceanbase"
        "polardb-pg" "externalPolardbPg" "polardb-x" "externalPolardbX" -}}
  {{- $blockKey := index $blockMap $type -}}
  {{- $b := index .Values.database $blockKey -}}
  {{- $_ := set $ds "type" $type -}}
  {{- $_ := set $ds "host" ($b.host | default "localhost") -}}
  {{- $_ := set $ds "port" (printf "%v" ($b.port | default 5432)) -}}
  {{- $_ := set $ds "username" ($b.username | default "forge_app") -}}
  {{- $_ := set $ds "password" ($b.password | default "") -}}
  {{- $_ := set $ds "name" ($b.database | default "forge_main") -}}
  {{- $_ := set $ds "sslMode" ($b.sslMode | default "prefer") -}}
{{- end -}}
{{- $ds | toJson -}}
{{- end }}

{{/* Cache type (redis | valkey). */}}
{{- define "forge.cache.type" -}}
{{- if .Values.externalRedis.enabled -}}{{- .Values.externalRedis.type | default "redis" -}}{{- else -}}redis{{- end -}}
{{- end }}

{{/* Cache host (external override or the redis subchart master service). */}}
{{- define "forge.cache.host" -}}
{{- if .Values.externalRedis.enabled -}}
{{- .Values.externalRedis.host -}}
{{- else -}}
{{- printf "%s-redis-master" .Release.Name -}}
{{- end -}}
{{- end }}

{{/* Cache port. */}}
{{- define "forge.cache.port" -}}
{{- if .Values.externalRedis.enabled -}}{{- .Values.externalRedis.port | default 6379 -}}{{- else -}}6379{{- end -}}
{{- end }}

{{/* Cache password. */}}
{{- define "forge.cache.password" -}}
{{- if .Values.externalRedis.enabled -}}
{{- .Values.externalRedis.password | default "" -}}
{{- else -}}
{{- .Values.redis.global.redis.password | default "" -}}
{{- end -}}
{{- end }}

{{/* Resolve the active object-storage block by persistence.type. Returns JSON. */}}
{{- define "forge.storage" -}}
{{- $s := dict -}}
{{- $type := .Values.persistence.type | default "local" -}}
{{- $_ := set $s "type" $type -}}
{{- $map := dict "s3" "s3" "aliyun-oss" "aliyunOss" "tencent-cos" "tencentCos" "volcengine-tos" "volcengineTos" "huawei-obs" "huaweiObs" "azure-blob" "azureBlob" "google-storage" "googleStorage" -}}
{{- if hasKey $map $type -}}
  {{- $b := index .Values.persistence (index $map $type) -}}
  {{- $_ := set $s "endpoint" ($b.endpoint | default "") -}}
  {{- $_ := set $s "region" ($b.region | default "") -}}
  {{- $_ := set $s "accessKey" ($b.accessKey | default "") -}}
  {{- $_ := set $s "secretKey" ($b.secretKey | default "") -}}
  {{- $_ := set $s "secure" ($b.secure | default true) -}}
  {{- $_ := set $s "accountName" ($b.accountName | default "") -}}
  {{- $_ := set $s "accountKey" ($b.accountKey | default "") -}}
  {{- $_ := set $s "serviceAccountJson" ($b.serviceAccountJson | default "") -}}
{{- end -}}
{{- $s | toJson -}}
{{- end }}

{{/* Resolve the active mail block by mail.type. Returns JSON. */}}
{{- define "forge.mail" -}}
{{- $m := dict -}}
{{- $type := .Values.mail.type | default "smtp" -}}
{{- $_ := set $m "type" $type -}}
{{- if eq $type "smtp" -}}
  {{- $b := .Values.mail.smtp -}}
  {{- $_ := set $m "host" ($b.host | default "") -}}
  {{- $_ := set $m "port" (printf "%v" ($b.port | default 465)) -}}
  {{- $_ := set $m "username" ($b.username | default "") -}}
  {{- $_ := set $m "password" ($b.password | default "") -}}
  {{- $_ := set $m "useTls" ($b.useTls | default true) -}}
{{- else -}}
  {{- $map := dict "aws_ses" "awsSes" "sendgrid" "sendgrid" "aliyun_dm" "aliyunDm" "tencent_ses" "tencentSes" "volcengine_dm" "volcengineDm" -}}
  {{- $b := index .Values.mail (index $map $type) -}}
  {{- $_ := set $m "region" ($b.region | default "") -}}
  {{- $_ := set $m "accessKey" ($b.accessKey | default "") -}}
  {{- $_ := set $m "secretKey" ($b.secretKey | default "") -}}
  {{- $_ := set $m "apiKey" ($b.apiKey | default "") -}}
{{- end -}}
{{- $m | toJson -}}
{{- end }}

{{/* Resolve the active search block by search.type. Returns JSON. */}}
{{- define "forge.search" -}}
{{- $s := dict -}}
{{- $type := .Values.search.type | default "opensearch" -}}
{{- $map := dict "opensearch" "opensearch" "elasticsearch" "elasticsearch" "transwarp" "transwarp" "easysearch" "easysearch" "huawei-css" "huaweiCss" "aliyun-es" "aliyunEs" "tencent-es" "tencentEs" -}}
{{- $b := index .Values.search (index $map $type) -}}
{{- $_ := set $s "type" $type -}}
{{- $_ := set $s "host" ($b.host | default "") -}}
{{- $_ := set $s "port" (printf "%v" ($b.port | default 9200)) -}}
{{- $_ := set $s "username" ($b.username | default "") -}}
{{- $_ := set $s "password" ($b.password | default "") -}}
{{- $_ := set $s "useSsl" ($b.useSsl | default true) -}}
{{- $s | toJson -}}
{{- end }}
