# Implement n8n Workflow Monitoring

## Priority: 2 (High)
## Estimated Time: 4-5 hours
## Phase: Week 2 - Service-Specific Monitoring

## Description
Implement comprehensive monitoring for n8n workflow automation including execution success/failure rates, workflow performance metrics, error tracking, and webhook monitoring.

## Acceptance Criteria
- [ ] n8n workflow execution metrics exported to Prometheus
- [ ] Success/failure rate tracking for all workflows
- [ ] Workflow execution duration monitoring
- [ ] Error tracking and categorization
- [ ] Webhook endpoint health monitoring
- [ ] Custom n8n dashboard in Grafana
- [ ] Alerts for workflow failures and performance degradation
- [ ] Queue depth and processing backlog monitoring

## Technical Implementation Details

### Files to Create/Modify
1. `monitoring/exporters/n8n-exporter.js` - Custom n8n metrics exporter
2. `monitoring/grafana/dashboards/n8n-workflows.json` - n8n-specific dashboard
3. `monitoring/prometheus/prometheus.yml` - Add n8n scrape config
4. `monitoring/prometheus/alert_rules.yml` - Add n8n-specific alerts
5. `docker-compose.monitoring.yml` - Add n8n exporter service
6. `monitoring/config/n8n-webhook-monitor.yml` - Webhook monitoring config

### n8n Metrics to Monitor
1. **Workflow Execution**:
   - Total workflow executions
   - Success/failure rates per workflow
   - Execution duration percentiles
   - Active vs manual executions

2. **Error Tracking**:
   - Error count by workflow
   - Error categorization (timeout, API error, data error)
   - Failed node tracking
   - Retry attempt counts

3. **Performance Metrics**:
   - Queue processing time
   - Webhook response times
   - Database query performance
   - Memory usage per execution

4. **System Health**:
   - n8n service availability
   - Database connectivity
   - External API health checks
   - License and version information

