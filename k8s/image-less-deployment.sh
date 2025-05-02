#!/bin/bash
# Script for Kubernetes deployment without requiring Docker image builds
# This version modifies the fresh-namespace-deployment.sh to use existing images only

# Define namespace for deployment
NAMESPACE="l1-monitoring"

# Check if namespace parameter is provided
if [ "$1" != "" ]; then
  NAMESPACE="$1"
  echo "Using custom namespace: $NAMESPACE"
fi

# Create namespace if it doesn't exist
if ! kubectl get namespace $NAMESPACE &> /dev/null; then
  echo "Creating namespace: $NAMESPACE"
  kubectl create namespace $NAMESPACE
else
  echo "Namespace $NAMESPACE already exists"
fi

# Clean up any existing deployments in the namespace
echo "Cleaning up existing resources in namespace: $NAMESPACE"
kubectl delete --all deployments --namespace=$NAMESPACE
kubectl delete --all services --namespace=$NAMESPACE
kubectl delete --all pods --namespace=$NAMESPACE
kubectl delete --all pvc --namespace=$NAMESPACE
kubectl delete --all configmaps --namespace=$NAMESPACE
kubectl delete --all secrets --namespace=$NAMESPACE
kubectl delete --all ingress --namespace=$NAMESPACE

# Wait for resources to be deleted
echo "Waiting for resources to be deleted..."
sleep 5

# Create secrets
echo "Creating secrets in namespace: $NAMESPACE"
cat <<EOF | kubectl apply -f - -n $NAMESPACE
apiVersion: v1
kind: Secret
metadata:
  name: l1-monitoring-secrets
type: Opaque
data:
  postgres-db: cG9zdGdyZXM=        # postgres
  postgres-user: cG9zdGdyZXM=       # postgres
  postgres-password: cG9zdGdyZXM=   # postgres
  clickhouse-user: ZGVmYXVsdA==     # default
  clickhouse-password: 
  ollama-api-key: 
  app-secret-key: bDFtb25pdG9yaW5nc2VjcmV0a2V5  # l1monitoringsecretkey
EOF

# Create persistent volume claims with emptyDir instead
echo "Creating deployments with emptyDir volumes in namespace: $NAMESPACE"

# Create PostgreSQL deployment
echo "Creating PostgreSQL deployment in namespace: $NAMESPACE"
cat <<EOF | kubectl apply -f - -n $NAMESPACE
apiVersion: apps/v1
kind: Deployment
metadata:
  name: postgres
  labels:
    app: postgres
spec:
  replicas: 1
  selector:
    matchLabels:
      app: postgres
  template:
    metadata:
      labels:
        app: postgres
    spec:
      # Add tolerations for scheduling flexibility
      tolerations:
      - key: "node.kubernetes.io/not-ready"
        operator: "Exists"
        effect: "NoExecute"
        tolerationSeconds: 300
      - key: "node.kubernetes.io/unreachable"
        operator: "Exists"
        effect: "NoExecute"
        tolerationSeconds: 300
      - key: "node-role.kubernetes.io/master"
        operator: "Exists"
        effect: "NoSchedule"
      containers:
      - name: postgres
        image: postgres:14
        imagePullPolicy: IfNotPresent
        ports:
        - containerPort: 5432
          name: postgres
        env:
        - name: POSTGRES_DB
          value: "postgres"
        - name: POSTGRES_USER
          value: "postgres"
        - name: POSTGRES_PASSWORD
          value: "postgres"
        resources:
          requests:
            memory: "256Mi"
            cpu: "100m"
          limits:
            memory: "512Mi"
            cpu: "250m"
        volumeMounts:
        - name: postgres-data
          mountPath: /var/lib/postgresql/data
          subPath: postgres-data
      volumes:
      - name: postgres-data
        emptyDir: {}
EOF

# Create PostgreSQL service
echo "Creating PostgreSQL service in namespace: $NAMESPACE"
cat <<EOF | kubectl apply -f - -n $NAMESPACE
apiVersion: v1
kind: Service
metadata:
  name: postgres
  labels:
    app: postgres
spec:
  selector:
    app: postgres
  ports:
  - port: 5432
    targetPort: 5432
    name: postgres
  type: ClusterIP
EOF

# Create ClickHouse deployment
echo "Creating ClickHouse deployment in namespace: $NAMESPACE"
cat <<EOF | kubectl apply -f - -n $NAMESPACE
apiVersion: apps/v1
kind: Deployment
metadata:
  name: clickhouse
  labels:
    app: clickhouse
