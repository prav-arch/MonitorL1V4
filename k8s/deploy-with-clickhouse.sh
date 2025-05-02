#!/bin/bash

# L1 Monitoring App Kubernetes Deployment Script with ClickHouse
# This script deploys the L1 Monitoring application to a Kubernetes cluster
# with ClickHouse as the primary database

# Color codes for terminal output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Print colored messages
info() {
    echo -e "${BLUE}[INFO] $1${NC}"
}

success() {
    echo -e "${GREEN}[SUCCESS] $1${NC}"
}

warn() {
    echo -e "${YELLOW}[WARNING] $1${NC}"
}

error() {
    echo -e "${RED}[ERROR] $1${NC}"
}

# Check if kubectl is installed
if ! command -v kubectl &> /dev/null; then
    error "kubectl is not installed. Please install kubectl first."
    exit 1
fi

# Check if current context is set
if ! kubectl config current-context &> /dev/null; then
    error "No Kubernetes context is set. Please set a context with 'kubectl config use-context <context>'"
    exit 1
fi

info "Using Kubernetes context: $(kubectl config current-context)"

# Check if secrets file exists
if [ ! -f "secrets/secrets.yaml" ]; then
    warn "Secrets file not found at secrets/secrets.yaml"
    info "Creating secrets file from template..."
    
    if [ ! -f "secrets/secrets-template.yaml" ]; then
        error "Secrets template file not found at secrets/secrets-template.yaml"
        exit 1
    fi
    
    cp secrets/secrets-template.yaml secrets/secrets.yaml
    warn "Please edit secrets/secrets.yaml to set your actual secret values before proceeding."
    warn "Run this script again after updating the secrets file."
    exit 1
fi

# Deploy persistent volume claims
info "Creating persistent volume claims..."
kubectl apply -f volumes/persistent-volume-claims.yaml
if [ $? -ne 0 ]; then
    error "Failed to create persistent volume claims. Check storage class and permissions."
    exit 1
fi
success "Persistent volume claims created successfully"

# Deploy secrets
info "Applying secrets..."
kubectl apply -f secrets/secrets.yaml
if [ $? -ne 0 ]; then
    error "Failed to apply secrets."
    exit 1
fi
success "Secrets applied successfully"

# Deploy ClickHouse database
info "Deploying ClickHouse database..."
kubectl apply -f deployments/clickhouse-deployment.yaml
kubectl apply -f services/clickhouse-service.yaml
if [ $? -ne 0 ]; then
    error "Failed to deploy ClickHouse"
    exit 1
fi
success "ClickHouse database deployed successfully"

# Deploy PostgreSQL database as fallback
info "Deploying PostgreSQL database as fallback..."
kubectl apply -f deployments/postgres-deployment.yaml
kubectl apply -f services/postgres-service.yaml
if [ $? -ne 0 ]; then
    error "Failed to deploy PostgreSQL fallback database"
    exit 1
fi
success "PostgreSQL database deployed successfully"

# Deploy OLLAMA
info "Deploying OLLAMA for local LLM support..."
kubectl apply -f configmaps/ollama-init.yaml
kubectl apply -f deployments/ollama-deployment.yaml
kubectl apply -f services/ollama-service.yaml
if [ $? -ne 0 ]; then
    error "Failed to deploy OLLAMA"
    exit 1
fi
success "OLLAMA deployed successfully"

# Wait for databases to be ready
info "Waiting for databases to be ready..."
kubectl wait --for=condition=available --timeout=300s deployment/clickhouse
kubectl wait --for=condition=available --timeout=300s deployment/postgres

# Deploy the application
info "Deploying L1 Monitoring application..."
kubectl apply -f deployments/app-deployment.yaml
kubectl apply -f services/app-service.yaml
if [ $? -ne 0 ]; then
    error "Failed to deploy L1 Monitoring application"
    exit 1
fi
success "L1 Monitoring application deployed successfully"

# Deploy ingress
info "Deploying ingress for external access..."
kubectl apply -f ingress/app-ingress.yaml
if [ $? -ne 0 ]; then
    warn "Failed to deploy ingress. This may be normal if your cluster doesn't support ingress."
    warn "You can access the application via port-forwarding: kubectl port-forward svc/l1-monitoring 5000:5000"
else
    success "Ingress deployed successfully"
fi

# Get deployment status
info "Checking deployment status..."
echo ""
echo "ClickHouse Database:"
kubectl get deployment clickhouse
echo ""
echo "PostgreSQL Database:"
kubectl get deployment postgres
echo ""
echo "OLLAMA LLM Service:"
kubectl get deployment ollama
echo ""
echo "L1 Monitoring Application:"
kubectl get deployment l1-monitoring
echo ""
echo "Services:"
kubectl get svc | grep -E 'clickhouse|postgres|ollama|l1-monitoring'
echo ""

if kubectl get ingress &> /dev/null; then
    echo "Ingress:"
    kubectl get ingress
    echo ""
    INGRESS_HOST=$(kubectl get ingress app-ingress -o jsonpath='{.status.loadBalancer.ingress[0].ip}')
    if [ -n "$INGRESS_HOST" ]; then
        success "Application is accessible at: http://${INGRESS_HOST}"
    else
        warn "Ingress IP not available yet. Check ingress status with: kubectl get ingress"
    fi
else
    warn "No ingress found. Use port-forwarding to access the application:"
    echo "kubectl port-forward svc/l1-monitoring 5000:5000"
    echo "Then access the application at: http://localhost:5000"
fi

success "Deployment completed successfully!"
info "Helpful commands:"
echo "  kubectl logs deployment/l1-monitoring             # View application logs"
echo "  kubectl logs deployment/clickhouse                # View ClickHouse logs"
echo "  kubectl exec -it deployment/clickhouse -- bash    # Connect to ClickHouse shell"
echo "  kubectl port-forward svc/l1-monitoring 5000:5000  # Forward application port"