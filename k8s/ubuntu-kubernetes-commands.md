# Ubuntu Kubernetes Deployment Commands

Since kubectl isn't available in the Replit environment, you'll need to run these commands on your Ubuntu system with Kubernetes installed. Here's a step-by-step guide to deploy the L1 Monitoring application to a dedicated namespace without needing Docker.

## Prerequisites on Ubuntu

Before starting, ensure your Ubuntu system has:

1. Kubernetes installed (minikube, microk8s, or kubeadm)
2. kubectl command available and configured

## Step 1: Copy the files to your Ubuntu system

First, download the necessary files from this Replit to your Ubuntu system:

1. Download the `k8s/image-less-deployment.sh` file
2. Make it executable: `chmod +x image-less-deployment.sh`

## Step 2: Verify Kubernetes is running

```bash
# Check Kubernetes nodes
kubectl get nodes

# Check if you can create resources
kubectl auth can-i create namespace
kubectl auth can-i create deployment
```

## Step 3: Create a namespace and deploy

```bash
# Run the deployment script
./image-less-deployment.sh l1-monitoring
```

This script will:
- Create a dedicated namespace called `l1-monitoring`
- Deploy standard images (Postgres, ClickHouse, Ollama, Nginx)
- Set up all necessary services and configurations
- Create a NodePort service for external access

## Step 4: Verify deployment

```bash
# Check all resources in the namespace
kubectl get all -n l1-monitoring

# Get the NodePort for external access
NODEPORT=$(kubectl get svc l1-monitoring-external -n l1-monitoring -o jsonpath='{.spec.ports[0].nodePort}')
echo "The application is available at: http://<your-node-ip>:$NODEPORT"
```

## Step 5: Access the application

1. Find your node's IP address:
   ```bash
   # For minikube
   minikube ip
   
   # For standard Kubernetes
   kubectl get nodes -o wide
   ```

2. Access the application at: `http://<node-ip>:<node-port>`

## Manual Deployment Commands

If you prefer to run individual commands instead of the script, here are the key ones:

```bash
# Create namespace
kubectl create namespace l1-monitoring

# Deploy Postgres
kubectl apply -f postgres-deployment.yaml -n l1-monitoring
kubectl apply -f postgres-service.yaml -n l1-monitoring

# Deploy ClickHouse
kubectl apply -f clickhouse-deployment.yaml -n l1-monitoring
kubectl apply -f clickhouse-service.yaml -n l1-monitoring

# Deploy Ollama
kubectl apply -f ollama-deployment.yaml -n l1-monitoring
kubectl apply -f ollama-service.yaml -n l1-monitoring

# Deploy the application (Nginx placeholder)
kubectl apply -f app-deployment.yaml -n l1-monitoring
kubectl apply -f app-service.yaml -n l1-monitoring
```

## Troubleshooting

If you encounter issues:

1. Check pod status:
   ```bash
   kubectl get pods -n l1-monitoring
   ```

2. View pod logs:
   ```bash
   kubectl logs <pod-name> -n l1-monitoring
   ```

3. Describe problematic pods:
   ```bash
   kubectl describe pod <pod-name> -n l1-monitoring
   ```

4. For resource constraints, edit the deployment:
   ```bash
   kubectl edit deployment <deployment-name> -n l1-monitoring
   ```
   Reduce the resource requests/limits if needed.