### Custom n8n Exporter (`monitoring/exporters/n8n-exporter.js`)
```javascript
#!/usr/bin/env node

/**
 * n8n Prometheus Exporter
 * Exports metrics from n8n database and API to Prometheus format
 */

const express = require('express');
const client = require('prom-client');
const axios = require('axios');
const sqlite3 = require('sqlite3').verbose();
const path = require('path');

// Configuration
const PORT = process.env.EXPORTER_PORT || 9618;
const N8N_URL = process.env.N8N_URL || 'https://n8n:5678';
const N8N_USER = process.env.N8N_USER || 'admin';
const N8N_PASS = process.env.N8N_PASS || 'password';
const DB_PATH = process.env.N8N_DB_PATH || '/data/database.sqlite';

// Prometheus metrics
const register = new client.Register();

const workflowExecutions = new client.Counter({
  name: 'n8n_workflow_executions_total',
  help: 'Total number of workflow executions',
  labelNames: ['workflow_id', 'workflow_name', 'status', 'mode'],
  registers: [register]
});

const workflowDuration = new client.Histogram({
  name: 'n8n_workflow_duration_seconds',
  help: 'Workflow execution duration in seconds',
  labelNames: ['workflow_id', 'workflow_name'],
  buckets: [0.1, 0.5, 1, 2, 5, 10, 30, 60, 300, 600],
  registers: [register]
});

const workflowErrors = new client.Counter({
  name: 'n8n_workflow_errors_total',
  help: 'Total number of workflow errors',
  labelNames: ['workflow_id', 'workflow_name', 'error_type'],
  registers: [register]
});

const webhookRequests = new client.Counter({
  name: 'n8n_webhook_requests_total',
  help: 'Total number of webhook requests',
  labelNames: ['workflow_id', 'method', 'status_code'],
  registers: [register]
});

const activeExecutions = new client.Gauge({
  name: 'n8n_active_executions',
  help: 'Number of currently active executions',
  registers: [register]
});

const queuedExecutions = new client.Gauge({
  name: 'n8n_queued_executions',
  help: 'Number of queued executions waiting to run',
  registers: [register]
});

class N8nExporter {
  constructor() {
    this.app = express();
    this.db = null;
    this.lastExecutionId = 0;
    this.setupRoutes();
    this.connectDatabase();
  }

  setupRoutes() {
    this.app.get('/metrics', async (req, res) => {
      try {
        await this.collectMetrics();
        res.set('Content-Type', register.contentType);
        res.end(await register.metrics());
      } catch (error) {
        console.error('Error collecting metrics:', error);
        res.status(500).end('Error collecting metrics');
      }
    });

    this.app.get('/health', (req, res) => {
      res.json({ status: 'healthy', timestamp: new Date().toISOString() });
    });
  }

  connectDatabase() {
    this.db = new sqlite3.Database(DB_PATH, sqlite3.OPEN_READONLY, (err) => {
      if (err) {
        console.error('Error connecting to n8n database:', err);
      } else {
        console.log('Connected to n8n database');
        this.initializeLastExecutionId();
      }
    });
  }

  initializeLastExecutionId() {
    const query = 'SELECT MAX(id) as max_id FROM execution_entity';
    this.db.get(query, (err, row) => {
      if (!err && row) {
        this.lastExecutionId = row.max_id || 0;
        console.log(`Initialized last execution ID: ${this.lastExecutionId}`);
      }
    });
  }

  async collectMetrics() {
    if (!this.db) {
      throw new Error('Database not connected');
    }

    await Promise.all([
      this.collectExecutionMetrics(),
      this.collectWorkflowStats(),
      this.collectSystemMetrics()
    ]);
  }

  collectExecutionMetrics() {
    return new Promise((resolve, reject) => {
      const query = `
        SELECT
          e.id,
          e.workflowId,
          w.name as workflowName,
          e.finished,
          e.mode,
          e.startedAt,
          e.stoppedAt,
          e.workflowData
        FROM execution_entity e
        LEFT JOIN workflow_entity w ON e.workflowId = w.id
        WHERE e.id > ?
        ORDER BY e.id
      `;

      this.db.all(query, [this.lastExecutionId], (err, rows) => {
        if (err) {
          reject(err);
          return;
        }

        rows.forEach(execution => {
          const workflowId = execution.workflowId || 'unknown';
          const workflowName = execution.workflowName || 'unknown';
          const status = execution.finished ? 'success' : 'running';
          const mode = execution.mode || 'unknown';

          // Update execution counter
          workflowExecutions.labels(workflowId, workflowName, status, mode).inc();

          // Calculate duration if execution is finished
          if (execution.finished && execution.startedAt && execution.stoppedAt) {
            const duration = (new Date(execution.stoppedAt) - new Date(execution.startedAt)) / 1000;
            workflowDuration.labels(workflowId, workflowName).observe(duration);
          }

          // Update last execution ID
          if (execution.id > this.lastExecutionId) {
            this.lastExecutionId = execution.id;
          }
        });

        resolve();
      });
    });
  }

  collectWorkflowStats() {
    return new Promise((resolve, reject) => {
      // Count active executions
      const activeQuery = `
        SELECT COUNT(*) as count
        FROM execution_entity
        WHERE finished = false AND stoppedAt IS NULL
      `;

      this.db.get(activeQuery, (err, row) => {
        if (!err && row) {
          activeExecutions.set(row.count || 0);
        }
        resolve();
      });
    });
  }

  async collectSystemMetrics() {
    try {
      // Check n8n health endpoint
      const healthResponse = await axios.get(`${N8N_URL}/healthz`, {
        timeout: 5000,
        httpsAgent: new (require('https').Agent)({
          rejectUnauthorized: false
        })
      });

      // Could add more system metrics here
      console.log('n8n health check successful');
    } catch (error) {
      console.error('n8n health check failed:', error.message);
    }
  }

  start() {
    this.app.listen(PORT, () => {
      console.log(`n8n exporter listening on port ${PORT}`);
    });

    // Periodic metric collection
    setInterval(() => {
      this.collectMetrics().catch(console.error);
    }, 30000); // Every 30 seconds
  }
}

// Start the exporter
if (require.main === module) {
  const exporter = new N8nExporter();
  exporter.start();
}

module.exports = N8nExporter;
```

### Docker Service for n8n Exporter
Add to `docker-compose.monitoring.yml`:
```yaml
  n8n-exporter:
    build:
      context: ./monitoring/exporters
      dockerfile: Dockerfile.n8n
    container_name: n8n-exporter
    restart: unless-stopped
    environment:
      - N8N_URL=https://n8n:5678
      - N8N_USER=${N8N_USER}
      - N8N_PASS=${N8N_PASSWORD}
      - N8N_DB_PATH=/data/database.sqlite
      - EXPORTER_PORT=9618
    ports:
      - "9618:9618"
    volumes:
      - ./data/n8n:/data:ro
    networks:
      - homeserver
    depends_on:
      - n8n
```

### Dockerfile for n8n Exporter (`monitoring/exporters/Dockerfile.n8n`)
```dockerfile
FROM node:18-alpine

WORKDIR /app

RUN npm install express prom-client axios sqlite3

COPY n8n-exporter.js .

EXPOSE 9618

CMD ["node", "n8n-exporter.js"]
```