spec:
  replicas: 1
  selector:
    matchLabels:
      app: clickhouse
  template:
    metadata:
      labels:
        app: clickhouse
    spec:
      # Add tolerations for scheduling flexibility
      tolerations:
      - key: "node.kubernetes.io/not-ready"
        operator: "Exists"
        effect: "NoExecute"
        tolerationSeconds: 300
      - key: "node.kubernetes.io/unreachable"
        operator: "Exists"
        effect: "NoExecute"
        tolerationSeconds: 300
      - key: "node-role.kubernetes.io/master"
        operator: "Exists"
        effect: "NoSchedule"
      containers:
      - name: clickhouse
        image: clickhouse/clickhouse-server:latest
        imagePullPolicy: IfNotPresent
        ports:
        - containerPort: 8123  # HTTP port
          name: http
        - containerPort: 9000  # Native port
          name: native
        resources:
          requests:
            memory: "512Mi"
            cpu: "100m"
          limits:
            memory: "1Gi"
            cpu: "250m"
        volumeMounts:
        - name: clickhouse-data
          mountPath: /var/lib/clickhouse
        env:
        - name: CLICKHOUSE_USER
          value: "default"
        - name: CLICKHOUSE_PASSWORD
          value: ""
        - name: CLICKHOUSE_DB
          value: "default"
        livenessProbe:
          httpGet:
            path: /ping
            port: http
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /ping
            port: http
          initialDelaySeconds: 30
          periodSeconds: 10
      volumes:
      - name: clickhouse-data
        emptyDir: {}
EOF

# Create ClickHouse service
echo "Creating ClickHouse service in namespace: $NAMESPACE"
cat <<EOF | kubectl apply -f - -n $NAMESPACE
apiVersion: v1
kind: Service
metadata:
  name: clickhouse
  labels:
    app: clickhouse
spec:
  selector:
    app: clickhouse
  ports:
  - port: 8123
    targetPort: 8123
    name: http
  - port: 9000
    targetPort: 9000
    name: native
  type: ClusterIP
EOF

# Create Ollama deployment
echo "Creating Ollama deployment in namespace: $NAMESPACE"
cat <<EOF | kubectl apply -f - -n $NAMESPACE
apiVersion: apps/v1
kind: Deployment
metadata:
  name: ollama
  labels:
    app: ollama
spec:
  replicas: 1
  selector:
    matchLabels:
      app: ollama
  template:
    metadata:
      labels:
        app: ollama
    spec:
      # Add tolerations for common taints
      tolerations:
      - key: "node.kubernetes.io/not-ready"
        operator: "Exists"
        effect: "NoExecute"
        tolerationSeconds: 300
      - key: "node.kubernetes.io/unreachable"
        operator: "Exists"
        effect: "NoExecute"
        tolerationSeconds: 300
      # Add more specific tolerations based on your cluster's taints
      - key: "node-role.kubernetes.io/master"
        operator: "Exists"
        effect: "NoSchedule"
      containers:
      - name: ollama-service
        image: ollama/ollama:latest
        imagePullPolicy: IfNotPresent
        ports:
        - containerPort: 11434
          name: api
        resources:
          requests:
            memory: "512Mi"
            cpu: "100m"
          limits:
            memory: "2Gi"
            cpu: "500m"
        volumeMounts:
        - name: ollama-data
          mountPath: /root/.ollama
        lifecycle:
          postStart:
            exec:
              command: 
              - "/bin/sh"
              - "-c"
              - "ollama serve & sleep 30 && ollama pull llama2 || true"
        readinessProbe:
          httpGet:
            path: /api/health
            port: 11434
          initialDelaySeconds: 60
          periodSeconds: 10
          timeoutSeconds: 5
          successThreshold: 1
          failureThreshold: 10
      volumes:
      - name: ollama-data
        emptyDir: {}
EOF

# Create Ollama service
echo "Creating Ollama service in namespace: $NAMESPACE"
cat <<EOF | kubectl apply -f - -n $NAMESPACE
apiVersion: v1
kind: Service
metadata:
  name: ollama
  labels:
    app: ollama
spec:
  selector:
    app: ollama
  ports:
  - port: 11434
    targetPort: 11434
    name: api
  type: ClusterIP
EOF

# Create nginx deployment for hosting the application
echo "Creating Nginx deployment in namespace: $NAMESPACE"
cat <<EOF | kubectl apply -f - -n $NAMESPACE
apiVersion: apps/v1
kind: Deployment
metadata:
  name: l1-monitoring
  labels:
    app: l1-monitoring
