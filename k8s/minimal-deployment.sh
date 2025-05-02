#!/bin/bash

# This script deploys only the minimal components of L1 Monitoring application
# It skips Ollama and ClickHouse completely for extremely resource-constrained systems

# Set script to exit on error
set -e

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

NAMESPACE="l1-monitoring"

echo -e "${YELLOW}Starting L1 Monitoring minimal deployment (PostgreSQL only)...${NC}"

# Verify kubernetes is available
if ! command -v kubectl &> /dev/null; then
    echo -e "${RED}kubectl could not be found. Please install kubectl first.${NC}"
    exit 1
fi

# Create namespace
echo -e "${GREEN}Creating ${NAMESPACE} namespace...${NC}"
kubectl apply -f import-yaml-files/namespace.yaml

# Deploy only PostgreSQL and the app
echo -e "${GREEN}Deploying PostgreSQL...${NC}"
kubectl apply -n ${NAMESPACE} -f import-yaml-files/postgres-deployment.yaml
kubectl apply -n ${NAMESPACE} -f import-yaml-files/postgres-service.yaml

# Deploy the application
echo -e "${GREEN}Deploying nginx config and application...${NC}"
kubectl apply -n ${NAMESPACE} -f import-yaml-files/nginx-config.yaml
kubectl apply -n ${NAMESPACE} -f import-yaml-files/app-deployment.yaml
kubectl apply -n ${NAMESPACE} -f import-yaml-files/app-service.yaml

echo -e "${GREEN}Minimal Deployment completed!${NC}"
echo -e "${YELLOW}Current pod status:${NC}"
kubectl get pods -n ${NAMESPACE}

# Print service access information
echo -e "${YELLOW}Access your application:${NC}"
echo -e "Use port-forwarding to access the application:"
echo -e "kubectl port-forward -n ${NAMESPACE} svc/l1-monitoring 8080:80"
echo -e "Then access at: http://localhost:8080"

# Display resource usage summary
echo -e "\n${YELLOW}Resource Usage Summary:${NC}"
echo -e "This minimal deployment uses approximately:"
echo -e "- App: 64Mi memory, 20m CPU"
echo -e "- PostgreSQL: 64Mi memory, 20m CPU"
echo -e "Total approximate resource usage: ~128Mi memory, 0.04 CPU cores"

echo -e "\n${YELLOW}Note:${NC} This deployment does not include ClickHouse or Ollama to save resources."
echo -e "The application will automatically fall back to using PostgreSQL for data storage."
echo -e "Advanced AI features will use mocked responses in this minimal setup."