# Telecom L1 Monitoring Application with RAG-based LLM

A sophisticated, locally-hosted GenAI application for L1 monitoring that uses RAG (Retrieval-Augmented Generation) to provide intelligent telecom-specific troubleshooting suggestions based on log analysis. Specialized for 5G Core and OpenRAN environments.

![L1 Monitoring Application Screenshot](generated-icon.png)

## Key Features

### Telecom-Specific Capabilities
- **5G Core Support**: Specialized knowledge and processing for AMF, SMF, UPF, AUSF, and other 5G Core network functions
- **OpenRAN Integration**: Support for O-DU, O-CU-CP, O-CU-UP components and interfaces
- **Telecom Metadata Extraction**: Automatically identifies network functions, interfaces, and telecom procedures
- **Domain-Specific Knowledge Base**: Integrated 5G and OpenRAN knowledge for intelligent analysis

### Core Functionality
- **Log Collection & Processing**: Upload and parse log files from telecom systems
- **High-Performance Log Storage**: Store logs in ClickHouse for fast analytics and querying
- **Three-Tier Database Fallback**: Automatic fallback from ClickHouse to PostgreSQL to SQLite for flexible deployment
- **ML-based Anomaly Detection**: Automatically identify unusual patterns in telecom logs
- **Vector Search**: Implement vector similarity search to find relevant logs for troubleshooting
- **Local LLM Integration**: Use locally-simulated telecom-specific LLM responses without external API dependencies
- **RAG Implementation**: Retrieve relevant logs and domain knowledge to provide context for AI suggestions
- **Dark-Mode Interactive UI**: View logs, charts, and AI-generated suggestions in a responsive web interface

## Architecture

The application consists of the following components:

1. **Flask Backend**: Serves the web application and APIs
2. **ClickHouse Database**: High-performance columnar database for log storage and analytics
3. **PostgreSQL Database**: Secondary database option with PostgreSQL
4. **SQLite Fallback**: Final fallback database option for development and testing
5. **Vector Store**: Maintains embeddings for semantic search of logs
6. **Simulated LLM Interface**: Provides sophisticated telecom-specific analysis without external API dependencies
7. **RAG Engine**: Combines vector search with telecom knowledge to generate contextual suggestions
8. **Telecom Processor**: Specialized component for parsing and extracting metadata from telecom logs
9. **ML Anomaly Detector**: Machine learning-based system for identifying anomalies in log patterns

## Deployment Options

### Windows Deployment

For detailed Windows installation and deployment instructions, see [WINDOWS_DEPLOYMENT.md](WINDOWS_DEPLOYMENT.md).

Quick Windows deployment steps:
1. Download and extract the application
2. Install ClickHouse (see [CLICKHOUSE_WINDOWS_SETUP.md](CLICKHOUSE_WINDOWS_SETUP.md))
3. Run `setup_clickhouse_windows.bat` to configure the database
4. Run `start_app.bat` to launch the application
5. Open `http://localhost:5000` in your browser

### Linux/macOS Setup

#### Prerequisites

- Python 3.9+
- ClickHouse (or the application will fallback to PostgreSQL, then SQLite)
- (Optional) OLLAMA for external LLM integration

#### Installation

1. **Clone the repository**:
   ```
   git clone https://github.com/yourusername/l1-monitoring-app.git
   cd l1-monitoring-app
   ```

2. **Install dependencies**:
   ```
   pip install -r requirements.txt
   ```

3. **Install ClickHouse (optional but recommended)**:
   ```
   # Run the installer script
   chmod +x install_clickhouse.sh
   ./install_clickhouse.sh
   ```

4. **Set up the database**:
   ```
   # Update your ClickHouse connection string in .env
   echo "DATABASE_URL=clickhouse://default:@localhost:8123/default" > .env
   ```

5. **Run the application**:
   ```
   gunicorn --bind 0.0.0.0:5000 main:app
   ```

6. Open the application in your browser at `http://localhost:5000`

### Kubernetes Deployment

The application is Kubernetes-ready. Deploy using the provided manifests:

```
cd k8s
./deploy.sh
```

For more details, see the deployment documentation in the `k8s` directory.

## Usage

### Uploading Logs

1. Click on the "Upload Logs" button
2. Select a log file (text-based logs in various formats are supported)
3. The logs will be parsed, stored in the database, and indexed for vector search

### Analyzing Logs

1. Enter a question or issue description in the analysis box
2. Optionally select specific logs you want to include in the analysis
3. Click "Analyze" to generate a suggestion
4. View the suggestion and the relevant logs that were used to generate it

### Viewing Log Statistics

The dashboard displays various statistics about your logs:
- Distribution by log level (ERROR, WARN, INFO, etc.)
- Distribution by service
- Timeline of log events

## Extending the Application

### Adding Support for New Telecom Log Formats

To support additional telecom log formats:
1. Edit `utils/telecom_processor.py` to add parsing logic
2. Update the pattern detection in the `detect_telecom_log_type` method
3. Add any specialized metadata extraction in `enrich_log_entry`

### Expanding the Knowledge Base

Enhance the telecom knowledge base by:
1. Adding more content to existing files in `data/telecom_kb/` 
2. Creating new knowledge files for additional network functions or components
3. Updating `utils/telecom_rag_engine.py` to reference new knowledge sources

### Customizing LLM Responses

Modify telecom-specific responses in `utils/llm_interface.py`:
1. Add new condition blocks to the `_generate_mock_response` method
2. Expand patterns to match more telecom-specific queries
3. Add domain expertise for additional network functions or interfaces

## Advanced Features

### ML Anomaly Detection

The application uses Isolation Forest and TF-IDF vectorization to detect anomalies in telecom logs. You can:
1. Tune detection parameters in `utils/ml_anomaly_detector.py`
2. Add new patterns for telecom-specific anomalies in `utils/telecom_processor.py`
3. Customize response generation for anomaly explanations

### Kubernetes Deployment

The application is designed for Kubernetes with:
1. Separate deployments for app, database, and (optionally) OLLAMA
2. Configurable resource settings for telecom-scale deployments
3. Service mesh compatibility for complex network configurations

## Troubleshooting

### Windows Deployment Issues
See [WINDOWS_DEPLOYMENT.md](WINDOWS_DEPLOYMENT.md) for Windows-specific troubleshooting.

### Database Connection Issues
- Verify ClickHouse is running and accessible on port 8123
- Run `clickhouse-client -q "SELECT version()"` to test the connection
- Check database credentials in your `.env` file
- Review CLICKHOUSE_WINDOWS_SETUP.md for detailed troubleshooting
- The application will automatically fall back to PostgreSQL if ClickHouse is unavailable, and to SQLite if PostgreSQL is also unavailable
- For Kubernetes, ensure persistent volumes are properly configured

### Log Processing Problems
- For telecom log parsing issues, check `utils/telecom_processor.py`
- For general log parsing, review patterns in `config.py`
- Debug metadata extraction by adding logging statements in processing functions