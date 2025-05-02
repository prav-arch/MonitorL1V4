#!/bin/bash

# This script deploys the L1 Monitoring application components optimized for low resources (8GB RAM)
# It uses tinyllama instead of llama2 for the LLM model and has reduced resource limits for all components
# All components have been optimized to run within 8GB of system memory

# Set script to exit on error
set -e

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

NAMESPACE="l1-monitoring"

echo -e "${YELLOW}Starting L1 Monitoring low-resource deployment...${NC}"

# Verify kubernetes is available
if ! command -v kubectl &> /dev/null; then
    echo -e "${RED}kubectl could not be found. Please install kubectl first.${NC}"
    exit 1
fi

# Check for minimum memory requirements (8GB)
TOTAL_MEMORY=$(free -m | awk '/^Mem:/{print $2}')
if [[ $TOTAL_MEMORY -lt 7500 ]]; then
    echo -e "${RED}WARNING: This system has less than 8GB of RAM ($TOTAL_MEMORY MB).${NC}"
    echo -e "${YELLOW}Deployment may not work correctly or may be unstable.${NC}"
    echo -e "${YELLOW}Do you want to continue anyway? (y/n)${NC}"
    read -r answer
    if [[ "$answer" != "y" ]]; then
        echo -e "${RED}Deployment aborted.${NC}"
        exit 1
    fi
    echo -e "${YELLOW}Continuing with deployment on limited resources...${NC}"
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

# Deploy the application
echo -e "${GREEN}Deploying nginx config...${NC}"
kubectl apply -n ${NAMESPACE} -f import-yaml-files/nginx-config.yaml

echo -e "${GREEN}Deploying application...${NC}"
kubectl apply -n ${NAMESPACE} -f import-yaml-files/app-deployment.yaml
kubectl apply -n ${NAMESPACE} -f import-yaml-files/app-service.yaml

# Create PVC for Ollama
echo -e "${GREEN}Creating PVC for Ollama...${NC}"
kubectl apply -n ${NAMESPACE} -f import-yaml-files/ollama-pvc.yaml

# Deploy Ollama model initialization job
echo -e "${GREEN}Running Ollama model initialization job...${NC}"
kubectl apply -n ${NAMESPACE} -f import-yaml-files/ollama-init-job.yaml

# Wait for Ollama initialization to complete (with a timeout)
echo -e "${YELLOW}Waiting for Ollama model to download (this may take several minutes)...${NC}"
kubectl -n ${NAMESPACE} wait --for=condition=complete --timeout=20m job/ollama-model-init || true

# Check if the job succeeded
JOB_STATUS=$(kubectl get job -n ${NAMESPACE} ollama-model-init -o jsonpath='{.status.conditions[?(@.type=="Complete")].status}' 2>/dev/null || echo "")
if [ "$JOB_STATUS" != "True" ]; then
    echo -e "${YELLOW}Ollama initialization may not have completed successfully. Checking logs...${NC}"
    kubectl logs -n ${NAMESPACE} -l job-name=ollama-model-init
    
    # Ask if we should continue without model download
    echo -e "${YELLOW}Do you want to continue with the deployment anyway? (y/n)${NC}"
    read -r answer
    if [[ "$answer" != "y" ]]; then
        echo -e "${RED}Deployment aborted.${NC}"
        exit 1
    fi
fi

# Deploy Ollama
echo -e "${GREEN}Deploying Ollama...${NC}"
kubectl apply -n ${NAMESPACE} -f import-yaml-files/ollama-deployment.yaml
kubectl apply -n ${NAMESPACE} -f import-yaml-files/ollama-service.yaml

# Deploy Ingress if available
if kubectl api-resources | grep -q ingress; then
    echo -e "${GREEN}Deploying ingress...${NC}"
    kubectl apply -n ${NAMESPACE} -f import-yaml-files/ingress.yaml
else
    echo -e "${YELLOW}Ingress controller not detected, skipping ingress deployment.${NC}"
fi

# Wait for deployments to be ready with timeouts
echo -e "${GREEN}Waiting for deployments to be ready (with timeouts)...${NC}"
kubectl -n ${NAMESPACE} rollout status deployment/l1-monitoring --timeout=2m || true
kubectl -n ${NAMESPACE} rollout status deployment/postgres --timeout=2m || true
kubectl -n ${NAMESPACE} rollout status deployment/clickhouse --timeout=2m || true
kubectl -n ${NAMESPACE} rollout status deployment/ollama --timeout=5m || true

echo -e "${GREEN}L1 Monitoring deployment completed!${NC}"
echo -e "${YELLOW}Use the following command to see the status of your pods:${NC}"
echo -e "kubectl get pods -n ${NAMESPACE}"

# Print service access information
echo -e "${YELLOW}Access your application:${NC}"
echo -e "If you have an ingress controller, access at: http://l1-monitoring.local"
echo -e "Otherwise, use port-forwarding to access the application:"
echo -e "kubectl port-forward -n ${NAMESPACE} svc/l1-monitoring 8080:80"
echo -e "Then access at: http://localhost:8080"

# Display resource usage summary
echo -e "\n${YELLOW}Resource Usage Summary:${NC}"
echo -e "This optimized deployment uses approximately:"
echo -e "- App: 192Mi memory, 80m CPU"
echo -e "- PostgreSQL: 192Mi memory, 80m CPU"
echo -e "- ClickHouse: 384Mi memory, 150m CPU"
echo -e "- Ollama (tinyllama): 1Gi memory, 800m CPU"
echo -e "Total approximate resource usage: 1.77Gi memory, 1.11 CPU cores"
echo -e "${YELLOW}Note: Actual resource usage may vary based on workload and data volume.${NC}"