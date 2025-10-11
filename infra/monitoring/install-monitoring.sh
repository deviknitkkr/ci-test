#!/bin/bash

# Install Prometheus and Grafana using Helm
echo "Installing Prometheus and Grafana monitoring stack..."

# Add Prometheus community helm repository
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo update

# Create monitoring namespace
kubectl create namespace monitoring

# Install Prometheus stack (includes Grafana, Alertmanager, and Prometheus)
helm upgrade --install prometheus-stack prometheus-community/kube-prometheus-stack \
  --namespace monitoring \
  --version 78.0.0 \
  --values prometheus-values.yaml

k3d image import registry.k8s.io/ingress-nginx/kube-webhook-certgen:v1.6.3
k3d image import registry.k8s.io/kube-state-metrics/kube-state-metrics:v2.17.0
k3d image import docker.io/library/busybox:1.31.1

