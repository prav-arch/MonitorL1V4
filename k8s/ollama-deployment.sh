#!/bin/bash

# This script deploys Ollama with model pre-downloading
# Set script to exit on error
set -e

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

NAMESPACE="l1-monitoring"

echo -e "${YELLOW}Starting L1 Monitoring Ollama deployment...${NC}"

# Verify kubernetes is available
if ! command -v kubectl &> /dev/null; then
    echo -e "${RED}kubectl could not be found. Please install kubectl first.${NC}"
    exit 1
fi

# Create namespace if it doesn't exist
echo -e "${YELLOW}Checking if namespace ${NAMESPACE} exists...${NC}"
if ! kubectl get namespace ${NAMESPACE} &> /dev/null; then
    echo -e "${GREEN}Creating ${NAMESPACE} namespace...${NC}"
    kubectl apply -f import-yaml-files/namespace.yaml
fi

# Create PVC for Ollama
echo -e "${GREEN}Creating PVC for Ollama...${NC}"
kubectl apply -n ${NAMESPACE} -f import-yaml-files/ollama-pvc.yaml

# Run Ollama initialization job
echo -e "${GREEN}Running Ollama model initialization job...${NC}"
kubectl apply -n ${NAMESPACE} -f import-yaml-files/ollama-init-job.yaml

# Wait for Ollama initialization to complete
echo -e "${YELLOW}Waiting for Ollama model to download (this may take several minutes)...${NC}"
kubectl -n ${NAMESPACE} wait --for=condition=complete --timeout=30m job/ollama-model-init || true

# Check if the job succeeded
JOB_STATUS=$(kubectl get job -n ${NAMESPACE} ollama-model-init -o jsonpath='{.status.conditions[?(@.type=="Complete")].status}' 2>/dev/null || echo "")
if [ "$JOB_STATUS" != "True" ]; then
    echo -e "${YELLOW}Ollama initialization may not have completed successfully. Checking logs...${NC}"
    kubectl logs -n ${NAMESPACE} -l job-name=ollama-model-init
    echo -e "${YELLOW}Will attempt to continue with deployment anyway...${NC}"
fi

# Deploy Ollama
echo -e "${GREEN}Deploying Ollama...${NC}"
kubectl apply -n ${NAMESPACE} -f import-yaml-files/ollama-deployment.yaml
kubectl apply -n ${NAMESPACE} -f import-yaml-files/ollama-service.yaml

# Wait for deployment to be ready
echo -e "${GREEN}Waiting for Ollama deployment to be ready...${NC}"
kubectl -n ${NAMESPACE} rollout status deployment/ollama --timeout=10m

echo -e "${GREEN}Ollama deployment completed!${NC}"
echo -e "${YELLOW}Use the following command to check Ollama pod status:${NC}"
echo -e "kubectl get pods -n ${NAMESPACE} -l app=ollama"
echo -e "${YELLOW}Use the following command to check Ollama logs:${NC}"
echo -e "kubectl logs -n ${NAMESPACE} -l app=ollama"