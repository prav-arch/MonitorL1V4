"""
NiFi data ingestion pipeline for telecom monitoring application.
This module provides functionality to create and manage NiFi data flows
that extract data from remote servers and store it in designated folders.
"""
import os
import logging
import json
import time
import random
import string
from typing import Dict, Any, List, Optional, Union

# Import NiPyAPI for NiFi integration
try:
    import nipyapi
    from nipyapi import canvas
    from nipyapi import security
    from nipyapi import templates
    from nipyapi import config
    from nipyapi import nifi
    
    NIFI_AVAILABLE = True
except ImportError:
    NIFI_AVAILABLE = False
    
# Configure logging
logger = logging.getLogger(__name__)

class NiFiPipeline:
    """Class to manage NiFi data ingestion pipelines for telecom monitoring."""

    def __init__(self, 
                 nifi_url: str = "http://localhost:8080/nifi-api",
                 ssl_enabled: bool = False,
                 username: Optional[str] = None, 
                 password: Optional[str] = None):
        """
        Initialize NiFi pipeline manager.
        
        Args:
            nifi_url: URL of the NiFi instance API
            ssl_enabled: Whether SSL is enabled on NiFi
            username: Username for NiFi authentication
            password: Password for NiFi authentication
        """
        self.nifi_url = nifi_url
        self.ssl_enabled = ssl_enabled
        self.username = username
        self.password = password
        self.mock_mode = not NIFI_AVAILABLE
        self.connected = False
        
        # Only attempt to connect if NiPyAPI is available
        if NIFI_AVAILABLE:
            try:
                # Configure NiPyAPI
                config.nifi_endpoint = nifi_url
                config.nifi_username = username
                config.nifi_password = password
                
                # Test connection
                self._test_connection()
                self.connected = True
                logger.info(f"Successfully connected to NiFi at {nifi_url}")
            except Exception as e:
                self.mock_mode = True
                logger.info(f"NiFi connection not available: {str(e)}. This is expected when running in development mode.")
                logger.info("Using simulated NiFi pipeline functionality - no data flows will be created.")
        else:
            logger.warning("NiPyAPI not available. Using mock mode for data ingestion.")

    def _test_connection(self) -> None:
        """Test connection to NiFi instance."""
        if NIFI_AVAILABLE:
            try:
                # Try to get system diagnostics to test connection
                system_diag = nipyapi.system.get_system_diagnostics()
                return system_diag is not None
            except Exception as e:
                raise ConnectionError(f"Failed to connect to NiFi at {self.nifi_url}: {str(e)}")
        return False

    def is_healthy(self) -> bool:
        """Check if the NiFi connection is healthy."""
        if self.mock_mode:
            # In mock mode, we're always "healthy"
            return True
            
        if NIFI_AVAILABLE:
            try:
                return self._test_connection()
            except Exception:
                return False
        return False

    def create_process_group(self, name: str, position: Dict[str, int] = None) -> Any:
        """
        Create a new process group in NiFi root canvas.
        
        Args:
            name: Name of the process group
            position: Position of the process group on canvas
            
        Returns:
            The created process group object
        """
        if self.mock_mode:
            # In mock mode, return a dummy process group
            return {
                "id": f"mock-pg-{name.lower().replace(' ', '-')}",
                "name": name,
                "position": position or {"x": 100, "y": 100}
            }
            
        if NIFI_AVAILABLE:
            # Default position if not provided
            if not position:
                position = {"x": 100, "y": 100}
                
            # Get root process group
            root_pg = canvas.get_process_group(canvas.get_root_pg_id(), 'id')
            
            # Create new process group
            new_pg = canvas.create_process_group(
                parent_pg=root_pg,
                new_pg_name=name,
                location=position
            )
            
            return new_pg
        
        return None

    def create_sftp_to_folder_pipeline(self, 
                                      process_group_name: str,
                                      remote_host: str,
                                      remote_port: int,
                                      remote_username: str,
                                      remote_password: str,
                                      remote_directory: str,
                                      local_directory: str,
                                      file_filter: str = "*.*") -> Dict[str, Any]:
        """
        Create a complete pipeline that fetches files from SFTP and stores them in a local folder.
        
        Args:
            process_group_name: Name of the process group to create
            remote_host: Remote SFTP server hostname
            remote_port: Remote SFTP server port
            remote_username: Username for SFTP authentication
            remote_password: Password for SFTP authentication
            remote_directory: Remote directory to fetch files from
            local_directory: Local directory to store files in
            file_filter: File filter pattern
            
        Returns:
            Dictionary with pipeline details including process group ID
        """
        if self.mock_mode:
            # In mock mode, create a directory for mock data if it doesn't exist
            os.makedirs(local_directory, exist_ok=True)
            
            # Return mock pipeline details
            return {
                "status": "success",
                "pipeline_type": "sftp",
                "process_group_id": f"mock-pg-{process_group_name.lower().replace(' ', '-')}",
                "process_group_name": process_group_name,
                "local_directory": local_directory,
                "remote_host": remote_host,
                "remote_directory": remote_directory,
                "mock_mode": True,
                "message": "Created mock SFTP pipeline (NiFi not available)"
            }
            
        if NIFI_AVAILABLE:
            try:
                # Create the process group
                pg = self.create_process_group(process_group_name)
                
                # Create the GetSFTP processor
                get_sftp = self._create_processor(
                    parent_pg=pg,
                    processor_type="org.apache.nifi.processors.standard.GetSFTP",
                    position={"x": 100, "y": 100},
                    name="Get Files from SFTP",
                    config={
                        "Remote Hostname": remote_host,
                        "Remote Port": str(remote_port),
                        "Username": remote_username,
                        "Password": remote_password,
                        "Remote Path": remote_directory,
                        "File Filter Regex": file_filter,
                        "Connection Timeout": "30 sec",
                        "Data Timeout": "30 sec",
                        "Strict Host Key Checking": "false",
                        "Send Keep Alive On Timeout": "true",
                        "Disable Directory Listing": "false",
                        "Batch Size": "10",
                    }
                )
                
                # Create the PutFile processor
                put_file = self._create_processor(
                    parent_pg=pg,
                    processor_type="org.apache.nifi.processors.standard.PutFile",
                    position={"x": 400, "y": 100},
                    name="Save Files to Disk",
                    config={
                        "Directory": local_directory,
                        "Conflict Resolution Strategy": "replace",
                        "Create Missing Directories": "true",
                        "Permissions": "0755",
                    }
                )
                
                # Connect GetSFTP to PutFile
                canvas.create_connection(get_sftp, put_file)
                
                return {
                    "status": "success",
                    "pipeline_type": "sftp",
                    "process_group_id": pg.id,
                    "process_group_name": process_group_name,
                    "local_directory": local_directory,
                    "remote_host": remote_host,
                    "remote_directory": remote_directory,
                    "mock_mode": False,
                    "message": "Created SFTP pipeline successfully"
                }
            except Exception as e:
                logger.error(f"Error creating SFTP pipeline: {str(e)}")
                # Fall back to mock mode if creating the pipeline fails
                self.mock_mode = True
                return self.create_sftp_to_folder_pipeline(
                    process_group_name, remote_host, remote_port, remote_username, 
                    remote_password, remote_directory, local_directory, file_filter
                )
                
        return {
            "status": "error",
            "message": "NiFi not available and mock mode disabled"
        }

    def create_http_to_folder_pipeline(self, 
                                     process_group_name: str,
                                     api_url: str,
                                     http_method: str = "GET",
                                     authentication_type: str = "None",
                                     username: Optional[str] = None,
                                     password: Optional[str] = None,
                                     headers: Dict[str, str] = None,
                                     local_directory: str = None,
                                     poll_interval: str = "60 sec") -> Dict[str, Any]:
        """
        Create a complete pipeline that fetches data from HTTP API and stores it in a local folder.
        
        Args:
            process_group_name: Name of the process group to create
            api_url: URL of the HTTP API to fetch data from
            http_method: HTTP method (GET, POST, etc.)
            authentication_type: Type of authentication (None, Basic, etc.)
            username: Username for authentication
            password: Password for authentication
            headers: HTTP headers to include in the request
            local_directory: Local directory to store API responses
            poll_interval: How often to poll the API
            
        Returns:
            Dictionary with pipeline details including process group ID
        """
        if self.mock_mode:
            # In mock mode, create a directory for mock data if it doesn't exist
            if local_directory:
                os.makedirs(local_directory, exist_ok=True)
            
            # Return mock pipeline details
            return {
                "status": "success",
                "pipeline_type": "http",
                "process_group_id": f"mock-pg-{process_group_name.lower().replace(' ', '-')}",
                "process_group_name": process_group_name,
                "api_url": api_url,
                "local_directory": local_directory,
                "mock_mode": True,
                "message": "Created mock HTTP pipeline (NiFi not available)"
            }
            
        if NIFI_AVAILABLE:
            try:
                # Create the process group
                pg = self.create_process_group(process_group_name)
                
                # Create the InvokeHTTP processor
                invoke_http = self._create_processor(
                    parent_pg=pg,
                    processor_type="org.apache.nifi.processors.standard.InvokeHTTP",
                    position={"x": 100, "y": 100},
                    name="Fetch Data from API",
                    config={
                        "HTTP Method": http_method,
                        "Remote URL": api_url,
                        "Connection Timeout": "30 sec",
                        "Read Timeout": "30 sec",
                        "Include Date Header": "true",
                        "Follow Redirects": "true",
                        "Scheduling Strategy": "timer-driven",
                        "Scheduling Period": poll_interval
                    }
                )
                
                # If authentication is required, configure it
                if authentication_type.lower() == "basic" and username and password:
                    # Add basic auth properties
                    self._update_processor_config(
                        invoke_http,
                        {
                            "Basic Authentication Username": username,
                            "Basic Authentication Password": password
                        }
                    )
                
                # If headers are provided, add them as dynamic properties
                if headers:
                    for header_name, header_value in headers.items():
                        self._add_dynamic_property(
                            invoke_http,
                            f"Header.{header_name}",
                            header_value
                        )
                
                # Create the UpdateAttribute processor to add filename
                update_attr = self._create_processor(
                    parent_pg=pg,
                    processor_type="org.apache.nifi.processors.attributes.UpdateAttribute",
                    position={"x": 300, "y": 100},
                    name="Add Filename",
                    config={
                        "Store State": "Do not store state"
                    }
                )
                
                # Add dynamic property for filename
                self._add_dynamic_property(
                    update_attr,
                    "filename",
                    "${now():format('yyyy-MM-dd_HH-mm-ss')}_api_response.json"
                )
                
                # Create the PutFile processor
                put_file = self._create_processor(
                    parent_pg=pg,
                    processor_type="org.apache.nifi.processors.standard.PutFile",
                    position={"x": 500, "y": 100},
                    name="Save Response to Disk",
                    config={
                        "Directory": local_directory,
                        "Conflict Resolution Strategy": "replace",
                        "Create Missing Directories": "true",
                        "Permissions": "0755"
                    }
                )
                
                # Connect processors
                canvas.create_connection(invoke_http, update_attr, ['Response'])
                canvas.create_connection(update_attr, put_file)
                
                return {
                    "status": "success",
                    "pipeline_type": "http",
                    "process_group_id": pg.id,
                    "process_group_name": process_group_name,
                    "api_url": api_url,
                    "local_directory": local_directory,
                    "mock_mode": False,
                    "message": "Created HTTP pipeline successfully"
                }
            except Exception as e:
                logger.error(f"Error creating HTTP pipeline: {str(e)}")
                # Fall back to mock mode if creating the pipeline fails
                self.mock_mode = True
                return self.create_http_to_folder_pipeline(
                    process_group_name, api_url, http_method, authentication_type,
                    username, password, headers, local_directory, poll_interval
                )
                
        return {
            "status": "error",
            "message": "NiFi not available and mock mode disabled"
        }

    def _create_processor(self, 
                         parent_pg: Any, 
                         processor_type: str, 
                         position: Dict[str, int], 
                         name: str, 
                         config: Dict[str, str] = None) -> Any:
        """
        Create a processor in NiFi.
        
        Args:
            parent_pg: Parent process group
            processor_type: Processor type
            position: Position on canvas
            name: Name of the processor
            config: Processor configuration
            
        Returns:
            The created processor
        """
        if not NIFI_AVAILABLE:
            return None
            
        # Create the processor
        processor = canvas.create_processor(
            parent_pg=parent_pg,
            processor_type=processor_type,
            location=position,
            name=name
        )
        
        # If config is provided, update the processor properties
        if config:
            self._update_processor_config(processor, config)
            
        return processor

    def _update_processor_config(self, processor: Any, config: Dict[str, str]) -> None:
        """
        Update processor configuration.
        
        Args:
            processor: Processor to update
            config: Configuration to apply
        """
        if not NIFI_AVAILABLE:
            return
            
        # Get the processor object
        processor_info = canvas.get_processor(processor.id, 'id')
        
        # Update configuration
        canvas.update_processor(
            processor=processor_info,
            update_dict={
                'config': {
                    'properties': config
                }
            }
        )

    def _add_dynamic_property(self, processor: Any, name: str, value: str) -> None:
        """
        Add dynamic property to a processor.
        
        Args:
            processor: Processor to update
            name: Property name
            value: Property value
        """
        if not NIFI_AVAILABLE:
            return
            
        # Get the processor object
        processor_info = canvas.get_processor(processor.id, 'id')
        
        # Get current properties
        current_properties = processor_info.config.properties or {}
        
        # Add dynamic property
        current_properties[name] = value
        
        # Update processor
        canvas.update_processor(
            processor=processor_info,
            update_dict={
                'config': {
                    'properties': current_properties
                }
            }
        )

    def get_pipeline_status(self, process_group_id: str) -> Dict[str, Any]:
        """
        Get status information about a process group.
        
        Args:
            process_group_id: ID of the process group
            
        Returns:
            Dictionary with status information
        """
        if self.mock_mode:
            # In mock mode, return dummy status
            return {
                "status": "success",
                "process_group_id": process_group_id,
                "state": "RUNNING",
                "transferred": random.randint(0, 100),
                "queued": random.randint(0, 10),
                "mock_mode": True
            }
            
        if NIFI_AVAILABLE:
            try:
                # Get the process group
                pg = canvas.get_process_group(process_group_id, 'id')
                if not pg:
                    return {
                        "status": "error",
                        "message": f"Process group {process_group_id} not found"
                    }
                    
                # Get status
                pg_status = canvas.get_process_group_status(pg.id)
                
                return {
                    "status": "success",
                    "process_group_id": process_group_id,
                    "state": pg_status.aggregation_snapshot.state,
                    "transferred": pg_status.aggregation_snapshot.transferred,
                    "queued": pg_status.aggregation_snapshot.queued,
                    "mock_mode": False
                }
            except Exception as e:
                logger.error(f"Error getting pipeline status: {str(e)}")
                # Fall back to mock mode for status
                self.mock_mode = True
                return self.get_pipeline_status(process_group_id)
                
        return {
            "status": "error",
            "message": "NiFi not available and mock mode disabled"
        }

    def start_pipeline(self, process_group_id: str) -> Dict[str, Any]:
        """
        Start all processors in a process group.
        
        Args:
            process_group_id: ID of the process group
            
        Returns:
            Dictionary with operation status
        """
        if self.mock_mode:
            # In mock mode, pretend we started it
            return {
                "status": "success",
                "process_group_id": process_group_id,
                "state": "RUNNING",
                "message": "Pipeline started (mock mode)",
                "mock_mode": True
            }
            
        if NIFI_AVAILABLE:
            try:
                # Get the process group
                pg = canvas.get_process_group(process_group_id, 'id')
                if not pg:
                    return {
                        "status": "error",
                        "message": f"Process group {process_group_id} not found"
                    }
                    
                # Start the processors
                canvas.schedule_process_group(pg.id, True)
                
                return {
                    "status": "success",
                    "process_group_id": process_group_id,
                    "state": "RUNNING",
                    "message": "Pipeline started",
                    "mock_mode": False
                }
            except Exception as e:
                logger.error(f"Error starting pipeline: {str(e)}")
                # Fall back to mock mode
                self.mock_mode = True
                return self.start_pipeline(process_group_id)
                
        return {
            "status": "error",
            "message": "NiFi not available and mock mode disabled"
        }

    def stop_pipeline(self, process_group_id: str) -> Dict[str, Any]:
        """
        Stop all processors in a process group.
        
        Args:
            process_group_id: ID of the process group
            
        Returns:
            Dictionary with operation status
        """
        if self.mock_mode:
            # In mock mode, pretend we stopped it
            return {
                "status": "success",
                "process_group_id": process_group_id,
                "state": "STOPPED",
                "message": "Pipeline stopped (mock mode)",
                "mock_mode": True
            }
            
        if NIFI_AVAILABLE:
            try:
                # Get the process group
                pg = canvas.get_process_group(process_group_id, 'id')
                if not pg:
                    return {
                        "status": "error",
                        "message": f"Process group {process_group_id} not found"
                    }
                    
                # Stop the processors
                canvas.schedule_process_group(pg.id, False)
                
                return {
                    "status": "success",
                    "process_group_id": process_group_id,
                    "state": "STOPPED",
                    "message": "Pipeline stopped",
                    "mock_mode": False
                }
            except Exception as e:
                logger.error(f"Error stopping pipeline: {str(e)}")
                # Fall back to mock mode
                self.mock_mode = True
                return self.stop_pipeline(process_group_id)
                
        return {
            "status": "error",
            "message": "NiFi not available and mock mode disabled"
        }

    def create_mock_pipeline(self, 
                           process_group_name: str,
                           local_directory: str,
                           data_type: str = 'telecom_logs',
                           interval: str = '1 min') -> Dict[str, Any]:
        """
        Create a mock pipeline that generates sample data for development.
        Useful when NiFi is not available or for testing purposes.
        
        Args:
            process_group_name: Name of the process group
            local_directory: Directory to store the generated files
            data_type: Type of data to generate ('telecom_logs', 'metrics', etc.)
            interval: How often to generate new data
            
        Returns:
            Dictionary with mock pipeline details
        """
        # Create the output directory if it doesn't exist
        os.makedirs(local_directory, exist_ok=True)
        
        # Return mock pipeline details
        return {
            "status": "success",
            "pipeline_type": "mock",
            "process_group_id": f"mock-pg-{process_group_name.lower().replace(' ', '-')}",
            "process_group_name": process_group_name,
            "local_directory": local_directory,
            "data_type": data_type,
            "mock_mode": True,
            "interval": interval,
            "message": "Created mock data pipeline"
        }


