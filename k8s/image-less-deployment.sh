#!/bin/bash

# This script deploys the L1 Monitoring application components without relying on Docker
# It uses pre-built images from public registries

# Set script to exit on error
set -e

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${YELLOW}Starting L1 Monitoring image-less deployment...${NC}"

# Verify kubernetes is available
if ! command -v kubectl &> /dev/null; then
    echo -e "${RED}kubectl could not be found. Please install kubectl first.${NC}"
    exit 1
fi

# Create namespace
echo -e "${GREEN}Creating l1-monitoring namespace...${NC}"
kubectl apply -f import-yaml-files/namespace.yaml

# Create secrets
echo -e "${GREEN}Creating secrets...${NC}"
kubectl apply -n l1-monitoring -f import-yaml-files/secrets.yaml

# Deploy PostgreSQL
echo -e "${GREEN}Deploying PostgreSQL...${NC}"
kubectl apply -n l1-monitoring -f import-yaml-files/postgres-deployment.yaml
kubectl apply -n l1-monitoring -f import-yaml-files/postgres-service.yaml

# Deploy ClickHouse
echo -e "${GREEN}Deploying ClickHouse...${NC}"
kubectl apply -n l1-monitoring -f import-yaml-files/clickhouse-deployment.yaml
kubectl apply -n l1-monitoring -f import-yaml-files/clickhouse-service.yaml

# Deploy Ollama
echo -e "${GREEN}Deploying Ollama...${NC}"
kubectl apply -n l1-monitoring -f import-yaml-files/ollama-deployment.yaml
kubectl apply -n l1-monitoring -f import-yaml-files/ollama-service.yaml

# Deploy the application (using nginx as a placeholder)
echo -e "${GREEN}Deploying nginx config...${NC}"
kubectl apply -n l1-monitoring -f import-yaml-files/nginx-config.yaml

echo -e "${GREEN}Deploying application...${NC}"
kubectl apply -n l1-monitoring -f import-yaml-files/app-deployment.yaml
kubectl apply -n l1-monitoring -f import-yaml-files/app-service.yaml

# Deploy Ingress if available
if kubectl api-resources | grep -q ingress; then
    echo -e "${GREEN}Deploying ingress...${NC}"
    kubectl apply -n l1-monitoring -f import-yaml-files/ingress.yaml
else
    echo -e "${YELLOW}Ingress controller not detected, skipping ingress deployment.${NC}"
fi

# Wait for deployments to be ready
echo -e "${GREEN}Waiting for deployments to be ready...${NC}"
kubectl -n l1-monitoring rollout status deployment/l1-monitoring
kubectl -n l1-monitoring rollout status deployment/postgres
kubectl -n l1-monitoring rollout status deployment/clickhouse
kubectl -n l1-monitoring rollout status deployment/ollama

echo -e "${GREEN}L1 Monitoring deployment completed successfully!${NC}"
echo -e "${YELLOW}Use the following command to see the status of your pods:${NC}"
echo -e "kubectl get pods -n l1-monitoring"

# Print service access information
echo -e "${YELLOW}Access your application:${NC}"
echo -e "If you have an ingress controller, access at: http://l1-monitoring.local"
echo -e "Otherwise, use port-forwarding to access the application:"
echo -e "kubectl port-forward -n l1-monitoring svc/l1-monitoring 8080:80"
echo -e "Then access at: http://localhost:8080"