### Prometheus Scrape Configuration
Add to `monitoring/prometheus/prometheus.yml`:
```yaml
  - job_name: 'n8n-exporter'
    static_configs:
      - targets: ['n8n-exporter:9618']
    scrape_interval: 30s

  - job_name: 'n8n-webhooks'
    static_configs:
      - targets: ['n8n:5678']
    metrics_path: '/webhook-test/healthz'
    scheme: https
    tls_config:
      insecure_skip_verify: true
    scrape_interval: 60s
```

### n8n-Specific Alert Rules
Add to `monitoring/prometheus/alert_rules.yml`:
```yaml
  - name: n8n-alerts
    rules:
      - alert: N8nDown
        expr: up{job="n8n-exporter"} == 0
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "n8n exporter is down"
          description: "n8n workflow monitoring is not responding"

      - alert: N8nWorkflowFailureRate
        expr: (rate(n8n_workflow_executions_total{status="error"}[10m]) / rate(n8n_workflow_executions_total[10m])) > 0.1
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High n8n workflow failure rate"
          description: "{{ $value | humanizePercentage }} of workflows are failing in the last 10 minutes"

      - alert: N8nWorkflowStuck
        expr: n8n_active_executions > 10
        for: 30m
        labels:
          severity: warning
        annotations:
          summary: "n8n workflows appear stuck"
          description: "{{ $value }} workflows have been running for more than 30 minutes"

      - alert: N8nWorkflowSlow
        expr: histogram_quantile(0.95, rate(n8n_workflow_duration_seconds_bucket[10m])) > 300
        for: 15m
        labels:
          severity: warning
        annotations:
          summary: "n8n workflows running slowly"
          description: "95th percentile workflow execution time is {{ $value }}s"

      - alert: N8nNoExecutions
        expr: rate(n8n_workflow_executions_total[1h]) == 0
        for: 2h
        labels:
          severity: warning
        annotations:
          summary: "No n8n workflow executions detected"
          description: "No workflow executions have been recorded in the last hour"

      - alert: N8nHighErrorRate
        expr: rate(n8n_workflow_errors_total[5m]) > 1
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "High n8n error rate"
          description: "n8n is generating {{ $value }} errors per second"
```

### Grafana Dashboard Panels
Key panels for n8n dashboard:

1. **Execution Overview**:
   - Total executions in last 24h
   - Success rate percentage
   - Active executions count
   - Average execution duration

2. **Workflow Performance**:
   - Executions per minute time series
   - Execution duration histogram
   - Success/failure rate by workflow
   - Top slowest workflows

3. **Error Analysis**:
   - Error rate over time
   - Errors by workflow (table)
   - Error type distribution
   - Failed node analysis

4. **System Health**:
   - n8n service uptime
   - Webhook response times
   - Database query performance
   - Memory usage trends

5. **Workflow Details**:
   - Individual workflow statistics
   - Execution history timeline
   - Queue depth monitoring
   - Manual vs automatic executions

### Webhook Health Monitoring
Create a simple health check workflow in n8n:
```json
{
  "name": "Health Check",
  "nodes": [
    {
      "name": "Webhook",
      "type": "n8n-nodes-base.webhook",
      "parameters": {
        "httpMethod": "GET",
        "path": "healthz"
      }
    },
    {
      "name": "Respond",
      "type": "n8n-nodes-base.respondToWebhook",
      "parameters": {
        "responseBody": "{\"status\": \"healthy\", \"timestamp\": \"{{ new Date().toISOString() }}\"}"
      }
    }
  ]
}
```

### Testing Commands
```bash
# Test n8n exporter
curl http://SERVER_IP:9618/metrics

# Test n8n health endpoint
curl -k https://SERVER_IP:5678/webhook-test/healthz

# Trigger test workflow
curl -k -X POST https://SERVER_IP:5678/webhook/test

# Check database connectivity
docker exec n8n-exporter ls -la /data/

# View Prometheus targets
curl http://SERVER_IP:9090/api/v1/targets | grep n8n
```

## Success Metrics
- n8n exporter running and exposing metrics
- Prometheus successfully scraping n8n metrics
- Grafana dashboard displaying workflow statistics
- Alerts firing for workflow failures
- Database connectivity working correctly

## Dependencies
- Completed: "Add Core Monitoring Stack (Foundation)"
- n8n running and accessible
- Access to n8n database file
- Node.js environment for custom exporter

## Risk Considerations
- Database lock issues affecting monitoring
- Large execution history impacting performance
- Webhook monitoring affecting workflow performance
- Privacy concerns with execution data

## Documentation to Update
- Add n8n monitoring section to README.md
- Document workflow performance optimization
- Include troubleshooting guide for stuck workflows
- Add webhook monitoring setup instructions