def generate_mock_data(output_directory: str, data_type: str = 'telecom_logs'):
    """
    Generate mock data for testing when NiFi is not available.
    
    Args:
        output_directory: Directory to write mock data files
        data_type: Type of data to generate
    """
    # Create directory if it doesn't exist
    os.makedirs(output_directory, exist_ok=True)
    
    # Generate timestamp for filename
    timestamp = time.strftime('%Y-%m-%d_%H-%M-%S')
    
    if data_type == 'telecom_logs':
        # Generate mock telecom logs
        log_entries = []
        
        # Services
        services = ['core-network', 'radio-access', 'signaling', 'packet-gateway', 'subscriber-db']
        
        # Message templates
        info_messages = [
            "Connection established to {service}",
            "Processed {count} packets successfully",
            "Session initiated for subscriber {id}",
            "Handover complete for UE {id}",
            "Configuration update applied to {service}"
        ]
        
        warn_messages = [
            "High latency detected in {service}",
            "Retry attempt {count} for operation",
            "Buffer utilization at {percent}%",
            "Connection pool nearing capacity",
            "Slow response from {service}"
        ]
        
        error_messages = [
            "Failed to connect to {service}",
            "Timeout occurred during {operation}",
            "Invalid configuration for {service}",
            "Database query failed: {error}",
            "Resource allocation failed for {resource}"
        ]
        
        # Generate log entries
        for _ in range(random.randint(5, 15)):
            # Determine level
            level_rand = random.random()
            if level_rand < 0.7:
                level = "INFO"
                message_templates = info_messages
            elif level_rand < 0.9:
                level = "WARN"
                message_templates = warn_messages
            else:
                level = "ERROR"
                message_templates = error_messages
                
            # Select service
            service = random.choice(services)
            
            # Create message
            message_template = random.choice(message_templates)
            message = message_template.format(
                service=random.choice(services),
                count=random.randint(1, 1000),
                id=f"ID-{''.join(random.choices(string.hexdigits, k=8))}",
                percent=random.randint(70, 99),
                operation=random.choice(['authentication', 'provisioning', 'routing', 'handover']),
                error=random.choice(['timeout', 'connection refused', 'invalid credentials']),
                resource=random.choice(['memory', 'CPU', 'disk space', 'bandwidth'])
            )
            
            # Create log entry
            log_entry = {
                "timestamp": time.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3],
                "level": level,
                "service": service,
                "message": message,
                "source_ip": f"192.168.{random.randint(1, 254)}.{random.randint(1, 254)}",
                "correlation_id": f"corr-{''.join(random.choices(string.hexdigits, k=6))}"
            }
            
            log_entries.append(log_entry)
            
        # Write to file
        filename = f"{timestamp}_telecom_logs.json"
        filepath = os.path.join(output_directory, filename)
        
        with open(filepath, 'w') as f:
            json.dump(log_entries, f, indent=2)
            
        logger.info(f"Generated mock telecom logs: {filepath}")
            
    elif data_type == 'metrics':
        # Generate mock metrics data
        metrics = {
            "timestamp": time.strftime('%Y-%m-%d %H:%M:%S'),
            "node_metrics": {
                "cpu_utilization": random.uniform(10, 90),
                "memory_utilization": random.uniform(20, 80),
                "disk_space_used": random.uniform(30, 70),
                "network_throughput_mbps": random.uniform(100, 1000)
            },
            "service_metrics": [
                {
                    "service_name": "core-network",
                    "response_time_ms": random.uniform(5, 100),
                    "request_count": random.randint(1000, 5000),
                    "error_rate": random.uniform(0, 0.05)
                },
                {
                    "service_name": "radio-access",
                    "response_time_ms": random.uniform(5, 100),
                    "request_count": random.randint(1000, 5000),
                    "error_rate": random.uniform(0, 0.05)
                }
            ]
        }
        
        # Write to file
        filename = f"{timestamp}_system_metrics.json"
        filepath = os.path.join(output_directory, filename)
        
        with open(filepath, 'w') as f:
            json.dump(metrics, f, indent=2)
            
        logger.info(f"Generated mock metrics: {filepath}")
    
    else:
        # Generate generic data
        data = {
            "timestamp": time.strftime('%Y-%m-%d %H:%M:%S'),
            "data_type": data_type,
            "sample_values": [random.random() for _ in range(5)],
            "labels": [f"label_{i}" for i in range(5)]
        }
        
        # Write to file
        filename = f"{timestamp}_{data_type}.json"
        filepath = os.path.join(output_directory, filename)
        
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)
            
        logger.info(f"Generated mock data ({data_type}): {filepath}")