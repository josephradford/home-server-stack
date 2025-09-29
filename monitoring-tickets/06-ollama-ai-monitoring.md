# Implement Ollama AI Model Monitoring

## Priority: 2 (High)
## Estimated Time: 3-4 hours
## Phase: Week 2 - Service-Specific Monitoring

## Description
Implement comprehensive monitoring for Ollama AI service including model availability, inference response times, GPU/CPU utilization during inference, model loading/unloading events, and API health monitoring.

## Acceptance Criteria
- [ ] Ollama API metrics exported to Prometheus
- [ ] Model availability and loading status tracking
- [ ] Inference request latency and throughput monitoring
- [ ] Resource utilization during AI inference
- [ ] Custom Ollama dashboard in Grafana
- [ ] Alerts for model failures and performance issues
- [ ] Model usage analytics and statistics
- [ ] GPU monitoring if available

## Technical Implementation Details

### Files to Create/Modify
1. `monitoring/exporters/ollama-exporter.py` - Custom Ollama metrics exporter
2. `monitoring/grafana/dashboards/ollama-ai.json` - Ollama-specific dashboard
3. `monitoring/prometheus/prometheus.yml` - Add Ollama scrape config
4. `monitoring/prometheus/alert_rules.yml` - Add Ollama-specific alerts
5. `docker-compose.monitoring.yml` - Add Ollama exporter service

### Ollama Metrics to Monitor
1. **Model Management**:
   - Available models count
   - Loaded models in memory
   - Model loading/unloading events
   - Model file sizes and disk usage

2. **Inference Performance**:
   - Request latency percentiles
   - Tokens per second generation rate
   - Concurrent request handling
   - Queue depth and wait times

3. **Resource Utilization**:
   - CPU usage during inference
   - Memory consumption per model
   - GPU utilization (if available)
   - Disk I/O for model loading

4. **API Health**:
   - Service availability
   - API response codes
   - Connection timeouts
   - Error rate tracking

