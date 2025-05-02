# L1 Monitoring Application - Kubernetes Deployment Guide

This guide provides instructions for deploying the L1 Monitoring application in a Kubernetes environment.

## Deployment Options

We provide two main deployment options:

1. **Namespace-isolated deployment** - Recommended for clean installation
2. **Image-less deployment** - For environments without Docker access

## Prerequisites

- Kubernetes cluster (v1.19+)
- kubectl configured to connect to your cluster
- 8GB+ of available memory (16GB+ recommended)
- Storage for persistent volumes

## Deployment Steps

### Option 1: Namespace-isolated Deployment

```bash
# Clone the repository 
git clone https://github.com/yourusername/l1-monitoring-app.git
cd l1-monitoring-app/k8s

# Make the script executable
chmod +x fresh-namespace-deployment.sh

# Run the deployment script
./fresh-namespace-deployment.sh
```

### Option 2: Image-less Deployment

If you don't have Docker access or prefer not to build custom images:

```bash
# Clone the repository
git clone https://github.com/yourusername/l1-monitoring-app.git
cd l1-monitoring-app/k8s

# Make the script executable
chmod +x image-less-deployment.sh

# Run the image-less deployment script
./image-less-deployment.sh
```

## Accessing the Application

After deployment is complete, you can access the application using:

1. **Ingress** (if enabled in your cluster):
   - Access via: http://l1-monitoring.local
   - Note: You may need to add an entry to your hosts file

2. **Port Forwarding**:
   ```bash
   kubectl port-forward -n l1-monitoring svc/l1-monitoring 8080:80
   ```
   Then access via: http://localhost:8080

## Component Status

Verify that all components are running:

```bash
kubectl get pods -n l1-monitoring
```

You should see pods for:
- l1-monitoring (the main application)
- postgres (database)
- clickhouse (analytics database)
- ollama (LLM service)

## Troubleshooting

If you encounter issues:

1. Check pod status:
   ```bash
   kubectl get pods -n l1-monitoring
   ```

2. Check pod logs:
   ```bash
   kubectl logs -n l1-monitoring <pod-name>
   ```

3. Common issues:
   - **Pending pods**: Check for resource constraints
   - **CrashLoopBackOff**: Check container logs for errors
   - **Init container failures**: May indicate volume mount issues

For detailed troubleshooting, refer to [troubleshooting.md](troubleshooting.md).