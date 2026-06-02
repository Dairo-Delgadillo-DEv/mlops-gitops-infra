# MLOps GitOps Infra — Fraud Detection API

Repositorio de infraestructura y aplicación para desplegar una **API de detección de fraude** (scikit-learn + FastAPI) en Kubernetes, con **GitOps (ArgoCD)**, **observabilidad (Prometheus + Grafana)**, alertas (Alertmanager) y notificaciones (Telegram + Slack).

## Arquitectura

```text
GitHub (main)
    │
    ▼
ArgoCD Application (fraud-detetion-prod)
    │
    ├── mlops-production/     → API Fraud (Deployment + Service)
    │
    └── mlops-monitoring/     → Prometheus, Grafana, Alertmanager,
                                kube-state-metrics, reglas de alerta
```

| Componente | Namespace | Rol |
|------------|-----------|-----|
| `mlops-fraud-api` | `mlops-production` | Inferencia ML (`/predict`, `/healthz`, `/metrics`) |
| `prometheus-core` | `mlops-monitoring` | Métricas y evaluación de alertas |
| `grafana-visualizer` | `mlops-monitoring` | Dashboards |
| `alertmanager` | `mlops-monitoring` | Notificaciones Telegram (principal) y Slack (escalación) |
| `kube-state-metrics` | `mlops-monitoring` | Métricas de Deployments/Pods |

## Estructura del repositorio

```text
.
├── main.py                          # API FastAPI + métricas Prometheus
├── Dockerfile                       # Build multi-stage de la API
├── requirements.txt
├── .github/workflows/ci-cd.yaml     # Build y push de imagen Docker
├── k8s-manifests/
│   ├── api-deployment.yaml          # API en producción
│   ├── monitoring-stack.yaml        # Prometheus, Grafana, RBAC
│   ├── alerting-stack.yaml          # Alertmanager, reglas, kube-state-metrics
│   └── alertmanager-secrets.example.yaml
```

## Despliegue rápido

### 1. Secretos de Alertmanager (no commitear)

```bash
cp k8s-manifests/alertmanager-secrets.example.yaml k8s-manifests/alertmanager-secrets.yaml
# Editar: telegram_bot_token, telegram_chat_id, slack_webhook_url
kubectl apply -f k8s-manifests/alertmanager-secrets.yaml
```

### 2. GitOps con ArgoCD

La aplicación ArgoCD apunta a `k8s-manifests/` en la rama `main`. Tras cada `git push`, sincroniza (auto-sync) o usa **Refresh → Sync** en la UI.

### 3. Acceso a Grafana

```bash
kubectl port-forward -n mlops-monitoring svc/grafana-svc 3000:3000
```

Abre http://localhost:3000 (usuario `admin`; contraseña definida en el manifest).

**Datasource Prometheus:**

```text
http://prometheus-core.mlops-monitoring.svc.cluster.local:9090
```

## Grafana — paneles de la API Fraud

Consultas PromQL de referencia:

**Memoria (MB):**

```promql
container_memory_working_set_bytes{
  namespace="mlops-production",
  pod=~"mlops-fraud-api.*",
  container="api-engine"
} / 1024 / 1024
```

**CPU (%):**

```promql
sum(rate(container_cpu_usage_seconds_total{
  namespace="mlops-production",
  pod=~"mlops-fraud-api.*",
  container="api-engine"
}[5m])) by (pod) * 100
```

> **Nota:** Si `container_cpu_usage_seconds_total` no está disponible en tu cluster, usa esta alternativa con métricas de cAdvisor:
> ```promql
> rate(container_cpu_cfs_throttled_seconds_total{namespace="mlops-production", pod=~"mlops-fraud-api.*"}[5m]) * 100
> ```

### Uso de memoria RAM

Para visualizar este panel en Grafana:
1. Crea un nuevo dashboard o añade un panel
2. Usa la consulta PromQL de **Memoria (MB)** anterior
3. Configura alertas si la memoria supera el 85% del límite (512Mi)

### Uso de CPU

Para visualizar este panel en Grafana:
1. Crea un nuevo dashboard o añade un panel
2. Usa la consulta PromQL de **CPU (%)** anterior
3. Configura alertas si el uso de CPU supera el 90%

> **Nota sobre imágenes:** Para capturar dashboards de Grafana y agregarlos a este README:
> 1. En Grafana, ve a tu dashboard
> 2. Haz clic en el panel
> 3. Usa la opción "Share" → "Link"
> 4. O toma una captura de pantalla (PNG) y súbela a GitHub (arrastra a GitHub durante la edición del README)
> 5. Reemplaza las URLs placeholder con las que genere GitHub automáticamente

## Alertas configuradas

### Operativas

| Alerta | Condición | Telegram | Slack (escalación) |
|--------|-----------|----------|---------------------|
| `FraudApiNoReplicasAvailable` | 0 réplicas listas | 2 min | 5 min |
| `FraudApiMemoryAbove85Percent` | RAM > 85% del límite (512Mi) | 5 min | 10 min |

### Seguridad (ataques / abuso)

| Alerta | Qué detecta |
|--------|-------------|
| `FraudApiCrashLoopBackOff` | Posible exploit o inestabilidad |
| `FraudApiRestartStorm` | 3+ reinicios en 10 min |
| `FraudApiCpuSaturationSuspectedAttack` | CPU > 90% del límite |
| `FraudApiTrafficFlood` | > 20 req/s (DDoS) |
| `FraudApiSuspiciousClientErrors` | Pico de respuestas 4xx |
| `FraudApiServerErrorSpike` | Pico de 5xx |
| `FraudApiMaliciousPayloadRate` | Muchos payloads inválidos (422) |
| `FraudApiPredictEndpointAbuse` | Abuso de `/predict` |

Las alertas de seguridad HTTP requieren imagen de API con `prometheus-fastapi-instrumentator` (CI/CD tras push a `main`).

**Flujo de notificación:**

```text
Incidente → Telegram (principal, repite cada 5 min)
         → Slack si persiste (escalación según regla)
         → RESOLVED en ambos canales al normalizar
```

## CI/CD

El workflow `.github/workflows/ci-cd.yaml` construye y publica:

```text
<DOCKERHUB_USER>/mlops-fraud-api:latest
<DOCKERHUB_USER>/mlops-fraud-api:<git-sha>
```

## Endpoints de la API

| Método | Ruta | Descripción |
|--------|------|-------------|
| `GET` | `/healthz` | Liveness / readiness |
| `POST` | `/predict` | Inferencia de fraude |
| `GET` | `/metrics` | Métricas Prometheus |

Ejemplo:

```bash
curl -X POST http://<host>:8000/predict \
  -H "Content-Type: application/json" \
  -d '{"feature_1": 1.5, "feature_2": 2.3}'
```

## Comandos útiles

```bash
# Estado de pods
kubectl get pods -n mlops-production
kubectl get pods -n mlops-monitoring

# Alertas activas en Prometheus
kubectl port-forward -n mlops-monitoring svc/prometheus-core 9090:9090
# → http://localhost:9090/alerts

# UI de Alertmanager
kubectl port-forward -n mlops-monitoring svc/alertmanager 9093:9093
```

## Autor

Dairo Delgadillo — Proyecto MLOps / GitOps.