### Custom Ollama Exporter (`monitoring/exporters/ollama-exporter.py`)
```python
#!/usr/bin/env python3
"""
Ollama Prometheus Exporter
Exports metrics from Ollama API to Prometheus format
"""

import time
import requests
import json
import psutil
import os
import logging
from prometheus_client import start_http_server, Gauge, Counter, Histogram, Info
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Ollama configuration
OLLAMA_URL = os.getenv('OLLAMA_URL', 'http://ollama:11434')
EXPORTER_PORT = int(os.getenv('EXPORTER_PORT', '9619'))
COLLECT_INTERVAL = int(os.getenv('COLLECT_INTERVAL', '30'))

# Prometheus metrics
ollama_info = Info('ollama_info', 'Ollama version and build information')
ollama_up = Gauge('ollama_up', 'Ollama service availability (1=up, 0=down)')
ollama_models_available = Gauge('ollama_models_available', 'Number of available models')
ollama_models_loaded = Gauge('ollama_models_loaded', 'Number of currently loaded models')

ollama_requests_total = Counter('ollama_requests_total', 'Total API requests', ['endpoint', 'method', 'status'])
ollama_request_duration = Histogram(
    'ollama_request_duration_seconds',
    'Request duration in seconds',
    ['endpoint', 'model'],
    buckets=[0.1, 0.5, 1, 2, 5, 10, 30, 60, 120, 300]
)

ollama_generation_tokens = Counter('ollama_generation_tokens_total', 'Total tokens generated', ['model'])
ollama_generation_duration = Histogram(
    'ollama_generation_duration_seconds',
    'Generation duration in seconds',
    ['model'],
    buckets=[0.1, 0.5, 1, 2, 5, 10, 30, 60, 120]
)

ollama_tokens_per_second = Gauge('ollama_tokens_per_second', 'Current tokens per second generation rate', ['model'])
ollama_model_size_bytes = Gauge('ollama_model_size_bytes', 'Model size in bytes', ['model'])
ollama_memory_usage = Gauge('ollama_memory_usage_bytes', 'Memory usage by Ollama process')
ollama_cpu_usage = Gauge('ollama_cpu_usage_percent', 'CPU usage by Ollama process')

# GPU metrics (if available)
ollama_gpu_usage = Gauge('ollama_gpu_usage_percent', 'GPU usage percentage', ['gpu_id'])
ollama_gpu_memory = Gauge('ollama_gpu_memory_bytes', 'GPU memory usage', ['gpu_id', 'type'])

class OllamaExporter:
    def __init__(self):
        self.session = requests.Session()
        self.session.timeout = 30
        self.last_request_time = {}
        self.process = None
        self.find_ollama_process()

    def find_ollama_process(self):
        """Find the Ollama process for resource monitoring"""
        try:
            for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                if 'ollama' in proc.info['name'].lower():
                    self.process = psutil.Process(proc.info['pid'])
                    logger.info(f"Found Ollama process: PID {proc.info['pid']}")
                    return
        except Exception as e:
            logger.warning(f"Could not find Ollama process: {e}")

    def collect_service_info(self):
        """Collect basic service information"""
        try:
            response = self.session.get(f'{OLLAMA_URL}/api/version')
            response.raise_for_status()

            ollama_up.set(1)
            version_data = response.json()
            ollama_info.info({
                'version': version_data.get('version', 'unknown'),
                'build': version_data.get('build', 'unknown')
            })

        except Exception as e:
            logger.error(f"Error collecting service info: {e}")
            ollama_up.set(0)

    def collect_model_metrics(self):
        """Collect model-related metrics"""
        try:
            # Get list of available models
            response = self.session.get(f'{OLLAMA_URL}/api/tags')
            response.raise_for_status()

            models_data = response.json()
            models = models_data.get('models', [])

            ollama_models_available.set(len(models))

            # Track model sizes
            for model in models:
                model_name = model.get('name', 'unknown')
                model_size = model.get('size', 0)
                ollama_model_size_bytes.labels(model=model_name).set(model_size)

            # Get currently running models
            running_response = self.session.get(f'{OLLAMA_URL}/api/ps')
            if running_response.status_code == 200:
                running_data = running_response.json()
                running_models = running_data.get('models', [])
                ollama_models_loaded.set(len(running_models))

        except Exception as e:
            logger.error(f"Error collecting model metrics: {e}")

    def collect_resource_metrics(self):
        """Collect resource usage metrics"""
        try:
            if self.process and self.process.is_running():
                # CPU usage
                cpu_percent = self.process.cpu_percent()
                ollama_cpu_usage.set(cpu_percent)

                # Memory usage
                memory_info = self.process.memory_info()
                ollama_memory_usage.set(memory_info.rss)

            # GPU metrics (requires nvidia-ml-py if using NVIDIA GPUs)
            self.collect_gpu_metrics()

        except Exception as e:
            logger.error(f"Error collecting resource metrics: {e}")

    def collect_gpu_metrics(self):
        """Collect GPU metrics if available"""
        try:
            import pynvml
            pynvml.nvmlInit()

            device_count = pynvml.nvmlDeviceGetCount()
            for i in range(device_count):
                handle = pynvml.nvmlDeviceGetHandleByIndex(i)

                # GPU utilization
                util = pynvml.nvmlDeviceGetUtilizationRates(handle)
                ollama_gpu_usage.labels(gpu_id=str(i)).set(util.gpu)

                # GPU memory
                mem_info = pynvml.nvmlDeviceGetMemoryInfo(handle)
                ollama_gpu_memory.labels(gpu_id=str(i), type='used').set(mem_info.used)
                ollama_gpu_memory.labels(gpu_id=str(i), type='total').set(mem_info.total)

        except ImportError:
            # pynvml not available, skip GPU metrics
            pass
        except Exception as e:
            logger.debug(f"GPU metrics not available: {e}")

    def test_inference_performance(self):
        """Test inference performance with a simple request"""
        try:
            test_models = ['llama3.1:8b', 'deepseek-coder-v2']

            for model in test_models:
                start_time = time.time()

                payload = {
                    "model": model,
                    "prompt": "Hello, how are you?",
                    "stream": False,
                    "options": {
                        "temperature": 0.1,
                        "num_predict": 10
                    }
                }

                response = self.session.post(
                    f'{OLLAMA_URL}/api/generate',
                    json=payload,
                    timeout=60
                )

                duration = time.time() - start_time

                if response.status_code == 200:
                    data = response.json()

                    # Record metrics
                    ollama_requests_total.labels(
                        endpoint='generate',
                        method='POST',
                        status='200'
                    ).inc()

                    ollama_request_duration.labels(
                        endpoint='generate',
                        model=model
                    ).observe(duration)

                    # Token metrics
                    if 'eval_count' in data:
                        eval_count = data['eval_count']
                        eval_duration = data.get('eval_duration', 0) / 1e9  # Convert to seconds

                        ollama_generation_tokens.labels(model=model).inc(eval_count)
                        ollama_generation_duration.labels(model=model).observe(eval_duration)

                        if eval_duration > 0:
                            tokens_per_sec = eval_count / eval_duration
                            ollama_tokens_per_second.labels(model=model).set(tokens_per_sec)
                else:
                    ollama_requests_total.labels(
                        endpoint='generate',
                        method='POST',
                        status=str(response.status_code)
                    ).inc()

        except Exception as e:
            logger.error(f"Error testing inference performance: {e}")
            ollama_requests_total.labels(
                endpoint='generate',
                method='POST',
                status='error'
            ).inc()

    def collect_all_metrics(self):
        """Collect all metrics"""
        logger.info("Collecting Ollama metrics...")

        self.collect_service_info()
        self.collect_model_metrics()
        self.collect_resource_metrics()

        # Test inference every 5 minutes to avoid overloading
        current_time = time.time()
        if current_time - self.last_request_time.get('inference', 0) > 300:
            self.test_inference_performance()
            self.last_request_time['inference'] = current_time

    def run(self):
        """Main exporter loop"""
        logger.info(f"Starting Ollama exporter on port {EXPORTER_PORT}")
        start_http_server(EXPORTER_PORT)

        while True:
            try:
                self.collect_all_metrics()
                time.sleep(COLLECT_INTERVAL)
            except KeyboardInterrupt:
                logger.info("Exporter stopped")
                break
            except Exception as e:
                logger.error(f"Error in main loop: {e}")
                time.sleep(60)  # Wait longer on error

if __name__ == '__main__':
    exporter = OllamaExporter()
    exporter.run()
```

