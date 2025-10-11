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
  --values prometheus-values.yaml

