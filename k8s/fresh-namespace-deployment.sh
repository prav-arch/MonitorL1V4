#!/bin/bash

# This script creates a fresh namespace and deploys the L1 Monitoring application components
# It's designed for a clean installation with proper namespace isolation

# Set script to exit on error
set -e

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

NAMESPACE="l1-monitoring"

echo -e "${YELLOW}Starting L1 Monitoring clean namespace deployment...${NC}"

# Verify kubernetes is available
if ! command -v kubectl &> /dev/null; then
    echo -e "${RED}kubectl could not be found. Please install kubectl first.${NC}"
    exit 1
fi

# Delete namespace if it exists (optional - remove if you don't want to clean up)
echo -e "${YELLOW}Checking if namespace ${NAMESPACE} exists...${NC}"
if kubectl get namespace ${NAMESPACE} &> /dev/null; then
    echo -e "${YELLOW}Namespace ${NAMESPACE} exists. Deleting for clean installation...${NC}"
    kubectl delete namespace ${NAMESPACE}
    
    # Wait for namespace to be fully deleted
    echo -e "${YELLOW}Waiting for namespace deletion to complete...${NC}"
    while kubectl get namespace ${NAMESPACE} &> /dev/null; do
        echo -e "${YELLOW}Waiting...${NC}"
        sleep 5
    done
    echo -e "${GREEN}Namespace deleted.${NC}"
fi

# Create namespace
echo -e "${GREEN}Creating ${NAMESPACE} namespace...${NC}"
kubectl apply -f import-yaml-files/namespace.yaml

# Create secrets
echo -e "${GREEN}Creating secrets...${NC}"
kubectl apply -n ${NAMESPACE} -f import-yaml-files/secrets.yaml

# Deploy PostgreSQL
echo -e "${GREEN}Deploying PostgreSQL...${NC}"
kubectl apply -n ${NAMESPACE} -f import-yaml-files/postgres-deployment.yaml
kubectl apply -n ${NAMESPACE} -f import-yaml-files/postgres-service.yaml

# Deploy ClickHouse
echo -e "${GREEN}Deploying ClickHouse...${NC}"
kubectl apply -n ${NAMESPACE} -f import-yaml-files/clickhouse-deployment.yaml
kubectl apply -n ${NAMESPACE} -f import-yaml-files/clickhouse-service.yaml

# Check if Ollama is already deployed
echo -e "${YELLOW}Checking if Ollama is already deployed...${NC}"
if kubectl get deployment -n ${NAMESPACE} ollama &> /dev/null; then
    echo -e "${YELLOW}Ollama deployment found. Skipping Ollama deployment.${NC}"
else
    echo -e "${YELLOW}Ollama deployment not found. Please run ./ollama-deployment.sh first.${NC}"
    echo -e "${YELLOW}Do you want to continue without Ollama? (y/n)${NC}"
    read -r answer
    if [[ "$answer" != "y" ]]; then
        echo -e "${RED}Aborting deployment. Please run ./ollama-deployment.sh first.${NC}"
        exit 1
    fi
    echo -e "${YELLOW}Continuing deployment without Ollama...${NC}"
fi

# Deploy the application (using nginx as a placeholder)
echo -e "${GREEN}Deploying nginx config...${NC}"
kubectl apply -n ${NAMESPACE} -f import-yaml-files/nginx-config.yaml

echo -e "${GREEN}Deploying application...${NC}"
kubectl apply -n ${NAMESPACE} -f import-yaml-files/app-deployment.yaml
kubectl apply -n ${NAMESPACE} -f import-yaml-files/app-service.yaml

# Deploy Ingress if available
if kubectl api-resources | grep -q ingress; then
    echo -e "${GREEN}Deploying ingress...${NC}"
    kubectl apply -n ${NAMESPACE} -f import-yaml-files/ingress.yaml
else
    echo -e "${YELLOW}Ingress controller not detected, skipping ingress deployment.${NC}"
fi

# Wait for deployments to be ready
echo -e "${GREEN}Waiting for deployments to be ready...${NC}"
kubectl -n ${NAMESPACE} rollout status deployment/l1-monitoring
kubectl -n ${NAMESPACE} rollout status deployment/postgres
kubectl -n ${NAMESPACE} rollout status deployment/clickhouse
kubectl -n ${NAMESPACE} rollout status deployment/ollama

echo -e "${GREEN}L1 Monitoring deployment completed successfully!${NC}"
echo -e "${YELLOW}Use the following command to see the status of your pods:${NC}"
echo -e "kubectl get pods -n ${NAMESPACE}"

# Print service access information
echo -e "${YELLOW}Access your application:${NC}"
echo -e "If you have an ingress controller, access at: http://l1-monitoring.local"
echo -e "Otherwise, use port-forwarding to access the application:"
echo -e "kubectl port-forward -n ${NAMESPACE} svc/l1-monitoring 8080:80"
echo -e "Then access at: http://localhost:8080"