### Docker Service for Ollama Exporter
Add to `docker-compose.monitoring.yml`:
```yaml
  ollama-exporter:
    build:
      context: ./monitoring/exporters
      dockerfile: Dockerfile.ollama
    container_name: ollama-exporter
    restart: unless-stopped
    environment:
      - OLLAMA_URL=http://ollama:11434
      - EXPORTER_PORT=9619
      - COLLECT_INTERVAL=30
    ports:
      - "9619:9619"
    networks:
      - homeserver
    depends_on:
      - ollama
```

### Dockerfile for Ollama Exporter (`monitoring/exporters/Dockerfile.ollama`)
```dockerfile
FROM python:3.11-alpine

WORKDIR /app

RUN pip install prometheus-client requests psutil

# Optional: Add NVIDIA GPU support
# RUN pip install pynvml

COPY ollama-exporter.py .

EXPOSE 9619

CMD ["python", "ollama-exporter.py"]
```

### Prometheus Scrape Configuration
Add to `monitoring/prometheus/prometheus.yml`:
```yaml
  - job_name: 'ollama-exporter'
    static_configs:
      - targets: ['ollama-exporter:9619']
    scrape_interval: 30s

  - job_name: 'ollama-api'
    static_configs:
      - targets: ['ollama:11434']
    metrics_path: '/api/version'
    scrape_interval: 60s
```

