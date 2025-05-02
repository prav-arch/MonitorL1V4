#!/bin/bash

# This script deploys the L1 Monitoring application components for extremely resource-constrained systems
# It uses orca-mini (smallest model) instead of llama2 and has extremely reduced resource limits

# Set script to exit on error
set -e

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

NAMESPACE="l1-monitoring"

echo -e "${YELLOW}Starting L1 Monitoring ultra lightweight deployment...${NC}"

# Verify kubernetes is available
if ! command -v kubectl &> /dev/null; then
    echo -e "${RED}kubectl could not be found. Please install kubectl first.${NC}"
    exit 1
fi

# Check for minimum memory requirements
TOTAL_MEMORY=$(free -m | awk '/^Mem:/{print $2}')
AVAILABLE_MEMORY=$(free -m | awk '/^Mem:/{print $7}')

echo -e "${YELLOW}System has ${TOTAL_MEMORY}MB total RAM with ${AVAILABLE_MEMORY}MB available.${NC}"
if [[ $AVAILABLE_MEMORY -lt 1000 ]]; then
    echo -e "${RED}WARNING: Less than 1GB of available memory detected ($AVAILABLE_MEMORY MB).${NC}"
    echo -e "${YELLOW}Deployment may fail or be unstable. Consider freeing up memory first.${NC}"
    echo -e "${YELLOW}Do you want to continue anyway? (y/n)${NC}"
    read -r answer
    if [[ "$answer" != "y" ]]; then
        echo -e "${RED}Deployment aborted.${NC}"
        exit 1
    fi
    echo -e "${YELLOW}Continuing with ultra lightweight deployment on limited resources...${NC}"
fi

# Delete namespace if it exists (optional - remove if you don't want to clean up)
echo -e "${YELLOW}Checking if namespace ${NAMESPACE} exists...${NC}"
if kubectl get namespace ${NAMESPACE} &> /dev/null; then
    echo -e "${YELLOW}Namespace ${NAMESPACE} exists. Deleting for clean installation...${NC}"
    kubectl delete namespace ${NAMESPACE}
    
    # Wait for namespace to be fully deleted with timeout
    echo -e "${YELLOW}Waiting for namespace deletion to complete (max 60s)...${NC}"
    TIMEOUT=60
    START_TIME=$(date +%s)
    while kubectl get namespace ${NAMESPACE} &> /dev/null; do
        CURRENT_TIME=$(date +%s)
        ELAPSED_TIME=$((CURRENT_TIME - START_TIME))
        if [[ $ELAPSED_TIME -gt $TIMEOUT ]]; then
            echo -e "${YELLOW}Namespace deletion taking too long, continuing anyway...${NC}"
            break
        fi
        echo -e "${YELLOW}Waiting... ($ELAPSED_TIME seconds elapsed)${NC}"
        sleep 5
    done
    echo -e "${GREEN}Namespace deleted or timeout reached.${NC}"
fi

# Create namespace
echo -e "${GREEN}Creating ${NAMESPACE} namespace...${NC}"
kubectl apply -f import-yaml-files/namespace.yaml

# Deploy components one at a time
echo -e "${GREEN}Deploying PostgreSQL (Step 1/5)...${NC}"
kubectl apply -n ${NAMESPACE} -f import-yaml-files/postgres-deployment.yaml
kubectl apply -n ${NAMESPACE} -f import-yaml-files/postgres-service.yaml

# Wait until PostgreSQL is ready before continuing
echo -e "${YELLOW}Waiting for PostgreSQL pod to be created...${NC}"
sleep 10
POSTGRES_POD=$(kubectl get pods -n ${NAMESPACE} -l app=postgres -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || echo "")

if [ -z "$POSTGRES_POD" ]; then
    echo -e "${YELLOW}PostgreSQL pod not found yet, continuing with deployment...${NC}"
