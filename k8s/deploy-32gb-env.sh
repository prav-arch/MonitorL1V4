#!/bin/bash
# Script for deploying L1 Monitoring with ClickHouse optimized for 32GB RAM environments

# Set colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}Deploying L1 Monitoring with ClickHouse (32GB RAM Optimized)...${NC}"

# Check if kubectl is available
if ! command -v kubectl &> /dev/null; then
    echo -e "${RED}Error: kubectl is not installed or not in the PATH${NC}"
    exit 1
fi

# Check if the secrets file exists
if [ ! -f secrets/secrets.yaml ]; then
    echo -e "${RED}Error: secrets/secrets.yaml not found.${NC}"
    echo -e "${YELLOW}Please create it from the template:${NC}"
    echo -e "cp secrets/secrets-template.yaml secrets/secrets.yaml"
    echo -e "Then edit secrets.yaml with your actual secret values."
    exit 1
fi

# Create persistent volume claims
echo -e "${GREEN}Creating persistent volume claims...${NC}"
kubectl apply -f volumes/persistent-volume-claims.yaml
if [ $? -ne 0 ]; then
    echo -e "${RED}Failed to create persistent volume claims.${NC}"
    exit 1
fi

# Apply secrets
echo -e "${GREEN}Applying secrets...${NC}"
kubectl apply -f secrets/secrets.yaml
if [ $? -ne 0 ]; then
    echo -e "${RED}Failed to apply secrets.${NC}"
    exit 1
fi

# Deploy ClickHouse
echo -e "${GREEN}Deploying ClickHouse database...${NC}"
kubectl apply -f deployments/clickhouse-deployment.yaml
kubectl apply -f services/clickhouse-service.yaml
if [ $? -ne 0 ]; then
    echo -e "${RED}Failed to deploy ClickHouse.${NC}"
    exit 1
fi

# Deploy PostgreSQL as fallback
echo -e "${GREEN}Deploying PostgreSQL database (fallback)...${NC}"
kubectl apply -f deployments/postgres-deployment.yaml
kubectl apply -f services/postgres-service.yaml
if [ $? -ne 0 ]; then
    echo -e "${RED}Failed to deploy PostgreSQL.${NC}"
    exit 1
fi

# Deploy OLLAMA
echo -e "${GREEN}Deploying OLLAMA service...${NC}"
kubectl apply -f configmaps/ollama-init.yaml
kubectl apply -f deployments/ollama-deployment.yaml
kubectl apply -f services/ollama-service.yaml
if [ $? -ne 0 ]; then
    echo -e "${RED}Failed to deploy OLLAMA.${NC}"
    exit 1
fi

# Deploy application
echo -e "${GREEN}Deploying L1 Monitoring application...${NC}"
kubectl apply -f deployments/app-deployment.yaml
kubectl apply -f services/app-service.yaml
if [ $? -ne 0 ]; then
    echo -e "${RED}Failed to deploy L1 Monitoring application.${NC}"
    exit 1
fi

# Deploy ingress
echo -e "${GREEN}Deploying ingress...${NC}"
kubectl apply -f ingress/app-ingress.yaml
if [ $? -ne 0 ]; then
    echo -e "${YELLOW}Warning: Failed to deploy ingress. Your cluster may not support ingress controllers.${NC}"
    echo -e "${YELLOW}You can access the application using port-forwarding instead:${NC}"
    echo -e "kubectl port-forward svc/l1-monitoring 5000:5000"
fi

echo -e "${GREEN}Deployment completed successfully.${NC}"
echo -e "${YELLOW}Note: It may take a few minutes for all services to start up.${NC}"
echo -e "${YELLOW}OLLAMA will download the Llama2 model on first startup, which may take 5-10 minutes.${NC}"

# Show deployment status
echo -e "${GREEN}Current deployment status:${NC}"
kubectl get deployments

echo -e "\n${GREEN}To monitor deployment progress, use:${NC}"
echo -e "kubectl get pods -w"

echo -e "\n${GREEN}To view application logs:${NC}"
echo -e "kubectl logs deployment/l1-monitoring"

echo -e "\n${GREEN}To access the application (if ingress is not working):${NC}"
echo -e "kubectl port-forward svc/l1-monitoring 5000:5000"
echo -e "Then access the application at http://localhost:5000"