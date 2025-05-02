# L1 Monitoring Application - Kubernetes Troubleshooting Guide

This document provides detailed troubleshooting steps for common issues encountered when deploying the L1 Monitoring application in Kubernetes.

## Table of Contents
1. [Checking Deployment Status](#checking-deployment-status)
2. [Common Issues and Solutions](#common-issues-and-solutions)
3. [Ollama-Specific Issues](#ollama-specific-issues)
4. [ClickHouse-Specific Issues](#clickhouse-specific-issues)
5. [Application Connectivity Issues](#application-connectivity-issues)
6. [Resource Constraints](#resource-constraints)
7. [Node Scheduling Problems](#node-scheduling-problems)

## Checking Deployment Status

First, verify the status of all components:

```bash
# Check pods
kubectl -n l1-monitoring get pods

# Check services
kubectl -n l1-monitoring get svc

# Check deployments
kubectl -n l1-monitoring get deployments

# Check persistent volume claims
kubectl -n l1-monitoring get pvc
```

## Common Issues and Solutions

### Pods Stuck in "Pending" State

**Symptoms:**
- Pods remain in "Pending" state

**Possible causes:**
1. Insufficient cluster resources
2. PersistentVolumeClaim not being bound
3. Node taints preventing scheduling

**Solutions:**
```bash
# Check node capacity and allocatable resources
kubectl describe nodes

# Check if PVCs are bound
kubectl -n l1-monitoring get pvc

# Check if pods have tolerations for node taints
kubectl -n l1-monitoring describe pod <pod-name>
```

### Pods in "CrashLoopBackOff" State

**Symptoms:**
- Pods continuously restart
- Status shows "CrashLoopBackOff"

**Solutions:**
```bash
# Check logs
kubectl -n l1-monitoring logs <pod-name>

# Check events
kubectl -n l1-monitoring get events
```

### Pods in "ImagePullBackOff" State

**Symptoms:**
- Image cannot be pulled from registry

**Solutions:**
```bash
# Check events for image pull errors
kubectl -n l1-monitoring get events | grep <pod-name>

# For private registries, verify secrets
kubectl -n l1-monitoring get secrets
```

## Ollama-Specific Issues

Ollama requires significant resources to run properly:

**Common issues:**
1. Container crashes due to memory limits
2. Slow startup times when pulling models
3. Model download failures

**Solutions:**
```bash
# Increase memory limits in deployment
kubectl -n l1-monitoring edit deployment ollama

# Check Ollama logs during startup
kubectl -n l1-monitoring logs <ollama-pod-name>

# Verify network connectivity for model downloads
kubectl -n l1-monitoring exec <ollama-pod-name> -- ping huggingface.co
```

## ClickHouse-Specific Issues

**Common issues:**
1. ClickHouse service unavailable
2. Database initialization failures
3. Connection refused errors

**Solutions:**
```bash
# Check ClickHouse logs
kubectl -n l1-monitoring logs <clickhouse-pod-name>

# Verify ClickHouse service
kubectl -n l1-monitoring describe svc clickhouse

# Test connection from another pod
kubectl -n l1-monitoring exec <any-pod> -- curl -v clickhouse:8123
```

## Application Connectivity Issues

If the application cannot connect to its dependencies:

**Symptoms:**
- Error logs showing connection failures
- Service functionality degraded

**Solutions:**
```bash
# Check if DNS resolution works
kubectl -n l1-monitoring exec <app-pod> -- nslookup postgres
kubectl -n l1-monitoring exec <app-pod> -- nslookup clickhouse
kubectl -n l1-monitoring exec <app-pod> -- nslookup ollama

# Verify service endpoints
kubectl -n l1-monitoring get endpoints
```

## Resource Constraints

If your cluster has limited resources:

**Solutions:**
1. Reduce resource requests/limits in deployment YAML files
2. Add more nodes to your cluster
3. Use a node with more resources

```bash
# Edit deployment to reduce resource requests
kubectl -n l1-monitoring edit deployment <deployment-name>
```

## Node Scheduling Problems

If pods won't schedule on certain nodes:

**Symptoms:**
- Pods remain in "Pending" state
- Events show scheduling conflicts

**Solutions:**
```bash
# Add tolerations to deployment
kubectl -n l1-monitoring edit deployment <deployment-name>

# Common tolerations to add:
tolerations:
- key: "node-role.kubernetes.io/master"
  operator: "Exists"
  effect: "NoSchedule"
```

## Re-applying the Full Deployment

If you need to start over:

```bash
# Delete namespace and recreate
kubectl delete namespace l1-monitoring
kubectl apply -f import-yaml-files/namespace.yaml

# Run deployment script again
./image-less-deployment.sh
```

## Getting Additional Help

If you continue to experience issues after trying these solutions, please:

1. Gather logs from all pods:
   ```bash
   kubectl -n l1-monitoring logs <pod-name> > <pod-name>-logs.txt
   ```

2. Get details of all resources:
   ```bash
   kubectl -n l1-monitoring describe all > l1-monitoring-details.txt
   ```

3. Contact support with these log files for further assistance.