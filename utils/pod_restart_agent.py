"""
Kubernetes Pod Restart Agent

This module provides an autonomous agent that monitors Kubernetes pods for errors
and automatically restarts them when error thresholds are exceeded.
"""

import logging
import time
import json
import re
import threading
import os
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class PodRestartAgent:
    """
    Autonomous agent that monitors Kubernetes pods and restarts them
    when error thresholds are exceeded
    """
    
    def __init__(self, 
                 namespace: str = 'default', 
                 error_threshold: int = 10, 
                 cooldown_period: int = 300,
                 check_interval: int = 60,
                 mock_mode: bool = False):
        """
        Initialize the Pod Restart Agent
        
        Args:
            namespace: Kubernetes namespace to monitor
            error_threshold: Number of errors before triggering a restart
            cooldown_period: Seconds to wait between restarts of the same pod
            check_interval: Seconds between monitoring checks
            mock_mode: Whether to run in mock mode (for development/testing)
        """
        self.namespace = namespace
        self.error_threshold = error_threshold
        self.cooldown_period = cooldown_period
        self.check_interval = check_interval
        self.mock_mode = mock_mode
        self.running = False
        self.monitor_thread = None
        
        # State tracking
        self.error_counts = {}  # Track error counts per pod
        self.last_restart = {}  # Track last restart time for each pod
        self.restart_history = []  # Historical record of restarts
        
        # Initialize Kubernetes client if not in mock mode
        self.core_api = None
        if not mock_mode:
            try:
                # Import here to avoid dependency issues
                try:
                    from kubernetes import client, config
                    self.kubernetes_client = client
                    
                    try:
                        # Try in-cluster configuration first (when running in K8s)
                        config.load_incluster_config()
                        logger.info("Using in-cluster Kubernetes configuration")
                    except:
                        # Fall back to kubeconfig file (for local development)
                        logger.warning("In-cluster config failed, falling back to kubeconfig")
                        config.load_kube_config()
                        
                    self.core_api = client.CoreV1Api()
                    logger.info("Kubernetes client initialized successfully")
                except ImportError:
                    logger.warning("Kubernetes package not available, falling back to mock mode")
                    self.mock_mode = True
                    self.kubernetes_client = None
            except Exception as e:
                logger.info(f"Kubernetes client not available: {str(e)}")
                self.mock_mode = True
                self.kubernetes_client = None
                logger.info("Using simulated pod restart agent - this is expected in development environment")
        
        # Initialize AI capabilities
        try:
            from utils.llm_interface import get_llm_interface
            self.llm = get_llm_interface()
            logger.info("AI capabilities initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize AI capabilities: {str(e)}")
            self.llm = None
    
    def record_error(self, 
                    pod_name: str, 
                    error_type: str, 
                    error_message: str, 
                    severity: int = 1) -> bool:
        """
        Record an error for a pod and return True if threshold is exceeded
        
        Args:
            pod_name: Name of the pod with the error
            error_type: Type of error (memory, cpu, api, etc.)
            error_message: Detailed error message
            severity: Error severity (1-10)
            
        Returns:
            bool: True if error threshold is exceeded
        """
        # Initialize pod data if not present
        if pod_name not in self.error_counts:
            self.error_counts[pod_name] = {
                'count': 0, 
                'errors': [], 
                'last_error_time': time.time()
            }
        
        # Add weighted error count based on severity
        self.error_counts[pod_name]['count'] += severity
        
        # Record error details
        error_record = {
            'type': error_type,
            'message': error_message,
            'severity': severity,
            'timestamp': time.time(),
            'recorded_at': datetime.now().isoformat()
        }
        
        self.error_counts[pod_name]['errors'].append(error_record)
        self.error_counts[pod_name]['last_error_time'] = time.time()
        
        # Log the error
        logger.info(f"Error recorded for pod {pod_name}: {error_type} (severity {severity})")
        
        # Check if threshold is exceeded
        if self.error_counts[pod_name]['count'] >= self.error_threshold:
            # Keep the error count but mark that we've reached the threshold
            self.error_counts[pod_name]['threshold_reached'] = True
            return True
        
        return False
    
    def should_restart_pod(self, pod_name: str) -> bool:
        """
        Check if a pod should be restarted based on cooldown period
        
        Args:
            pod_name: Name of the pod to check
            
        Returns:
            bool: True if the pod should be restarted
        """
        current_time = time.time()
        
        # Check if pod was recently restarted
        if pod_name in self.last_restart:
            elapsed = current_time - self.last_restart[pod_name]
            if elapsed < self.cooldown_period:
                logger.info(f"Pod {pod_name} in cooldown period ({elapsed:.1f}s < {self.cooldown_period}s), skipping restart")
                return False
                
        return True
    
    def restart_pod(self, pod_name: str) -> bool:
        """
        Restart a pod and log the action
        
        Args:
            pod_name: Name of the pod to restart
            
        Returns:
            bool: True if restart was successful
        """
        if self.mock_mode:
            logger.info(f"[MOCK MODE] Would restart pod {pod_name} in namespace {self.namespace}")
            self._record_restart(pod_name, "mock_restart", successful=True)
            return True
            
        try:
            # Double check cooldown
            if not self.should_restart_pod(pod_name):
                return False
                
            # Get pod info for logging
            pod = None
            try:
                pod = self.core_api.read_namespaced_pod(pod_name, self.namespace)
            except Exception as e:
                logger.error(f"Failed to get info for pod {pod_name}: {str(e)}")
            
            # Ask AI for recommendation before restarting if available
            ai_recommendation = None
            if self.llm:
                ai_recommendation = self._get_ai_recommendation(pod_name, pod)
                
                if ai_recommendation and not ai_recommendation.get('should_restart', True):
                    logger.info(f"AI recommends against restarting pod {pod_name}: {ai_recommendation.get('reason', 'No reason provided')}")
                    return False
            
            # Delete pod (Kubernetes will recreate it if managed by controller)
            if self.core_api and self.kubernetes_client:
                self.core_api.delete_namespaced_pod(
                    name=pod_name,
                    namespace=self.namespace,
                    body=self.kubernetes_client.V1DeleteOptions()
                )
                
                # Record successful restart
                self._record_restart(pod_name, "api_restart", successful=True, ai_recommendation=ai_recommendation)
                
                logger.info(f"Successfully restarted pod {pod_name} in namespace {self.namespace}")
                return True
            else:
                logger.error(f"Cannot restart pod {pod_name}: Kubernetes client not initialized")
                self._record_restart(pod_name, "api_restart", successful=False, 
                                    error_message="Kubernetes client not initialized")
                return False
            
        except Exception as e:
            logger.error(f"Failed to restart pod {pod_name}: {str(e)}")
            self._record_restart(pod_name, "api_restart", successful=False, error_message=str(e))
            return False
    
    def _record_restart(self, 
                        pod_name: str, 
                        restart_type: str, 
                        successful: bool = True, 
                        error_message: Optional[str] = None,
                        ai_recommendation: Optional[Dict[str, Any]] = None) -> None:
        """
        Record a restart attempt in the history
        
        Args:
            pod_name: Name of the pod
            restart_type: Type of restart (mock, api, manual)
            successful: Whether the restart was successful
            error_message: Error message if restart failed
            ai_recommendation: AI recommendation if available
        """
        # Update restart timestamp
        current_time = time.time()
        self.last_restart[pod_name] = current_time
        
        # Record in history
        restart_record = {
            'pod_name': pod_name,
            'namespace': self.namespace,
            'timestamp': current_time,
            'datetime': datetime.now().isoformat(),
            'restart_type': restart_type,
            'successful': successful,
            'error_count': self.error_counts.get(pod_name, {}).get('count', 0)
        }
        
        if error_message:
            restart_record['error_message'] = error_message
            
        if ai_recommendation:
            restart_record['ai_recommendation'] = ai_recommendation
            
        # Add to history and reset error count
        self.restart_history.append(restart_record)
        
        # Reset error count if successful
        if successful and pod_name in self.error_counts:
            self.error_counts[pod_name]['count'] = 0
            self.error_counts[pod_name]['threshold_reached'] = False
    
    def _get_ai_recommendation(self, 
                              pod_name: str, 
                              pod_obj: Optional[Any] = None) -> Dict[str, Any]:
        """
        Get AI recommendation on whether to restart pod
        
        Args:
            pod_name: Name of the pod
            pod_obj: Kubernetes pod object if available
            
        Returns:
            dict: AI recommendation with decision and reasoning
        """
        if not self.llm:
            # No LLM available, default to simple threshold-based decision
            return {
                'should_restart': True,
                'reason': 'Default restart policy based on error threshold. No AI available.',
                'confidence': 0.8
            }
            
        try:
            # Get recent errors for this pod
            recent_errors = []
            if pod_name in self.error_counts:
                # Get the last 5 errors (most recent first)
                recent_errors = sorted(
                    self.error_counts[pod_name]['errors'][-5:],
                    key=lambda x: x['timestamp'],
                    reverse=True
                )
                
            # Convert errors to a text description
            error_description = "\n".join([
                f"Error {i+1}: {err['type']} (severity {err['severity']}) - {err['message']}"
                for i, err in enumerate(recent_errors)
            ])
            
            # Get pod details if available
            pod_details = "Pod details not available"
            if pod_obj:
                pod_status = pod_obj.status.phase
                pod_conditions = "\n".join([
                    f"Condition: {c.type}, Status: {c.status}" 
                    for c in pod_obj.status.conditions or []
                ])
                
                # Get container statuses
                container_statuses = []
                for container in (pod_obj.status.container_statuses or []):
                    ready = container.ready
                    restarts = container.restart_count
                    state = "unknown"
                    
                    if container.state.running:
                        state = "running"
                    elif container.state.terminated:
                        state = f"terminated ({container.state.terminated.reason})"
                    elif container.state.waiting:
                        state = f"waiting ({container.state.waiting.reason})"
                        
                    container_statuses.append(f"Container {container.name}: {state}, Ready: {ready}, Restarts: {restarts}")
                
                pod_details = f"""
                Pod Name: {pod_name}
                Status: {pod_status}
                Conditions: 
                {pod_conditions}
                
                Container Statuses:
                {chr(10).join(container_statuses)}
                """
            
            # Create prompt for LLM
            prompt = f"""
            As a Kubernetes pod management AI, analyze this information and recommend whether to restart the pod.
            
            {pod_details}
            
            Recent Errors:
            {error_description}
            
            The configured error threshold of {self.error_threshold} has been reached.
            Based on this information, should the pod be restarted? 
            
            Respond in JSON format with the following structure:
            {{
                "should_restart": true/false,
                "reason": "detailed explanation of your recommendation",
                "confidence": 0.0-1.0,
                "alternative_actions": ["other possible actions to take"]
            }}
            """
            
            # Get LLM recommendation
            response = self.llm.generate_text(prompt)
            
            # Parse the recommendation
            import json
            import re
            
            # Find JSON in response
            json_match = re.search(r'({.*})', response, re.DOTALL)
            if json_match:
                try:
                    recommendation = json.loads(json_match.group(1))
                    return recommendation
                except json.JSONDecodeError:
                    logger.error("Failed to decode JSON from LLM response")
                
            # Fallback if parsing fails
            return {
                'should_restart': True,
                'reason': 'Error threshold exceeded. LLM response parsing failed.',
                'confidence': 0.7,
                'alternative_actions': ['Investigate logs', 'Scale deployment']
            }
            
        except Exception as e:
            logger.error(f"Error getting AI recommendation: {str(e)}")
            return {
                'should_restart': True,
                'reason': f'Error threshold exceeded. AI consultation failed: {str(e)}',
                'confidence': 0.6
            }
    
    def _get_pod_metrics(self, pod_name: str) -> Dict[str, Any]:
        """
        Get metrics for a pod using the Kubernetes Metrics API
        
        Args:
            pod_name: Name of the pod
            
        Returns:
            dict: Pod metrics or empty dict if metrics not available
        """
        if self.mock_mode or not self.core_api:
            return {}
            
        try:
            # This requires the metrics-server to be installed in the cluster
            from kubernetes.client.api_client import ApiClient
            from kubernetes import client
            
            api_client = ApiClient()
            response = api_client.call_api(
                f'/apis/metrics.k8s.io/v1beta1/namespaces/{self.namespace}/pods/{pod_name}',
                'GET',
                auth_settings=['BearerToken'],
                response_type='object'
            )
            
            if response and response[0]:
                return response[0]
                
        except Exception as e:
            logger.warning(f"Failed to get metrics for pod {pod_name}: {str(e)}")
            
        return {}
    
    def _check_pod_health(self, pod: Any) -> Dict[str, Any]:
        """
        Check the health of a pod and report any issues
        
        Args:
            pod: Kubernetes pod object
            
        Returns:
            dict: Health check results
        """
        pod_name = pod.metadata.name
        issues = []
        error_severity = 0
        is_unhealthy = False
        
        # Check for container restarts
        restart_count = 0
        for container_status in pod.status.container_statuses or []:
            restart_count += container_status.restart_count
            
            # Check for waiting containers
            if container_status.state.waiting:
                reason = container_status.state.waiting.reason
                message = container_status.state.waiting.message
                
                if reason in ['CrashLoopBackOff', 'Error', 'ErrImagePull', 'ImagePullBackOff', 'CreateContainerError']:
                    is_unhealthy = True
                    severity = 5  # Higher severity for critical container issues
                    issues.append({
                        'type': f"container_waiting_{reason}",
                        'message': f"Container {container_status.name} is waiting: {reason}. {message}",
                        'severity': severity
                    })
                    error_severity = max(error_severity, severity)
            
            # Check for terminated containers
            elif container_status.state.terminated:
                reason = container_status.state.terminated.reason
                exit_code = container_status.state.terminated.exit_code
                
                if exit_code != 0 or reason not in ['Completed']:
                    is_unhealthy = True
                    severity = 4  # Medium-high severity for termination with non-zero exit code
                    issues.append({
                        'type': f"container_terminated_{reason}",
                        'message': f"Container {container_status.name} terminated: {reason} (exit code {exit_code})",
                        'severity': severity
                    })
                    error_severity = max(error_severity, severity)
            
            # Check for container not ready
            if not container_status.ready and pod.status.phase == 'Running':
                is_unhealthy = True
                severity = 3  # Medium severity for not ready containers
                issues.append({
                    'type': "container_not_ready",
                    'message': f"Container {container_status.name} is not ready",
                    'severity': severity
                })
                error_severity = max(error_severity, severity)
        
        # Check for high restart count (more than 5)
        if restart_count > 5:
            is_unhealthy = True
            severity = min(restart_count // 5, 8)  # Scale with number of restarts, capped at 8
            issues.append({
                'type': "high_restart_count",
                'message': f"Pod has high restart count: {restart_count}",
                'severity': severity
            })
            error_severity = max(error_severity, severity)
        
        # Check for pod in non-running state
        if pod.status.phase != 'Running' and pod.status.phase != 'Succeeded':
            is_unhealthy = True
            
            # Map phase to severity
            phase_severity = {
                'Pending': 2,
                'Failed': 6,
                'Unknown': 4,
            }
            
            severity = phase_severity.get(pod.status.phase, 3)
            issues.append({
                'type': f"non_running_phase_{pod.status.phase}",
                'message': f"Pod in non-running state: {pod.status.phase}",
                'severity': severity
            })
            error_severity = max(error_severity, severity)
        
        # Check pod conditions
        for condition in pod.status.conditions or []:
            # Check for critical conditions that aren't True (except for normal ones like PodScheduled)
            if condition.type not in ['PodScheduled'] and condition.status != 'True':
                is_unhealthy = True
                severity = 3  # Medium severity for condition issues
                issues.append({
                    'type': f"condition_{condition.type}_{condition.status}",
                    'message': f"Pod condition {condition.type} is {condition.status}: {condition.reason}",
                    'severity': severity
                })
                error_severity = max(error_severity, severity)
        
        return {
            'pod_name': pod_name,
            'is_unhealthy': is_unhealthy,
            'issues': issues,
            'max_severity': error_severity
        }
    
    def start_monitoring(self) -> None:
        """Start the monitoring loop in a background thread"""
        if self.running:
            logger.warning("Monitoring already running, ignoring start request")
            return
            
        self.running = True
        self.monitor_thread = threading.Thread(
            target=self._monitoring_loop,
            daemon=True
        )
        self.monitor_thread.start()
        logger.info(f"Pod restart agent monitoring started for namespace {self.namespace}")
    
    def stop_monitoring(self) -> None:
        """Stop the monitoring loop"""
        if not self.running:
            logger.warning("Monitoring not running, ignoring stop request")
            return
            
        self.running = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=5.0)
        logger.info("Pod restart agent monitoring stopped")
    
    def _monitoring_loop(self) -> None:
        """Main monitoring loop that runs continuously"""
        logger.info(f"Starting pod restart agent monitoring loop (interval: {self.check_interval}s)")
        
        while self.running:
            try:
                # Skip if in mock mode and no mock pods provided
                if self.mock_mode:
                    logger.debug("Running in mock mode, simulating pod monitoring")
                    time.sleep(self.check_interval)
                    continue
                
                # Get all pods in the namespace
                pods = self.core_api.list_namespaced_pod(self.namespace)
                
                if not pods.items:
                    logger.warning(f"No pods found in namespace {self.namespace}")
                    time.sleep(self.check_interval)
                    continue
                
                logger.info(f"Checking health of {len(pods.items)} pods in namespace {self.namespace}")
                
                for pod in pods.items:
                    pod_name = pod.metadata.name
                    
                    # Skip pods that are being terminated
                    if pod.metadata.deletion_timestamp:
                        logger.debug(f"Skipping pod {pod_name} as it's being terminated")
                        continue
                    
                    # Check pod health
                    health_check = self._check_pod_health(pod)
                    
                    # Record errors if unhealthy
                    if health_check['is_unhealthy']:
                        for issue in health_check['issues']:
                            should_restart = self.record_error(
                                pod_name, 
                                issue['type'], 
                                issue['message'],
                                severity=issue['severity']
                            )
                            
                            # Only try to restart if we hit the threshold and are not in cooldown
                            if should_restart and self.should_restart_pod(pod_name):
                                logger.warning(f"Unhealthy pod {pod_name} detected, attempting restart")
                                self.restart_pod(pod_name)
                                # Break after attempting restart to avoid multiple restart attempts
                                break
                
                # Sleep until next check
                time.sleep(self.check_interval)
                
            except Exception as e:
                logger.error(f"Error in monitoring loop: {str(e)}")
                time.sleep(self.check_interval)  # Continue the loop
        
        logger.info("Monitoring loop exited")
    
    def get_pod_status(self, pod_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Get the current status of monitored pods
        
        Args:
            pod_name: Optional specific pod name to get status for
            
        Returns:
            dict: Status information for pods
        """
        if pod_name:
            # Return status for specific pod
            if pod_name in self.error_counts:
                return {
                    'pod_name': pod_name,
                    'error_count': self.error_counts[pod_name]['count'],
                    'last_error_time': self.error_counts[pod_name]['last_error_time'],
                    'errors': self.error_counts[pod_name]['errors'][-10:],  # Last 10 errors
                    'last_restart': self.last_restart.get(pod_name, None),
                    'threshold_reached': self.error_counts[pod_name].get('threshold_reached', False)
                }
            else:
                return {
                    'pod_name': pod_name,
                    'monitored': False,
                    'message': f"Pod {pod_name} is not currently monitored or has no recorded errors"
                }
        
        # Return summary of all pods
        return {
            'monitoring_active': self.running,
            'namespace': self.namespace,
            'error_threshold': self.error_threshold,
            'cooldown_period': self.cooldown_period,
            'check_interval': self.check_interval,
            'mock_mode': self.mock_mode,
            'monitored_pods': len(self.error_counts),
            'restarted_pods': len(self.last_restart),
            'total_restarts': len(self.restart_history),
            'pod_summaries': [
                {
                    'pod_name': pod_name,
                    'error_count': pod_data['count'],
                    'error_types': list(set(err['type'] for err in pod_data['errors'][-10:])),
                    'last_error_time': datetime.fromtimestamp(pod_data['last_error_time']).isoformat(),
                    'last_restart': datetime.fromtimestamp(self.last_restart.get(pod_name, 0)).isoformat() 
                        if pod_name in self.last_restart else None,
                    'threshold_reached': pod_data.get('threshold_reached', False)
                }
                for pod_name, pod_data in self.error_counts.items()
            ],
            'recent_restarts': self.restart_history[-10:]  # Last 10 restarts
        }


# Singleton instance of the agent
_pod_restart_agent = None

def get_pod_restart_agent():
    """Get the singleton instance of the pod restart agent"""
    global _pod_restart_agent
    if _pod_restart_agent is None:
        # Initialize with environment variables if available
        namespace = os.environ.get('K8S_NAMESPACE', 'default')
        error_threshold = int(os.environ.get('POD_ERROR_THRESHOLD', '10'))
        cooldown_period = int(os.environ.get('POD_RESTART_COOLDOWN', '300'))
        check_interval = int(os.environ.get('AGENT_CHECK_INTERVAL', '60'))
        mock_mode = os.environ.get('AGENT_MOCK_MODE', '').lower() in ('true', '1', 't')
        
        _pod_restart_agent = PodRestartAgent(
            namespace=namespace,
            error_threshold=error_threshold,
            cooldown_period=cooldown_period,
            check_interval=check_interval,
            mock_mode=mock_mode
        )
    
    return _pod_restart_agent


def init_pod_restart_agent() -> bool:
    """
    Initialize the pod restart agent and start monitoring
    
    Returns:
        bool: True if initialization was successful
    """
    try:
        agent = get_pod_restart_agent()
        agent.start_monitoring()
        logger.info("Pod restart agent initialized and monitoring started")
        return True
    except Exception as e:
        logger.error(f"Failed to initialize pod restart agent: {str(e)}")
        return False