spec:
  replicas: 1
  selector:
    matchLabels:
      app: l1-monitoring
  template:
    metadata:
      labels:
        app: l1-monitoring
    spec:
      # Add tolerations for scheduling flexibility
      tolerations:
      - key: "node.kubernetes.io/not-ready"
        operator: "Exists"
        effect: "NoExecute"
        tolerationSeconds: 300
      - key: "node.kubernetes.io/unreachable"
        operator: "Exists"
        effect: "NoExecute"
        tolerationSeconds: 300
      - key: "node-role.kubernetes.io/master"
        operator: "Exists"
        effect: "NoSchedule"
      containers:
      - name: l1-monitoring-app
        # Using nginx as a placeholder - replace with your actual image when available
        image: nginx:alpine
        imagePullPolicy: IfNotPresent
        ports:
        - containerPort: 80
          name: http
        resources:
          requests:
            memory: "256Mi"
            cpu: "100m"
          limits:
            memory: "512Mi"
            cpu: "250m"
        volumeMounts:
        - name: nginx-config
          mountPath: /etc/nginx/conf.d/default.conf
          subPath: default.conf
        readinessProbe:
          httpGet:
            path: /
            port: 80
          initialDelaySeconds: 10
          periodSeconds: 5
        livenessProbe:
          httpGet:
            path: /
            port: 80
          initialDelaySeconds: 15
          periodSeconds: 10
      volumes:
      - name: nginx-config
        configMap:
          name: nginx-config
          items:
          - key: config
            path: default.conf
EOF

# Create Nginx config for the application
echo "Creating Nginx configuration in namespace: $NAMESPACE"
cat <<EOF | kubectl apply -f - -n $NAMESPACE
apiVersion: v1
kind: ConfigMap
metadata:
  name: nginx-config
data:
  config: |
    server {
        listen 80;
        server_name localhost;

        location / {
            root   /usr/share/nginx/html;
            index  index.html index.htm;
        }

        location /api {
            return 200 '{"status": "ok", "message": "L1 Monitoring API placeholder"}';
            add_header Content-Type application/json;
        }

        location /api/health {
            return 200 '{"status": "healthy", "uptime": "0d 0h 0m", "components": {"postgres": "ok", "clickhouse": "ok", "ollama": "ok"}}';
            add_header Content-Type application/json;
        }

        error_page   500 502 503 504  /50x.html;
        location = /50x.html {
            root   /usr/share/nginx/html;
        }
    }
EOF

# Create main application service
echo "Creating L1 Monitoring application service in namespace: $NAMESPACE"
cat <<EOF | kubectl apply -f - -n $NAMESPACE
apiVersion: v1
kind: Service
metadata:
  name: l1-monitoring
  labels:
    app: l1-monitoring
spec:
  selector:
    app: l1-monitoring
  ports:
  - port: 80
    targetPort: 80
    name: http
  type: ClusterIP
EOF

# Create NodePort service for external access
echo "Creating NodePort service for external access in namespace: $NAMESPACE"
cat <<EOF | kubectl apply -f - -n $NAMESPACE
apiVersion: v1
kind: Service
metadata:
  name: l1-monitoring-external
  labels:
    app: l1-monitoring
spec:
  selector:
    app: l1-monitoring
  ports:
  - port: 80
    targetPort: 80
    name: http
  type: NodePort
EOF

# Wait for pods to start
echo "Waiting for pods to start in namespace: $NAMESPACE"
sleep 5

# Check deployment status
echo "Current deployments in namespace: $NAMESPACE"
kubectl get deployments -n $NAMESPACE

echo "Current pods in namespace: $NAMESPACE"
kubectl get pods -n $NAMESPACE

echo "Current services in namespace: $NAMESPACE"
kubectl get services -n $NAMESPACE

# Get the NodePort
NODE_PORT=$(kubectl get svc l1-monitoring-external -n $NAMESPACE -o jsonpath='{.spec.ports[0].nodePort}')

# Instructions for verifying the deployment
echo ""
echo "================================================"
echo "Deployment to namespace '$NAMESPACE' is complete!"
echo "================================================"
echo ""
echo "To monitor pod status, run:"
echo "  kubectl get pods -n $NAMESPACE -w"
echo ""
echo "To check Ollama logs, run:"
echo "  kubectl logs -f \$(kubectl get pods -n $NAMESPACE -l app=ollama -o jsonpath='{.items[0].metadata.name}') -n $NAMESPACE"
echo ""
echo "You can access the application externally on port $NODE_PORT:"
echo "  http://<node-ip>:$NODE_PORT"
echo ""
echo "To check for any scheduling issues, run:"
echo "  kubectl describe pods -n $NAMESPACE | grep -A10 'Events:'"