### Ollama-Specific Alert Rules
Add to `monitoring/prometheus/alert_rules.yml`:
```yaml
  - name: ollama-alerts
    rules:
      - alert: OllamaDown
        expr: ollama_up == 0
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "Ollama service is down"
          description: "Ollama AI service is not responding"

      - alert: OllamaNoModelsLoaded
        expr: ollama_models_loaded == 0
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "No Ollama models loaded"
          description: "No AI models are currently loaded in memory"

      - alert: OllamaSlowInference
        expr: histogram_quantile(0.95, rate(ollama_request_duration_seconds_bucket{endpoint="generate"}[10m])) > 30
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Ollama inference is slow"
          description: "95th percentile inference time is {{ $value }}s"

      - alert: OllamaHighCPU
        expr: ollama_cpu_usage_percent > 80
        for: 15m
        labels:
          severity: warning
        annotations:
          summary: "Ollama high CPU usage"
          description: "Ollama CPU usage is {{ $value }}% for more than 15 minutes"

      - alert: OllamaHighMemory
        expr: ollama_memory_usage_bytes > 8e9  # 8GB
        for: 15m
        labels:
          severity: warning
        annotations:
          summary: "Ollama high memory usage"
          description: "Ollama memory usage is {{ $value | humanizeBytes }}"

      - alert: OllamaRequestErrors
        expr: rate(ollama_requests_total{status!="200"}[5m]) > 0.1
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Ollama request errors detected"
          description: "{{ $value }} Ollama requests per second are failing"

      - alert: OllamaLowTokenRate
        expr: ollama_tokens_per_second < 5
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "Ollama token generation rate is low"
          description: "Token generation rate is {{ $value }} tokens/second"
```

### Grafana Dashboard Panels
Key panels for Ollama dashboard:

1. **Service Overview**:
   - Service uptime status
   - Available models count
   - Loaded models count
   - Current token generation rate

2. **Performance Metrics**:
   - Inference latency percentiles
   - Tokens per second over time
   - Request rate and error rate
   - Concurrent request handling

3. **Resource Utilization**:
   - CPU usage during inference
   - Memory usage trends
   - GPU utilization (if available)
   - Model memory consumption

4. **Model Analytics**:
   - Most used models (by request count)
   - Model performance comparison
   - Model loading/unloading events
   - Model size distribution

5. **Error Analysis**:
   - Error rate by model
   - Timeout and failure tracking
   - API response codes distribution
   - Performance degradation alerts

### Testing Commands
```bash
# Test Ollama exporter
curl http://SERVER_IP:9619/metrics

# Test Ollama API
curl http://SERVER_IP:11434/api/version

# Test model inference
curl http://SERVER_IP:11434/api/generate -d '{
  "model": "llama3.1:8b",
  "prompt": "Hello world",
  "stream": false
}'

# Check available models
curl http://SERVER_IP:11434/api/tags

# Check running models
curl http://SERVER_IP:11434/api/ps

# Monitor resource usage
docker stats ollama
```

## Success Metrics
- Ollama exporter running and exposing metrics
- Prometheus successfully scraping Ollama metrics
- Grafana dashboard displaying AI performance data
- Alerts firing for service and performance issues
- Resource monitoring working correctly

## Dependencies
- Completed: "Add Core Monitoring Stack (Foundation)"
- Ollama running with models downloaded
- Python environment for custom exporter
- Optional: NVIDIA drivers for GPU monitoring

## Risk Considerations
- Inference testing may impact production workloads
- Large model downloads affecting disk space
- Resource monitoring overhead
- GPU metrics requiring additional dependencies

## Documentation to Update
- Add Ollama monitoring section to README.md
- Document AI performance optimization tips
- Include model management best practices
- Add GPU monitoring setup instructions