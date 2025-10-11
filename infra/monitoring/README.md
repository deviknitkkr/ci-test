# Monitoring Setup Guide

This guide explains how to set up monitoring for the CI-Test Spring Boot application using Prometheus and Grafana.

## Overview

The monitoring setup includes:
- **Prometheus**: Metrics collection and storage
- **Grafana**: Metrics visualization and dashboards
- **AlertManager**: Alert management
- **Custom metrics**: Latency, TPS, error rate for the `/ping` API
- **Auto-deployed dashboard**: Application-specific Grafana dashboard deployed via Helm

## Installation

### Option 1: Using Helm directly
```bash
cd infra/monitoring
./install-monitoring.sh
```

### Option 2: Using ArgoCD
```bash
kubectl apply -f infra/monitoring/monitoring-app.yaml
```

## Accessing the Monitoring Stack

After installation, you can access:
- **Grafana**: http://grafana.local (admin/admin123)
- **Prometheus**: http://prometheus.local
- **AlertManager**: http://alertmanager.local

## Application Metrics

The Spring Boot application exposes the following custom metrics:

### Available Metrics
- `ping_requests_total`: Total number of ping requests
- `ping_errors_total`: Total number of ping errors
- `ping_request_duration_seconds`: Request duration histogram

### Metrics Endpoint
- Application metrics: `http://ci-test.local/actuator/prometheus`
- Health check: `http://ci-test.local/actuator/health`

## Grafana Dashboard

The dashboard is **automatically deployed** with your application via Helm chart:
- Dashboard ConfigMap: `helm/templates/grafana-dashboard.yaml`
- Auto-discovery: Grafana sidecar automatically loads the dashboard
- Customizable title via `values.yaml`

### Dashboard Features
- Request Rate (TPS)
- Error Rate (%)
- 95th Percentile Latency
- Active Pods
- Response Time Distribution
- Historical trends

### Dashboard Configuration
```yaml
monitoring:
  dashboard:
    enabled: true
    title: "My Custom Dashboard Title"
```

## Alerts

The following alerts are configured:

### Alert Rules
1. **HighErrorRate**: Triggers when error rate > 5% for 2 minutes
2. **HighLatency**: Triggers when 95th percentile latency > 1 second for 2 minutes
3. **LowThroughput**: Triggers when request rate < 1 req/sec for 5 minutes
4. **ServiceDown**: Triggers when service is unreachable for 1 minute

### Alert Thresholds (configurable in values.yaml)
```yaml
monitoring:
  alerts:
    errorRateThreshold: 0.05  # 5%
    latencyThreshold: 1.0     # 1 second
    throughputThreshold: 1.0  # 1 request/sec
```

## Testing the Setup

1. **Deploy the application** (dashboard included):
   ```bash
   helm upgrade --install ci-test ./helm
   ```

2. **Generate some traffic**:
   ```bash
   curl http://ci-test.local/ping
   ```

3. **Check metrics**:
   ```bash
   curl http://ci-test.local/actuator/prometheus | grep ping_
   ```

4. **View in Grafana**:
   - Go to http://grafana.local
   - Navigate to Dashboards → Browse
   - Find your auto-deployed application dashboard
   - View real-time metrics

## Configuration Files

### Infrastructure
- `infra/monitoring/prometheus-values.yaml`: Prometheus stack configuration with dashboard discovery
- `infra/monitoring/install-monitoring.sh`: Installation script
- `infra/monitoring/monitoring-app.yaml`: ArgoCD application
- `infra/monitoring/ingress.yaml`: Access configuration

### Application
- `helm/templates/servicemonitor.yaml`: Prometheus scraping configuration
- `helm/templates/prometheusrule.yaml`: Custom alert rules
- `helm/templates/grafana-dashboard.yaml`: Auto-deployed Grafana dashboard
- `helm/values.yaml`: Monitoring and dashboard settings

## Dashboard Auto-Discovery

The dashboard is automatically discovered by Grafana through:
1. **ConfigMap labeling**: `grafana_dashboard: "1"` label
2. **Sidecar configuration**: Grafana sidecar scans for dashboard ConfigMaps
3. **Automatic loading**: Dashboard appears in Grafana without manual import

## Troubleshooting

1. **Dashboard not appearing**: Check if monitoring.dashboard.enabled is true in values.yaml
2. **Metrics not appearing**: Check if ServiceMonitor is created and Prometheus is scraping
3. **Alerts not firing**: Verify PrometheusRule is loaded and thresholds are correct
4. **Access issues**: Check ingress configuration and DNS resolution
