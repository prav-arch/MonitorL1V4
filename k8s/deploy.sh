#!/bin/bash
# Deployment script for L1 Monitoring Application

set -e

# Configuration variables
REGISTRY="<your-registry>"
APP_IMAGE_NAME="l1-monitoring"
APP_IMAGE_TAG="latest"
NAMESPACE="default"

# Color codes for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Print header
echo -e "${GREEN}=========================================${NC}"
echo -e "${GREEN}   L1 Monitoring Deployment Script       ${NC}"
echo -e "${GREEN}=========================================${NC}"

# Check if kubectl is installed
if ! command -v kubectl &> /dev/null; then
    echo -e "${RED}Error: kubectl is not installed.${NC}"
    exit 1
fi

# Check if valid kubeconfig exists
if ! kubectl cluster-info &> /dev/null; then
    echo -e "${RED}Error: Cannot communicate with Kubernetes cluster.${NC}"
    echo "Please check your kubeconfig and cluster connection."
    exit 1
fi

# Create namespace if it doesn't exist
echo -e "\n${YELLOW}Checking namespace...${NC}"
if ! kubectl get namespace $NAMESPACE &> /dev/null; then
    echo -e "Creating namespace ${NAMESPACE}..."
    kubectl create namespace $NAMESPACE
else
    echo -e "Namespace ${NAMESPACE} already exists."
fi

# Create secrets
if [ ! -f "k8s/secrets/secrets.yaml" ]; then
    echo -e "\n${RED}Error: secrets.yaml not found.${NC}"
    echo "Please create k8s/secrets/secrets.yaml from the template before continuing."
    exit 1
fi

echo -e "\n${YELLOW}Applying secrets...${NC}"
kubectl apply -f k8s/secrets/secrets.yaml -n $NAMESPACE

# Create persistent volume claims
echo -e "\n${YELLOW}Creating persistent volume claims...${NC}"
kubectl apply -f k8s/volumes/persistent-volume-claims.yaml -n $NAMESPACE

# Deploy PostgreSQL
echo -e "\n${YELLOW}Deploying PostgreSQL...${NC}"
kubectl apply -f k8s/deployments/postgres-deployment.yaml -n $NAMESPACE
kubectl apply -f k8s/services/postgres-service.yaml -n $NAMESPACE

# Wait for PostgreSQL to be ready
echo -e "\n${YELLOW}Waiting for PostgreSQL to be ready...${NC}"
kubectl wait --for=condition=ready pod -l app=postgres -n $NAMESPACE --timeout=120s

# Deploy OLLAMA
echo -e "\n${YELLOW}Deploying OLLAMA...${NC}"
kubectl apply -f k8s/configmaps/ollama-init.yaml -n $NAMESPACE
kubectl apply -f k8s/deployments/ollama-deployment.yaml -n $NAMESPACE
kubectl apply -f k8s/services/ollama-service.yaml -n $NAMESPACE

echo -e "\n${YELLOW}OLLAMA is being deployed. The init container will download models.${NC}"
echo -e "This may take several minutes. You can check the status with:"
echo -e "  kubectl logs -f -l app=ollama -c init-ollama -n $NAMESPACE"

# Ask user if they want to continue with app deployment
echo -e "\n${YELLOW}Do you want to wait for OLLAMA initialization? (y/n)${NC}"
read -r wait_response
if [[ "$wait_response" =~ ^[Yy]$ ]]; then
    echo -e "\n${YELLOW}Waiting for OLLAMA init container to complete...${NC}"
    kubectl wait --for=condition=ready pod -l app=ollama -n $NAMESPACE --timeout=600s
fi

# Check if the image needs to be built and pushed
echo -e "\n${YELLOW}Do you need to build and push the application image? (y/n)${NC}"
read -r build_response
if [[ "$build_response" =~ ^[Yy]$ ]]; then
    # Check if Docker is installed
    if ! command -v docker &> /dev/null; then
        echo -e "${RED}Error: Docker is not installed.${NC}"
        exit 1
    fi
    
    # Build and push the image
    echo -e "\n${YELLOW}Building application image...${NC}"
    docker build -t ${REGISTRY}/${APP_IMAGE_NAME}:${APP_IMAGE_TAG} .
    
    echo -e "\n${YELLOW}Pushing image to registry...${NC}"
    docker push ${REGISTRY}/${APP_IMAGE_NAME}:${APP_IMAGE_TAG}
    
    # Update the deployment file
    echo -e "\n${YELLOW}Updating deployment image reference...${NC}"
    sed -i "s|\${YOUR_REGISTRY}|${REGISTRY}|g" k8s/deployments/app-deployment.yaml
fi

# Deploy the application
echo -e "\n${YELLOW}Deploying the application...${NC}"
kubectl apply -f k8s/deployments/app-deployment.yaml -n $NAMESPACE
kubectl apply -f k8s/services/app-service.yaml -n $NAMESPACE

# Wait for the application to be ready
echo -e "\n${YELLOW}Waiting for the application to be ready...${NC}"
kubectl wait --for=condition=ready pod -l app=l1-monitoring -n $NAMESPACE --timeout=120s

# Deploy ingress if requested
echo -e "\n${YELLOW}Do you want to deploy the ingress? (y/n)${NC}"
read -r ingress_response
if [[ "$ingress_response" =~ ^[Yy]$ ]]; then
    echo -e "\n${YELLOW}Please update the hostname in k8s/ingress/app-ingress.yaml before continuing.${NC}"
    echo -e "Current value: $(grep -o 'host: .*' k8s/ingress/app-ingress.yaml | cut -d ' ' -f 2)"
    echo -e "\n${YELLOW}Proceed with deploying ingress? (y/n)${NC}"
    read -r proceed_ingress
    
    if [[ "$proceed_ingress" =~ ^[Yy]$ ]]; then
        echo -e "\n${YELLOW}Deploying ingress...${NC}"
        kubectl apply -f k8s/ingress/app-ingress.yaml -n $NAMESPACE
    fi
fi

# Display deployment status
echo -e "\n${GREEN}Deployment completed!${NC}"
echo -e "\n${YELLOW}Deployment Status:${NC}"
kubectl get deployments -n $NAMESPACE
echo -e "\n${YELLOW}Service Status:${NC}"
kubectl get services -n $NAMESPACE
echo -e "\n${YELLOW}Pod Status:${NC}"
kubectl get pods -n $NAMESPACE

# Forward port for local testing
echo -e "\n${YELLOW}Do you want to port-forward the service for local testing? (y/n)${NC}"
read -r forward_response
if [[ "$forward_response" =~ ^[Yy]$ ]]; then
    echo -e "\n${GREEN}Port forwarding l1-monitoring-service to http://localhost:8080${NC}"
    echo -e "Press Ctrl+C to stop port forwarding"
    kubectl port-forward svc/l1-monitoring-service 8080:80 -n $NAMESPACE
fi

echo -e "\n${GREEN}Deployment complete!${NC}"