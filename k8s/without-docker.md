# Kubernetes Deployment Without Docker

If you're facing issues connecting to the Docker daemon socket, there are two options:

1. Fix the Docker socket permissions issue (recommended if you need to build custom images)
2. Deploy using pre-built images only (no Docker needed)

## Option 1: Fix Docker Socket Permissions

The "Permission denied while trying to connect to the Docker daemon socket" error occurs when your user doesn't have permission to access the Docker socket.

**To fix this issue:**

```bash
# Make the fix-docker-socket-permission.sh script executable
chmod +x k8s/fix-docker-socket-permission.sh

# Run the script with sudo
sudo ./k8s/fix-docker-socket-permission.sh
```

After running this script:
1. Log out and log back in for the group changes to take effect
2. Or run `newgrp docker` to apply the group membership changes without logging out
3. Test that Docker works with `docker info`

## Option 2: Deploy Without Docker

If you prefer not to use Docker or can't fix the permission issues, you can deploy using pre-built images only.

**To deploy without Docker:**

```bash
# Make the image-less-deployment.sh script executable
chmod +x k8s/image-less-deployment.sh

# Run the script with the desired namespace
./k8s/image-less-deployment.sh l1-monitoring
```

This script:
1. Creates a clean namespace
2. Deploys standard images (Postgres, ClickHouse, Ollama, Nginx)
3. Uses emptyDir volumes (no persistent storage needed)
4. Creates a NodePort service for external access
5. Requires no Docker build process

## Key Differences in the No-Docker Approach

1. Uses Nginx as a placeholder for the main application
2. Configures a basic API response for health checks
3. Creates a NodePort service for easier access
4. Uses minimal resource requirements suitable for testing

## Verifying the Deployment

After running either deployment method:

```bash
# Check all resources in the namespace
kubectl get all -n l1-monitoring

# For the no-Docker deployment, get the NodePort
kubectl get svc l1-monitoring-external -n l1-monitoring
```

The NodePort service will expose your application on a random port (typically 30000-32767). You can access it using:

```
http://<node-ip>:<node-port>
```

## Troubleshooting

If you still experience issues with the deployment:

1. Check logs for specific pods:
   ```bash
   kubectl logs -f <pod-name> -n l1-monitoring
   ```

2. Describe pods to see events:
   ```bash
   kubectl describe pod <pod-name> -n l1-monitoring
   ```

3. Check node capacity:
   ```bash
   kubectl describe nodes
   ```

4. For persistent volume issues, consider editing the deployment to use emptyDir volumes instead of PVCs.

For more detailed troubleshooting, refer to `k8s/v2-deployment-troubleshooting.md`.