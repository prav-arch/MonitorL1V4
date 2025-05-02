"""
Kubernetes Cluster Monitoring Utility.
This module provides functions to monitor and report on Kubernetes cluster health.
"""

import os
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple

from kubernetes import client, config
from kubernetes.client.rest import ApiException

logger = logging.getLogger(__name__)

# Constants for resource usage thresholds
CPU_WARNING_THRESHOLD = 80  # 80% CPU usage
MEMORY_WARNING_THRESHOLD = 80  # 80% memory usage
POD_READY_WARNING_THRESHOLD = 70  # 70% of pods ready


class KubernetesMonitor:
    """Class to monitor Kubernetes cluster health"""
    
    def __init__(self, in_cluster: bool = False, kubeconfig_path: Optional[str] = None, 
                 context_name: Optional[str] = None, mock_mode: bool = False):
        """
        Initialize the Kubernetes monitor
        
        Args:
            in_cluster: Whether to run in-cluster (using service account) or not
            kubeconfig_path: Path to kubeconfig file if not using in-cluster config
            context_name: Kubernetes context name to use
            mock_mode: Whether to run in mock mode with simulated data
        """
        self.mock_mode = mock_mode
        
        if self.mock_mode:
            logger.info("Initializing Kubernetes monitor in mock mode")
            return
        
        try:
            if in_cluster:
                logger.info("Loading in-cluster Kubernetes configuration")
                config.load_incluster_config()
            else:
                if kubeconfig_path:
                    logger.info(f"Loading Kubernetes configuration from {kubeconfig_path}")
                    config.load_kube_config(kubeconfig_path, context=context_name)
                else:
                    # Try to load from default location
                    logger.info("Loading Kubernetes configuration from default location")
                    config.load_kube_config(context=context_name)
            
            # Initialize API clients
            self.core_api = client.CoreV1Api()
            self.apps_api = client.AppsV1Api()
            self.batch_api = client.BatchV1Api()
            self.metrics_api = None
            
            # Try to initialize metrics API if available
            try:
                self.metrics_api = client.CustomObjectsApi()
            except Exception as e:
                logger.warning(f"Failed to initialize metrics API: {e}")
                logger.warning("Resource usage data will not be available")
                
            logger.info("Kubernetes monitor initialized successfully")
        except Exception as e:
            logger.info(f"Kubernetes client not available: {e}")
            logger.info("Using simulated Kubernetes monitoring - this is expected in development")
            self.mock_mode = True
    
    def get_cluster_overview(self) -> Dict[str, Any]:
        """
        Get an overview of the cluster health
        
        Returns:
            Dictionary with cluster health metrics
        """
        if self.mock_mode:
            return self._get_mock_cluster_overview()
        
        try:
            # Get nodes
            nodes = self.core_api.list_node().items
            
            # Get overall pod status
            pods = self.core_api.list_pod_for_all_namespaces().items
            
            # Get deployments
            deployments = self.apps_api.list_deployment_for_all_namespaces().items
            
            # Get services
            services = self.core_api.list_service_for_all_namespaces().items
            
            # Process node data
            node_data = self._process_node_data(nodes)
            
            # Process pod data
            pod_data = self._process_pod_data(pods)
            
            # Process deployment data
            deployment_data = self._process_deployment_data(deployments)
            
            # Get recent events
            events = self._get_recent_events()
            
            # Check component health for control plane
            control_plane_health = self._check_control_plane_health()
            
            return {
                "timestamp": datetime.utcnow().isoformat(),
                "nodes": node_data,
                "pods": pod_data,
                "deployments": deployment_data,
                "services": {
                    "total_count": len(services),
                    "service_types": self._count_service_types(services)
                },
                "events": events,
                "control_plane": control_plane_health,
                "overall_health": self._calculate_overall_health(node_data, pod_data, deployment_data, control_plane_health),
            }
        except ApiException as e:
            logger.error(f"Kubernetes API error: {e}")
            return {
                "error": f"Kubernetes API error: {e.reason}",
                "timestamp": datetime.utcnow().isoformat(),
                "status": "error"
            }
        except Exception as e:
            logger.error(f"Error getting cluster overview: {e}")
            return {
                "error": f"Error getting cluster overview: {str(e)}",
                "timestamp": datetime.utcnow().isoformat(),
                "status": "error"
            }
    
    def get_node_metrics(self, node_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Get metrics for one or all nodes
        
        Args:
            node_name: Name of the node to get metrics for, or None for all nodes
            
        Returns:
            Dictionary with node metrics
        """
        if self.mock_mode:
            return self._get_mock_node_metrics(node_name)
        
        try:
            nodes = self.core_api.list_node().items
            
            if node_name:
                nodes = [n for n in nodes if n.metadata.name == node_name]
                if not nodes:
                    return {"error": f"Node {node_name} not found"}
            
            result = []
            
            for node in nodes:
                node_info = {
                    "name": node.metadata.name,
                    "status": self._get_node_status(node),
                    "capacity": {
                        "cpu": node.status.capacity.get("cpu"),
                        "memory": node.status.capacity.get("memory"),
                        "pods": node.status.capacity.get("pods")
                    },
                    "allocatable": {
                        "cpu": node.status.allocatable.get("cpu"),
                        "memory": node.status.allocatable.get("memory"),
                        "pods": node.status.allocatable.get("pods")
                    },
                    "conditions": self._extract_conditions(node.status.conditions),
                    "labels": node.metadata.labels
                }
                
                # Try to get usage metrics if metrics API is available
                if self.metrics_api:
                    try:
                        metrics = self.metrics_api.list_cluster_custom_object(
                            "metrics.k8s.io", "v1beta1", "nodes")
                        for item in metrics.get("items", []):
                            if item.get("metadata", {}).get("name") == node.metadata.name:
                                node_info["usage"] = {
                                    "cpu": item.get("usage", {}).get("cpu"),
                                    "memory": item.get("usage", {}).get("memory")
                                }
                                break
                    except Exception as e:
                        logger.warning(f"Failed to get node metrics: {e}")
                
                result.append(node_info)
            
            return {
                "timestamp": datetime.utcnow().isoformat(),
                "nodes": result,
                "count": len(result)
            }
        except ApiException as e:
            logger.error(f"Kubernetes API error: {e}")
            return {
                "error": f"Kubernetes API error: {e.reason}",
                "timestamp": datetime.utcnow().isoformat(),
                "status": "error"
            }
        except Exception as e:
            logger.error(f"Error getting node metrics: {e}")
            return {
                "error": f"Error getting node metrics: {str(e)}",
                "timestamp": datetime.utcnow().isoformat(),
                "status": "error"
            }
    
    def get_pod_metrics(self, namespace: Optional[str] = None, 
                      label_selector: Optional[str] = None) -> Dict[str, Any]:
        """
        Get metrics for pods
        
        Args:
            namespace: Namespace to get pods from, or None for all namespaces
            label_selector: Label selector to filter pods
            
        Returns:
            Dictionary with pod metrics
        """
        if self.mock_mode:
            return self._get_mock_pod_metrics(namespace, label_selector)
        
        try:
            if namespace:
                pods = self.core_api.list_namespaced_pod(namespace, label_selector=label_selector).items
            else:
                pods = self.core_api.list_pod_for_all_namespaces(label_selector=label_selector).items
            
            result = []
            
            for pod in pods:
                pod_info = {
                    "name": pod.metadata.name,
                    "namespace": pod.metadata.namespace,
                    "node": pod.spec.node_name,
                    "status": pod.status.phase,
                    "start_time": pod.status.start_time.isoformat() if pod.status.start_time else None,
                    "containers": [
                        {
                            "name": c.name,
                            "ready": c.ready,
                            "restart_count": c.restart_count,
                            "image": c.image
                        }
                        for c in pod.status.container_statuses if pod.status.container_statuses
                    ],
                    "conditions": self._extract_conditions(pod.status.conditions)
                }
                
                # Try to get usage metrics if metrics API is available
                if self.metrics_api:
                    try:
                        metrics = None
                        if namespace:
                            metrics = self.metrics_api.list_namespaced_custom_object(
                                "metrics.k8s.io", "v1beta1", namespace, "pods")
                        else:
                            metrics = self.metrics_api.list_cluster_custom_object(
                                "metrics.k8s.io", "v1beta1", "pods")
                                
                        for item in metrics.get("items", []):
                            if (item.get("metadata", {}).get("name") == pod.metadata.name and 
                                item.get("metadata", {}).get("namespace") == pod.metadata.namespace):
                                
                                containers = {}
                                for c in item.get("containers", []):
                                    containers[c.get("name")] = {
                                        "cpu": c.get("usage", {}).get("cpu"),
                                        "memory": c.get("usage", {}).get("memory")
                                    }
                                
                                pod_info["usage"] = {
                                    "containers": containers
                                }
                                break
                    except Exception as e:
                        logger.warning(f"Failed to get pod metrics: {e}")
                
                result.append(pod_info)
            
            return {
                "timestamp": datetime.utcnow().isoformat(),
                "pods": result,
                "count": len(result)
            }
        except ApiException as e:
            logger.error(f"Kubernetes API error: {e}")
            return {
                "error": f"Kubernetes API error: {e.reason}",
                "timestamp": datetime.utcnow().isoformat(),
                "status": "error"
            }
        except Exception as e:
            logger.error(f"Error getting pod metrics: {e}")
            return {
                "error": f"Error getting pod metrics: {str(e)}",
                "timestamp": datetime.utcnow().isoformat(),
                "status": "error"
            }
    
    def get_namespace_health(self, namespace: Optional[str] = None) -> Dict[str, Any]:
        """
        Get health metrics for one or all namespaces
        
        Args:
            namespace: Specific namespace to get health for, or None for all namespaces
            
        Returns:
            Dictionary with namespace health metrics
        """
        if self.mock_mode:
            return self._get_mock_namespace_health(namespace)
        
        try:
            if namespace:
                namespaces = [self.core_api.read_namespace(namespace)]
            else:
                namespaces = self.core_api.list_namespace().items
            
            result = []
            
            for ns in namespaces:
                ns_name = ns.metadata.name
                
                # Get pods for this namespace
                pods = self.core_api.list_namespaced_pod(ns_name).items
                
                # Get deployments for this namespace
                deployments = self.apps_api.list_namespaced_deployment(ns_name).items
                
                # Get services for this namespace
                services = self.core_api.list_namespaced_service(ns_name).items
                
                # Process pod data for this namespace
                pod_data = self._process_pod_data(pods)
                
                # Process deployment data for this namespace
                deployment_data = self._process_deployment_data(deployments)
                
                # Get recent events for this namespace
                events = self._get_recent_events(ns_name)
                
                # Calculate namespace health
                health_score, health_status = self._calculate_namespace_health(
                    ns_name, pod_data, deployment_data, events
                )
                
                ns_info = {
                    "name": ns_name,
                    "status": ns.status.phase,
                    "pods": pod_data,
                    "deployments": deployment_data,
                    "services": {
                        "total_count": len(services),
                        "service_types": self._count_service_types(services)
                    },
                    "events": events,
                    "health": {
                        "score": health_score,
                        "status": health_status
                    }
                }
                
                result.append(ns_info)
            
            return {
                "timestamp": datetime.utcnow().isoformat(),
                "namespaces": result,
                "count": len(result)
            }
        except ApiException as e:
            logger.error(f"Kubernetes API error: {e}")
            return {
                "error": f"Kubernetes API error: {e.reason}",
                "timestamp": datetime.utcnow().isoformat(),
                "status": "error"
            }
        except Exception as e:
            logger.error(f"Error getting namespace health: {e}")
            return {
                "error": f"Error getting namespace health: {str(e)}",
                "timestamp": datetime.utcnow().isoformat(),
                "status": "error"
            }
    
    def get_l1monitoring_health(self) -> Dict[str, Any]:
        """
        Get health metrics specifically for L1 Monitoring components
        
        Returns:
            Dictionary with L1 Monitoring health metrics
        """
        if self.mock_mode:
            return self._get_mock_l1monitoring_health()
        
        try:
            # Get pods with app=l1-monitoring label
            pods = self.core_api.list_pod_for_all_namespaces(
                label_selector="app=l1-monitoring").items
            
            # Get deployments with app=l1-monitoring label
            deployments = self.apps_api.list_deployment_for_all_namespaces(
                label_selector="app=l1-monitoring").items
            
            # Get pods for related services: clickhouse, postgres, ollama
            clickhouse_pods = self.core_api.list_pod_for_all_namespaces(
                label_selector="app=clickhouse").items
            
            postgres_pods = self.core_api.list_pod_for_all_namespaces(
                label_selector="app=postgres").items
            
            ollama_pods = self.core_api.list_pod_for_all_namespaces(
                label_selector="app=ollama").items
            
            # Process pod data
            app_pod_data = self._process_pod_data(pods)
            clickhouse_pod_data = self._process_pod_data(clickhouse_pods)
            postgres_pod_data = self._process_pod_data(postgres_pods)
            ollama_pod_data = self._process_pod_data(ollama_pods)
            
            # Process deployment data
            deployment_data = self._process_deployment_data(deployments)
            
            # Check connectivity between components
            component_connectivity = self._check_component_connectivity()
            
            # Calculate overall L1 Monitoring health
            health_score, health_status = self._calculate_l1monitoring_health(
                app_pod_data, clickhouse_pod_data, postgres_pod_data, 
                ollama_pod_data, deployment_data, component_connectivity
            )
            
            return {
                "timestamp": datetime.utcnow().isoformat(),
                "components": {
                    "application": {
                        "pods": app_pod_data,
                        "deployments": deployment_data
                    },
                    "clickhouse": {
                        "pods": clickhouse_pod_data
                    },
                    "postgres": {
                        "pods": postgres_pod_data
                    },
                    "ollama": {
                        "pods": ollama_pod_data
                    }
                },
                "connectivity": component_connectivity,
                "health": {
                    "score": health_score,
                    "status": health_status
                }
            }
        except ApiException as e:
            logger.error(f"Kubernetes API error: {e}")
            return {
                "error": f"Kubernetes API error: {e.reason}",
                "timestamp": datetime.utcnow().isoformat(),
                "status": "error"
            }
        except Exception as e:
            logger.error(f"Error getting L1 Monitoring health: {e}")
            return {
                "error": f"Error getting L1 Monitoring health: {str(e)}",
                "timestamp": datetime.utcnow().isoformat(),
                "status": "error"
            }
    
    # Helper methods
    def _get_node_status(self, node) -> str:
        """Get node status based on conditions"""
        for condition in node.status.conditions:
            if condition.type == "Ready":
                return "Ready" if condition.status == "True" else "NotReady"
        return "Unknown"
    
    def _extract_conditions(self, conditions) -> List[Dict[str, Any]]:
        """Extract relevant info from conditions list"""
        if not conditions:
            return []
            
        result = []
        for condition in conditions:
            result.append({
                "type": condition.type,
                "status": condition.status,
                "reason": getattr(condition, "reason", None),
                "message": getattr(condition, "message", None),
                "last_transition_time": condition.last_transition_time.isoformat() 
                    if hasattr(condition, "last_transition_time") and condition.last_transition_time 
                    else None
            })
        return result
    
    def _process_node_data(self, nodes) -> Dict[str, Any]:
        """Process node data to get aggregated statistics"""
        total = len(nodes)
        ready = sum(1 for n in nodes if self._get_node_status(n) == "Ready")
        
        return {
            "total_count": total,
            "ready_count": ready,
            "not_ready_count": total - ready,
            "ready_percentage": (ready / total * 100) if total > 0 else 0,
            "conditions": self._aggregate_conditions([n.status.conditions for n in nodes])
        }
    
    def _process_pod_data(self, pods) -> Dict[str, Any]:
        """Process pod data to get aggregated statistics"""
        total = len(pods)
        running = sum(1 for p in pods if p.status.phase == "Running")
        pending = sum(1 for p in pods if p.status.phase == "Pending")
        failed = sum(1 for p in pods if p.status.phase == "Failed")
        succeeded = sum(1 for p in pods if p.status.phase == "Succeeded")
        unknown = sum(1 for p in pods if p.status.phase == "Unknown")
        
        return {
            "total_count": total,
            "running_count": running,
            "pending_count": pending,
            "failed_count": failed,
            "succeeded_count": succeeded,
            "unknown_count": unknown,
            "running_percentage": (running / total * 100) if total > 0 else 0
        }
    
    def _process_deployment_data(self, deployments) -> Dict[str, Any]:
        """Process deployment data to get aggregated statistics"""
        total = len(deployments)
        available = 0
        unavailable = 0
        
        for d in deployments:
            if not d.status.available_replicas:
                unavailable += 1
            else:
                available += 1
        
        return {
            "total_count": total,
            "available_count": available,
            "unavailable_count": unavailable,
            "available_percentage": (available / total * 100) if total > 0 else 0
        }
    
    def _aggregate_conditions(self, condition_lists) -> Dict[str, int]:
        """Aggregate node conditions"""
        result = {}
        
        for conditions in condition_lists:
            for condition in conditions:
                if condition.type not in result:
                    result[condition.type] = {
                        "True": 0,
                        "False": 0,
                        "Unknown": 0
                    }
                
                status = condition.status
                if status not in ["True", "False", "Unknown"]:
                    status = "Unknown"
                    
                result[condition.type][status] += 1
        
        return result
    
    def _count_service_types(self, services) -> Dict[str, int]:
        """Count services by type"""
        result = {}
        
        for svc in services:
            svc_type = svc.spec.type
            if svc_type not in result:
                result[svc_type] = 0
            result[svc_type] += 1
        
        return result
    
    def _get_recent_events(self, namespace: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get recent events, optionally filtered by namespace"""
        # Return mock events when in mock mode
        if self.mock_mode:
            # Create timestamps for mock events
            now = datetime.utcnow()
            
            # Generate mock events data with realistic Kubernetes event information
            mock_events = [
                {
                    "type": "Normal",
                    "reason": "Started",
                    "message": "Started container l1-monitoring-app",
                    "count": 1,
                    "first_timestamp": (now - timedelta(minutes=15)).isoformat(),
                    "last_timestamp": (now - timedelta(minutes=15)).isoformat(),
                    "involved_object": {
                        "kind": "Pod",
                        "name": "l1-monitoring-app",
                        "namespace": "default"
                    }
                },
                {
                    "type": "Normal",
                    "reason": "Created",
                    "message": "Created container postgres-database",
                    "count": 1,
                    "first_timestamp": (now - timedelta(minutes=25)).isoformat(),
                    "last_timestamp": (now - timedelta(minutes=25)).isoformat(),
                    "involved_object": {
                        "kind": "Pod",
                        "name": "postgres-database",
                        "namespace": "default"
                    }
                },
                {
                    "type": "Warning",
                    "reason": "BackOff",
                    "message": "Back-off restarting failed container",
                    "count": 3,
                    "first_timestamp": (now - timedelta(minutes=35)).isoformat(),
                    "last_timestamp": (now - timedelta(minutes=30)).isoformat(),
                    "involved_object": {
                        "kind": "Pod",
                        "name": "failing-job",
                        "namespace": "default"
                    }
                },
                {
                    "type": "Normal",
                    "reason": "ScalingReplicaSet",
                    "message": "Scaled up replica set l1-monitoring-app to 1",
                    "count": 1,
                    "first_timestamp": (now - timedelta(minutes=40)).isoformat(),
                    "last_timestamp": (now - timedelta(minutes=40)).isoformat(),
                    "involved_object": {
                        "kind": "Deployment",
                        "name": "l1-monitoring-app",
                        "namespace": "default"
                    }
                },
                {
                    "type": "Normal",
                    "reason": "Pulled",
                    "message": "Successfully pulled image 'ollama-model-server:latest'",
                    "count": 1,
                    "first_timestamp": (now - timedelta(minutes=45)).isoformat(),
                    "last_timestamp": (now - timedelta(minutes=45)).isoformat(),
                    "involved_object": {
                        "kind": "Pod",
                        "name": "ollama-model-server",
                        "namespace": "default"
                    }
                }
            ]
            
            # Filter by namespace if specified
            if namespace:
                return [event for event in mock_events if event["involved_object"]["namespace"] == namespace]
            return mock_events
            
        # Real Kubernetes API implementation
        try:
            cutoff_time = datetime.utcnow() - timedelta(hours=1)
            
            if namespace:
                events = self.core_api.list_namespaced_event(namespace).items
            else:
                events = self.core_api.list_event_for_all_namespaces().items
            
            # Filter recent events and sort by timestamp
            recent_events = []
            for event in events:
                # Use last_timestamp if available, otherwise creation_timestamp
                event_time = event.last_timestamp or event.metadata.creation_timestamp
                
                if event_time >= cutoff_time:
                    recent_events.append({
                        "type": event.type,
                        "reason": event.reason,
                        "message": event.message,
                        "count": event.count,
                        "first_timestamp": event.first_timestamp.isoformat() if event.first_timestamp else None,
                        "last_timestamp": event.last_timestamp.isoformat() if event.last_timestamp else None,
                        "involved_object": {
                            "kind": event.involved_object.kind,
                            "name": event.involved_object.name,
                            "namespace": event.involved_object.namespace
                        }
                    })
            
            # Sort by timestamp (most recent first)
            recent_events.sort(
                key=lambda x: x["last_timestamp"] or x["first_timestamp"] or "",
                reverse=True
            )
            
            return recent_events[:20]  # Return top 20 most recent events
        except Exception as e:
            logger.error(f"Error getting recent events: {e}")
            return []
    
    def _check_control_plane_health(self) -> Dict[str, Any]:
        """Check Kubernetes control plane component health"""
        try:
            # Get control plane components
            component_statuses = self.core_api.list_component_status().items
            
            components = {}
            for cs in component_statuses:
                components[cs.metadata.name] = {
                    "status": "Healthy" if all(c.status == "True" for c in cs.conditions) else "Unhealthy",
                    "conditions": self._extract_conditions(cs.conditions)
                }
            
            # If we couldn't get component statuses, try to check API server health
            if not components:
                # Just do a generic API call to check if the API server is responding
                self.core_api.list_namespace(limit=1)
                components["apiserver"] = {
                    "status": "Healthy",
                    "conditions": [{"type": "Healthy", "status": "True"}]
                }
            
            return {
                "components": components,
                "healthy": all(c["status"] == "Healthy" for c in components.values()),
            }
        except Exception as e:
            logger.error(f"Error checking control plane health: {e}")
            return {
                "components": {"apiserver": {"status": "Unhealthy", "error": str(e)}},
                "healthy": False,
            }
    
    def _check_component_connectivity(self) -> Dict[str, Any]:
        """Check connectivity between L1 Monitoring components"""
        # In a real implementation, this would make requests between components
        # to verify they can talk to each other. For now, we just assume connectivity
        # based on pod status.
        try:
            app_pods = self.core_api.list_pod_for_all_namespaces(
                label_selector="app=l1-monitoring").items
                
            clickhouse_pods = self.core_api.list_pod_for_all_namespaces(
                label_selector="app=clickhouse").items
                
            postgres_pods = self.core_api.list_pod_for_all_namespaces(
                label_selector="app=postgres").items
                
            ollama_pods = self.core_api.list_pod_for_all_namespaces(
                label_selector="app=ollama").items
            
            app_ready = any(
                pod.status.phase == "Running" and 
                all(c.ready for c in pod.status.container_statuses if pod.status.container_statuses)
                for pod in app_pods
            )
            
            clickhouse_ready = any(
                pod.status.phase == "Running" and 
                all(c.ready for c in pod.status.container_statuses if pod.status.container_statuses)
                for pod in clickhouse_pods
            )
            
            postgres_ready = any(
                pod.status.phase == "Running" and 
                all(c.ready for c in pod.status.container_statuses if pod.status.container_statuses)
                for pod in postgres_pods
            )
            
            ollama_ready = any(
                pod.status.phase == "Running" and 
                all(c.ready for c in pod.status.container_statuses if pod.status.container_statuses)
                for pod in ollama_pods
            )
            
            return {
                "app_to_clickhouse": "Healthy" if app_ready and clickhouse_ready else "Unhealthy",
                "app_to_postgres": "Healthy" if app_ready and postgres_ready else "Unhealthy",
                "app_to_ollama": "Healthy" if app_ready and ollama_ready else "Unhealthy",
                "overall": "Healthy" if (
                    app_ready and (clickhouse_ready or postgres_ready) and ollama_ready
                ) else "Degraded"
            }
        except Exception as e:
            logger.error(f"Error checking component connectivity: {e}")
            return {
                "app_to_clickhouse": "Unknown",
                "app_to_postgres": "Unknown",
                "app_to_ollama": "Unknown",
                "overall": "Unknown",
                "error": str(e)
            }
    
    def _calculate_overall_health(self, node_data, pod_data, deployment_data, 
                                 control_plane_health) -> Tuple[int, str]:
        """Calculate overall cluster health score and status"""
        score = 100  # Start with perfect score
        
        # Node health (40% of score)
        node_ready_pct = node_data["ready_percentage"]
        if node_ready_pct < 50:
            score -= 35
        elif node_ready_pct < 80:
            score -= 20
        elif node_ready_pct < 100:
            score -= 5
        
        # Pod health (30% of score)
        pod_running_pct = pod_data["running_percentage"]
        if pod_running_pct < 50:
            score -= 25
        elif pod_running_pct < 80:
            score -= 15
        elif pod_running_pct < 95:
            score -= 5
        
        # Deployment health (15% of score)
        deployment_available_pct = deployment_data["available_percentage"]
        if deployment_available_pct < 50:
            score -= 13
        elif deployment_available_pct < 80:
            score -= 8
        elif deployment_available_pct < 100:
            score -= 3
        
        # Control plane health (15% of score)
        if not control_plane_health["healthy"]:
            score -= 15
        
        # Determine status based on score
        if score >= 90:
            status = "Healthy"
        elif score >= 70:
            status = "Degraded"
        elif score >= 40:
            status = "Unhealthy"
        else:
            status = "Critical"
        
        return (max(0, score), status)
    
    def _calculate_namespace_health(self, namespace, pod_data, deployment_data, 
                                   events) -> Tuple[int, str]:
        """Calculate namespace health score and status"""
        score = 100  # Start with perfect score
        
        # Pod health (50% of score)
        pod_running_pct = pod_data["running_percentage"]
        if pod_running_pct < 50:
            score -= 40
        elif pod_running_pct < 80:
            score -= 25
        elif pod_running_pct < 95:
            score -= 10
        
        # Deployment health (30% of score)
        deployment_available_pct = deployment_data["available_percentage"]
        if deployment_available_pct < 50:
            score -= 25
        elif deployment_available_pct < 80:
            score -= 15
        elif deployment_available_pct < 100:
            score -= 5
        
        # Recent events (20% of score)
        warning_events = sum(1 for e in events if e["type"] == "Warning")
        if warning_events > 10:
            score -= 20
        elif warning_events > 5:
            score -= 10
        elif warning_events > 0:
            score -= 5
        
        # Determine status based on score
        if score >= 90:
            status = "Healthy"
        elif score >= 70:
            status = "Degraded"
        elif score >= 40:
            status = "Unhealthy"
        else:
            status = "Critical"
        
        return (max(0, score), status)
    
    def _calculate_l1monitoring_health(self, app_pod_data, clickhouse_pod_data, 
                                     postgres_pod_data, ollama_pod_data, 
                                     deployment_data, connectivity) -> Tuple[int, str]:
        """Calculate L1 Monitoring health score and status"""
        score = 100  # Start with perfect score
        
        # App pod health (25% of score)
        app_running_pct = app_pod_data["running_percentage"]
        if app_running_pct < 50:
            score -= 20
        elif app_running_pct < 80:
            score -= 15
        elif app_running_pct < 95:
            score -= 5
        
        # Database health (25% of score)
        clickhouse_running_pct = clickhouse_pod_data["running_percentage"]
        postgres_running_pct = postgres_pod_data["running_percentage"]
        # If either database is healthy, we're good (fallback works)
        if clickhouse_running_pct < 80 and postgres_running_pct < 80:
            score -= 20
        elif clickhouse_running_pct < 80 or postgres_running_pct < 80:
            score -= 5  # One DB is still healthy
        
        # Ollama health (25% of score)
        ollama_running_pct = ollama_pod_data["running_percentage"]
        if ollama_running_pct < 50:
            score -= 20
        elif ollama_running_pct < 80:
            score -= 15
        elif ollama_running_pct < 95:
            score -= 5
        
        # Connectivity (25% of score)
        if connectivity["overall"] != "Healthy":
            score -= 20
        
        # Determine status based on score
        if score >= 90:
            status = "Healthy"
        elif score >= 70:
            status = "Degraded"
        elif score >= 40:
            status = "Unhealthy"
        else:
            status = "Critical"
        
        return (max(0, score), status)
    
    # Mock data methods
    def _get_mock_cluster_overview(self) -> Dict[str, Any]:
        """Generate mock cluster overview data"""
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "nodes": {
                "total_count": 3,
                "ready_count": 3,
                "not_ready_count": 0,
                "ready_percentage": 100.0,
                "conditions": {
                    "Ready": {
                        "True": 3,
                        "False": 0,
                        "Unknown": 0
                    },
                    "DiskPressure": {
                        "True": 0,
                        "False": 3,
                        "Unknown": 0
                    },
                    "MemoryPressure": {
                        "True": 0,
                        "False": 3,
                        "Unknown": 0
                    },
                    "NetworkUnavailable": {
                        "True": 0,
                        "False": 3,
                        "Unknown": 0
                    }
                }
            },
            "pods": {
                "total_count": 15,
                "running_count": 14,
                "pending_count": 1,
                "failed_count": 0,
                "succeeded_count": 0,
                "unknown_count": 0,
                "running_percentage": 93.33
            },
            "deployments": {
                "total_count": 5,
                "available_count": 5,
                "unavailable_count": 0,
                "available_percentage": 100.0
            },
            "services": {
                "total_count": 8,
                "service_types": {
                    "ClusterIP": 6,
                    "LoadBalancer": 2
                }
            },
            "events": [
                {
                    "type": "Normal",
                    "reason": "Started",
                    "message": "Started container l1-monitoring-app",
                    "count": 1,
                    "first_timestamp": (datetime.utcnow() - timedelta(minutes=30)).isoformat(),
                    "last_timestamp": (datetime.utcnow() - timedelta(minutes=30)).isoformat(),
                    "involved_object": {
                        "kind": "Pod",
                        "name": "l1-monitoring-5d4f8b9d6c-2xlpn",
                        "namespace": "default"
                    }
                },
                {
                    "type": "Normal",
                    "reason": "Pulled",
                    "message": "Container image pulled",
                    "count": 1,
                    "first_timestamp": (datetime.utcnow() - timedelta(minutes=31)).isoformat(),
                    "last_timestamp": (datetime.utcnow() - timedelta(minutes=31)).isoformat(),
                    "involved_object": {
                        "kind": "Pod",
                        "name": "l1-monitoring-5d4f8b9d6c-2xlpn",
                        "namespace": "default"
                    }
                },
                {
                    "type": "Warning",
                    "reason": "Unhealthy",
                    "message": "Readiness probe failed: Get \"http://10.1.0.12:5000/api/health\": dial tcp 10.1.0.12:5000: connect: connection refused",
                    "count": 3,
                    "first_timestamp": (datetime.utcnow() - timedelta(minutes=35)).isoformat(),
                    "last_timestamp": (datetime.utcnow() - timedelta(minutes=32)).isoformat(),
                    "involved_object": {
                        "kind": "Pod",
                        "name": "l1-monitoring-5d4f8b9d6c-2xlpn",
                        "namespace": "default"
                    }
                }
            ],
            "control_plane": {
                "components": {
                    "scheduler": {
                        "status": "Healthy",
                        "conditions": [
                            {
                                "type": "Healthy",
                                "status": "True",
                                "reason": None,
                                "message": "ok",
                                "last_transition_time": None
                            }
                        ]
                    },
                    "controller-manager": {
                        "status": "Healthy",
                        "conditions": [
                            {
                                "type": "Healthy",
                                "status": "True",
                                "reason": None,
                                "message": "ok",
                                "last_transition_time": None
                            }
                        ]
                    },
                    "etcd-0": {
                        "status": "Healthy",
                        "conditions": [
                            {
                                "type": "Healthy",
                                "status": "True",
                                "reason": None,
                                "message": "ok",
                                "last_transition_time": None
                            }
                        ]
                    }
                },
                "healthy": True
            },
            "overall_health": {
                "score": 95,
                "status": "Healthy"
            }
        }
    
    def _get_mock_node_metrics(self, node_name: Optional[str] = None) -> Dict[str, Any]:
        """Generate mock node metrics data"""
        mock_nodes = [
            {
                "name": "k8s-node-1",
                "status": "Ready",
                "capacity": {
                    "cpu": "4",
                    "memory": "16Gi",
                    "pods": "110"
                },
                "allocatable": {
                    "cpu": "3800m",
                    "memory": "15Gi",
                    "pods": "110"
                },
                "conditions": [
                    {
                        "type": "Ready",
                        "status": "True",
                        "reason": "KubeletReady",
                        "message": "kubelet is posting ready status",
                        "last_transition_time": (datetime.utcnow() - timedelta(days=7)).isoformat()
                    }
                ],
                "usage": {
                    "cpu": "1200m",
                    "memory": "7.5Gi"
                }
            },
            {
                "name": "k8s-node-2",
                "status": "Ready",
                "capacity": {
                    "cpu": "8",
                    "memory": "32Gi",
                    "pods": "110"
                },
                "allocatable": {
                    "cpu": "7600m",
                    "memory": "30Gi",
                    "pods": "110"
                },
                "conditions": [
                    {
                        "type": "Ready",
                        "status": "True",
                        "reason": "KubeletReady",
                        "message": "kubelet is posting ready status",
                        "last_transition_time": (datetime.utcnow() - timedelta(days=5)).isoformat()
                    }
                ],
                "usage": {
                    "cpu": "3200m",
                    "memory": "15Gi"
                }
            },
            {
                "name": "k8s-node-3",
                "status": "Ready",
                "capacity": {
                    "cpu": "4",
                    "memory": "16Gi",
                    "pods": "110"
                },
                "allocatable": {
                    "cpu": "3800m",
                    "memory": "15Gi",
                    "pods": "110"
                },
                "conditions": [
                    {
                        "type": "Ready",
                        "status": "True",
                        "reason": "KubeletReady",
                        "message": "kubelet is posting ready status",
                        "last_transition_time": (datetime.utcnow() - timedelta(days=3)).isoformat()
                    }
                ],
                "usage": {
                    "cpu": "900m",
                    "memory": "6Gi"
                }
            }
        ]
        
        if node_name:
            nodes = [n for n in mock_nodes if n["name"] == node_name]
            if not nodes:
                return {
                    "error": f"Node {node_name} not found",
                    "timestamp": datetime.utcnow().isoformat(),
                    "status": "error"
                }
        else:
            nodes = mock_nodes
        
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "nodes": nodes,
            "count": len(nodes)
        }
    
    def _get_mock_pod_metrics(self, namespace: Optional[str] = None, 
                            label_selector: Optional[str] = None) -> Dict[str, Any]:
        """Generate mock pod metrics data"""
        mock_pods = [
            {
                "name": "l1-monitoring-5d4f8b9d6c-2xlpn",
                "namespace": "default",
                "node": "k8s-node-1",
                "status": "Running",
                "start_time": (datetime.utcnow() - timedelta(hours=2)).isoformat(),
                "containers": [
                    {
                        "name": "l1-monitoring-app",
                        "ready": True,
                        "restart_count": 1,
                        "image": "l1-monitoring:latest"
                    }
                ],
                "conditions": [
                    {
                        "type": "Ready",
                        "status": "True",
                        "reason": None,
                        "message": None,
                        "last_transition_time": (datetime.utcnow() - timedelta(hours=1, minutes=58)).isoformat()
                    }
                ],
                "usage": {
                    "containers": {
                        "l1-monitoring-app": {
                            "cpu": "150m",
                            "memory": "256Mi"
                        }
                    }
                }
            },
            {
                "name": "clickhouse-6f8d9b4c5-7jklm",
                "namespace": "default",
                "node": "k8s-node-2",
                "status": "Running",
                "start_time": (datetime.utcnow() - timedelta(hours=3)).isoformat(),
                "containers": [
                    {
                        "name": "clickhouse",
                        "ready": True,
                        "restart_count": 0,
                        "image": "clickhouse/clickhouse-server:latest"
                    }
                ],
                "conditions": [
                    {
                        "type": "Ready",
                        "status": "True",
                        "reason": None,
                        "message": None,
                        "last_transition_time": (datetime.utcnow() - timedelta(hours=2, minutes=58)).isoformat()
                    }
                ],
                "usage": {
                    "containers": {
                        "clickhouse": {
                            "cpu": "500m",
                            "memory": "1.2Gi"
                        }
                    }
                }
            },
            {
                "name": "postgres-5f7c8d6b9-8npkm",
                "namespace": "default",
                "node": "k8s-node-3",
                "status": "Running",
                "start_time": (datetime.utcnow() - timedelta(hours=4)).isoformat(),
                "containers": [
                    {
                        "name": "postgres",
                        "ready": True,
                        "restart_count": 0,
                        "image": "postgres:latest"
                    }
                ],
                "conditions": [
                    {
                        "type": "Ready",
                        "status": "True",
                        "reason": None,
                        "message": None,
                        "last_transition_time": (datetime.utcnow() - timedelta(hours=3, minutes=58)).isoformat()
                    }
                ],
                "usage": {
                    "containers": {
                        "postgres": {
                            "cpu": "120m",
                            "memory": "350Mi"
                        }
                    }
                }
            },
            {
                "name": "ollama-6c7d8e5f9-3qpjr",
                "namespace": "default",
                "node": "k8s-node-2",
                "status": "Running",
                "start_time": (datetime.utcnow() - timedelta(hours=2, minutes=30)).isoformat(),
                "containers": [
                    {
                        "name": "ollama",
                        "ready": True,
                        "restart_count": 0,
                        "image": "ollama/ollama:latest"
                    }
                ],
                "conditions": [
                    {
                        "type": "Ready",
                        "status": "True",
                        "reason": None,
                        "message": None,
                        "last_transition_time": (datetime.utcnow() - timedelta(hours=2, minutes=25)).isoformat()
                    }
                ],
                "usage": {
                    "containers": {
                        "ollama": {
                            "cpu": "800m",
                            "memory": "1.8Gi"
                        }
                    }
                }
            },
            {
                "name": "l1-monitoring-5d4f8b9d6c-5mnkl",
                "namespace": "default",
                "node": "k8s-node-1",
                "status": "Pending",
                "start_time": (datetime.utcnow() - timedelta(minutes=5)).isoformat(),
                "containers": [
                    {
                        "name": "l1-monitoring-app",
                        "ready": False,
                        "restart_count": 0,
                        "image": "l1-monitoring:latest"
                    }
                ],
                "conditions": [
                    {
                        "type": "Ready",
                        "status": "False",
                        "reason": "ContainersNotReady",
                        "message": "containers with unready status: [l1-monitoring-app]",
                        "last_transition_time": (datetime.utcnow() - timedelta(minutes=5)).isoformat()
                    }
                ]
            }
        ]
        
        # Filter by namespace if provided
        if namespace:
            pods = [p for p in mock_pods if p["namespace"] == namespace]
        else:
            pods = mock_pods
        
        # Filter by label selector if provided (simplified)
        if label_selector:
            if label_selector == "app=l1-monitoring":
                pods = [p for p in pods if "l1-monitoring" in p["name"]]
            elif label_selector == "app=clickhouse":
                pods = [p for p in pods if "clickhouse" in p["name"]]
            elif label_selector == "app=postgres":
                pods = [p for p in pods if "postgres" in p["name"]]
            elif label_selector == "app=ollama":
                pods = [p for p in pods if "ollama" in p["name"]]
        
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "pods": pods,
            "count": len(pods)
        }
    
    def _get_mock_namespace_health(self, namespace: Optional[str] = None) -> Dict[str, Any]:
        """Generate mock namespace health data"""
        mock_namespaces = [
            {
                "name": "default",
                "status": "Active",
                "pods": {
                    "total_count": 9,
                    "running_count": 8,
                    "pending_count": 1,
                    "failed_count": 0,
                    "succeeded_count": 0,
                    "unknown_count": 0,
                    "running_percentage": 88.89
                },
                "deployments": {
                    "total_count": 4,
                    "available_count": 4,
                    "unavailable_count": 0,
                    "available_percentage": 100.0
                },
                "services": {
                    "total_count": 5,
                    "service_types": {
                        "ClusterIP": 3,
                        "LoadBalancer": 2
                    }
                },
                "events": [
                    {
                        "type": "Normal",
                        "reason": "Started",
                        "message": "Started container l1-monitoring-app",
                        "count": 1,
                        "first_timestamp": (datetime.utcnow() - timedelta(minutes=30)).isoformat(),
                        "last_timestamp": (datetime.utcnow() - timedelta(minutes=30)).isoformat(),
                        "involved_object": {
                            "kind": "Pod",
                            "name": "l1-monitoring-5d4f8b9d6c-2xlpn",
                            "namespace": "default"
                        }
                    }
                ],
                "health": {
                    "score": 90,
                    "status": "Healthy"
                }
            },
            {
                "name": "kube-system",
                "status": "Active",
                "pods": {
                    "total_count": 6,
                    "running_count": 6,
                    "pending_count": 0,
                    "failed_count": 0,
                    "succeeded_count": 0,
                    "unknown_count": 0,
                    "running_percentage": 100.0
                },
                "deployments": {
                    "total_count": 1,
                    "available_count": 1,
                    "unavailable_count": 0,
                    "available_percentage": 100.0
                },
                "services": {
                    "total_count": 3,
                    "service_types": {
                        "ClusterIP": 3
                    }
                },
                "events": [],
                "health": {
                    "score": 100,
                    "status": "Healthy"
                }
            }
        ]
        
        if namespace:
            namespaces = [n for n in mock_namespaces if n["name"] == namespace]
            if not namespaces:
                return {
                    "error": f"Namespace {namespace} not found",
                    "timestamp": datetime.utcnow().isoformat(),
                    "status": "error"
                }
        else:
            namespaces = mock_namespaces
        
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "namespaces": namespaces,
            "count": len(namespaces)
        }
    
    def _get_mock_l1monitoring_health(self) -> Dict[str, Any]:
        """Generate mock L1 Monitoring health data"""
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "components": {
                "application": {
                    "pods": {
                        "total_count": 2,
                        "running_count": 1,
                        "pending_count": 1,
                        "failed_count": 0,
                        "succeeded_count": 0,
                        "unknown_count": 0,
                        "running_percentage": 50.0
                    },
                    "deployments": {
                        "total_count": 1,
                        "available_count": 1,
                        "unavailable_count": 0,
                        "available_percentage": 100.0
                    }
                },
                "clickhouse": {
                    "pods": {
                        "total_count": 1,
                        "running_count": 1,
                        "pending_count": 0,
                        "failed_count": 0,
                        "succeeded_count": 0,
                        "unknown_count": 0,
                        "running_percentage": 100.0
                    }
                },
                "postgres": {
                    "pods": {
                        "total_count": 1,
                        "running_count": 1,
                        "pending_count": 0,
                        "failed_count": 0,
                        "succeeded_count": 0,
                        "unknown_count": 0,
                        "running_percentage": 100.0
                    }
                },
                "ollama": {
                    "pods": {
                        "total_count": 1,
                        "running_count": 1,
                        "pending_count": 0,
                        "failed_count": 0,
                        "succeeded_count": 0,
                        "unknown_count": 0,
                        "running_percentage": 100.0
                    }
                }
            },
            "connectivity": {
                "app_to_clickhouse": "Healthy",
                "app_to_postgres": "Healthy",
                "app_to_ollama": "Healthy",
                "overall": "Healthy"
            },
            "health": {
                "score": 85,
                "status": "Degraded"
            }
        }


# Singleton instance for the monitor
_monitor_instance = None

def get_kubernetes_monitor(in_cluster: bool = False, kubeconfig_path: Optional[str] = None, 
                          context_name: Optional[str] = None, mock_mode: bool = False) -> KubernetesMonitor:
    """Get the singleton instance of the Kubernetes monitor"""
    global _monitor_instance
    
    # Force mock mode when running locally
    if not in_cluster and not kubeconfig_path:
        is_local = os.environ.get("REPLIT_ENVIRONMENT") is not None
        mock_mode = mock_mode or is_local
    
    if _monitor_instance is None:
        _monitor_instance = KubernetesMonitor(
            in_cluster=in_cluster,
            kubeconfig_path=kubeconfig_path,
            context_name=context_name,
            mock_mode=mock_mode
        )
    
    return _monitor_instance