else
    echo -e "${GREEN}PostgreSQL pod created: $POSTGRES_POD${NC}"
    
    # Check if pod is running or in pending state before continuing
    POD_STATUS=$(kubectl get pod $POSTGRES_POD -n ${NAMESPACE} -o jsonpath='{.status.phase}' 2>/dev/null || echo "Unknown")
    if [ "$POD_STATUS" != "Running" ]; then
        echo -e "${YELLOW}PostgreSQL pod status: $POD_STATUS. Continuing anyway...${NC}"
    else
        echo -e "${GREEN}PostgreSQL pod status: $POD_STATUS${NC}"
    fi
fi

echo -e "${GREEN}Deploying ClickHouse (Step 2/5)...${NC}"
kubectl apply -n ${NAMESPACE} -f import-yaml-files/clickhouse-deployment.yaml
kubectl apply -n ${NAMESPACE} -f import-yaml-files/clickhouse-service.yaml
sleep 5

# Deploy the application
echo -e "${GREEN}Deploying nginx config and application (Step 3/5)...${NC}"
kubectl apply -n ${NAMESPACE} -f import-yaml-files/nginx-config.yaml
kubectl apply -n ${NAMESPACE} -f import-yaml-files/app-deployment.yaml
kubectl apply -n ${NAMESPACE} -f import-yaml-files/app-service.yaml
sleep 5

# Create PVC for Ollama
echo -e "${GREEN}Creating PVC for Ollama (Step 4/5)...${NC}"
kubectl apply -n ${NAMESPACE} -f import-yaml-files/ollama-pvc.yaml
sleep 2

echo -e "${GREEN}Deploying Ollama (Step 5/5)...${NC}"
# Skip the init job for now to save resources
echo -e "${YELLOW}Skipping Ollama init job to save resources. Model will be pulled when needed.${NC}"
kubectl apply -n ${NAMESPACE} -f import-yaml-files/ollama-deployment.yaml
kubectl apply -n ${NAMESPACE} -f import-yaml-files/ollama-service.yaml

# Don't wait for deployments to be ready to save time
echo -e "${GREEN}Deployment commands completed!${NC}"
echo -e "${YELLOW}Pods are starting in the background. This may take several minutes.${NC}"

# Print out pod status
echo -e "${YELLOW}Current pod status:${NC}"
kubectl get pods -n ${NAMESPACE}

echo -e "${GREEN}Ultra-light L1 Monitoring deployment initiated!${NC}"
echo -e "${YELLOW}Use the following command to see the status of your pods:${NC}"
echo -e "kubectl get pods -n ${NAMESPACE}"

# Print service access information
echo -e "${YELLOW}Access your application:${NC}"
echo -e "Use port-forwarding to access the application:"
echo -e "kubectl port-forward -n ${NAMESPACE} svc/l1-monitoring 8080:80"
echo -e "Then access at: http://localhost:8080"

# Display resource usage summary
echo -e "\n${YELLOW}Resource Usage Summary:${NC}"
echo -e "This ultra lightweight deployment uses approximately:"
echo -e "- App: 64Mi memory, 20m CPU"
echo -e "- PostgreSQL: 64Mi memory, 20m CPU"
echo -e "- ClickHouse: 96Mi memory, 20m CPU"
echo -e "- Ollama (orca-mini): 256Mi memory, 80m CPU"
echo -e "Total approximate resource usage: ~480Mi memory, 0.14 CPU cores"
echo -e "${YELLOW}Note: Ollama will use more resources temporarily when loading the model.${NC}"

echo -e "\n${YELLOW}Troubleshooting Tips:${NC}"
echo -e "1. If pods are in 'Pending' state, check for resource constraints:"
echo -e "   kubectl describe pods -n ${NAMESPACE}"
echo -e "2. If pods are in 'CrashLoopBackOff', check the logs:"
echo -e "   kubectl logs -n ${NAMESPACE} <pod-name>"
echo -e "3. If Ollama fails to start, you can run a simpler version without it:"
echo -e "   kubectl scale deployment -n ${NAMESPACE} ollama --replicas=0"
echo -e "4. For very limited resources, disable ClickHouse:"
echo -e "   kubectl scale deployment -n ${NAMESPACE} clickhouse --replicas=0"