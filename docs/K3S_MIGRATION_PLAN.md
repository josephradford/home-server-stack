# k3s Migration Plan

**Migration Goal**: Transition the home-server-stack from Docker Compose to k3s across two servers while maintaining VPN-first security strategy.

**Timeline**: 2-3 weekends (15-19 hours total)
**Servers**: 2x servers on same LAN
**Strategy**: Gradual migration with rollback points

---

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Architecture Overview](#architecture-overview)
3. [Phase 1: k3s Cluster Installation](#phase-1-k3s-cluster-installation)
4. [Phase 2: Deploy Monitoring Stack](#phase-2-deploy-monitoring-stack)
5. [Phase 3: Migrate Services](#phase-3-migrate-services)
6. [Phase 4: Networking & Ingress](#phase-4-networking--ingress)
7. [Phase 5: Cleanup & Optimization](#phase-5-cleanup--optimization)
8. [Rollback Procedures](#rollback-procedures)
9. [Helper Scripts](#helper-scripts)
10. [Troubleshooting](#troubleshooting)

---

## Prerequisites

### Hardware Requirements (Per Server)
- **CPU**: 2+ cores
- **RAM**: 4GB minimum (8GB recommended with monitoring)
- **Disk**: 50GB+ available
- **Network**: Same LAN, static IPs recommended

### Software Prerequisites
```bash
# Install on both servers
curl -sfL https://get.k3s.io | sh -

# Verify installation
sudo systemctl status k3s        # Server 1 (control plane)
sudo systemctl status k3s-agent  # Server 2 (worker)
```

### Pre-Migration Checklist
- [ ] Docker Compose stack running and healthy
- [ ] Backups of all data volumes (`./data/*`)
- [ ] `.env` file backed up
- [ ] SSL certificates backed up (`./ssl/*`)
- [ ] WireGuard configs backed up (`./data/wireguard/*`)
- [ ] Test server access via SSH
- [ ] Document current service URLs and ports

---

## Architecture Overview

### Current Docker Compose Architecture
```
homeserver network (bridge)
├── adguard (DNS/DHCP)
├── n8n (automation)
├── ollama (AI models)
├── wireguard (VPN)
└── monitoring stack (optional)
    ├── prometheus
    ├── grafana
    ├── alertmanager
    ├── node-exporter
    └── cadvisor
```

### Target k3s Architecture
```
k3s Cluster
├── Server 1 (control-plane + worker)
│   ├── adguard (DNS - DaemonSet or affinity)
│   ├── wireguard (VPN - DaemonSet)
│   └── monitoring stack
└── Server 2 (worker)
    ├── ollama (AI - high resource)
    ├── n8n (automation)
    └── monitoring agents
```

### Network Strategy
- **Pod Network**: 10.42.0.0/16 (k3s default)
- **Service Network**: 10.43.0.0/16 (k3s default)
- **WireGuard VPN**: 10.13.13.0/24
- **MetalLB Pool**: 192.168.1.240-192.168.1.250 (adjust to your LAN)
- **Ingress Strategy**: NGINX Ingress with IP whitelisting for VPN-first

### Storage Strategy
- **Default**: local-path-provisioner (bundled with k3s)
- **Path**: `/var/lib/rancher/k3s/storage/`
- **Backup**: Standard filesystem backup of PVCs

---

## Phase 1: k3s Cluster Installation

**Time**: 2 hours
**Risk**: Low (Docker Compose still running)

### 1.1 Install k3s on Server 1 (Control Plane)

```bash
# SSH into Server 1
ssh user@<SERVER_1_IP>

# Install k3s with embedded etcd (single control plane)
curl -sfL https://get.k3s.io | sh -s - server \
  --disable traefik \
  --disable servicelb \
  --write-kubeconfig-mode 644 \
  --node-name server1 \
  --cluster-cidr 10.42.0.0/16 \
  --service-cidr 10.43.0.0/16

# Get node token for Server 2
sudo cat /var/lib/rancher/k3s/server/node-token
# Save this token - you'll need it for Server 2

# Verify k3s is running
sudo systemctl status k3s
kubectl get nodes
```

**Expected Output**:
```
NAME      STATUS   ROLES                  AGE   VERSION
server1   Ready    control-plane,master   30s   v1.28.x+k3s1
```

### 1.2 Install k3s on Server 2 (Worker)

```bash
# SSH into Server 2
ssh user@<SERVER_2_IP>

# Install k3s agent (replace with actual token from Server 1)
curl -sfL https://get.k3s.io | K3S_URL=https://<SERVER_1_IP>:6443 \
  K3S_TOKEN=<NODE_TOKEN_FROM_SERVER_1> \
  sh -s - agent \
  --node-name server2

# Verify agent is running
sudo systemctl status k3s-agent
```

### 1.3 Verify Cluster from Server 1

```bash
# SSH back to Server 1
ssh user@<SERVER_1_IP>

# Check cluster status
kubectl get nodes
kubectl get pods -A

# Label nodes for workload placement
kubectl label node server1 homeserver.local/role=infrastructure
kubectl label node server2 homeserver.local/role=compute
```

**Expected Output**:
```
NAME      STATUS   ROLES                  AGE     VERSION
server1   Ready    control-plane,master   5m      v1.28.x+k3s1
server2   Ready    <none>                 2m      v1.28.x+k3s1
```

### 1.4 Create Namespaces

```bash
# Create namespace structure
kubectl create namespace homeserver
kubectl create namespace monitoring
kubectl create namespace ingress-nginx

# Set default namespace (optional)
kubectl config set-context --current --namespace=homeserver
```

### 1.5 Setup kubectl on Local Machine (Optional)

```bash
# On Server 1, copy kubeconfig
sudo cat /etc/rancher/k3s/k3s.yaml

# On your local machine
mkdir -p ~/.kube
# Paste the content, replace 127.0.0.1 with <SERVER_1_IP>
vim ~/.kube/config

# Test connection
kubectl get nodes
```

**Validation**:
- [ ] Both nodes in Ready state
- [ ] All system pods running (`kubectl get pods -A`)
- [ ] Namespaces created
- [ ] kubectl working from control plane

---

## Phase 2: Deploy Monitoring Stack

**Time**: 2-3 hours
**Risk**: Low (existing monitoring still runs in Docker)

### 2.1 Install Helm

```bash
# On Server 1
curl https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash

# Verify
helm version
```

### 2.2 Deploy kube-prometheus-stack

```bash
# Add Prometheus Community Helm repo
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo update

# Create values file for customization
cat > ~/monitoring-values.yaml <<'EOF'
# kube-prometheus-stack values
prometheus:
  prometheusSpec:
    retention: 30d
    storageSpec:
      volumeClaimTemplate:
        spec:
          accessModes: ["ReadWriteOnce"]
          resources:
            requests:
              storage: 20Gi
    # VPN-first: Only accessible from VPN or LAN
    externalUrl: http://prometheus.homeserver.local

grafana:
  enabled: true
  adminPassword: <GRAFANA_PASSWORD>
  persistence:
    enabled: true
    size: 5Gi
  grafana.ini:
    server:
      root_url: http://grafana.homeserver.local
    security:
      admin_user: admin
      admin_password: <GRAFANA_PASSWORD>

alertmanager:
  alertmanagerSpec:
    retention: 168h
    storage:
      volumeClaimTemplate:
        spec:
          accessModes: ["ReadWriteOnce"]
          resources:
            requests:
              storage: 5Gi
    externalUrl: http://alertmanager.homeserver.local

# Enable node-exporter on all nodes
nodeExporter:
  enabled: true

# Disable default ingress (we'll use our own)
prometheus:
  ingress:
    enabled: false
grafana:
  ingress:
    enabled: false
alertmanager:
  ingress:
    enabled: false
EOF

# Install the stack
helm install kube-prometheus-stack prometheus-community/kube-prometheus-stack \
  --namespace monitoring \
  --values ~/monitoring-values.yaml \
  --version 55.0.0

# Wait for pods to be ready
kubectl wait --for=condition=ready pod -l app.kubernetes.io/name=kube-prometheus-stack -n monitoring --timeout=300s
```

### 2.3 Migrate Existing Alert Rules

Create PrometheusRule CRD from your existing `monitoring/prometheus/alert_rules.yml`:

```bash
cat > ~/alert-rules-migrated.yaml <<'EOF'
apiVersion: monitoring.coreos.com/v1
kind: PrometheusRule
metadata:
  name: homeserver-alerts
  namespace: monitoring
  labels:
    prometheus: kube-prometheus-stack-prometheus
    role: alert-rules
spec:
  groups:
    # Critical Alerts
    - name: critical-alerts
      interval: 30s
      rules:
        - alert: HighCPUUsage
          expr: 100 - (avg(rate(node_cpu_seconds_total{mode="idle"}[5m])) * 100) > 85
          for: 5m
          labels:
            severity: critical
            category: resource
          annotations:
            summary: "High CPU usage detected on {{ $labels.instance }}"
            description: "CPU usage is {{ $value | humanize }}% (threshold: 85%)"

        - alert: HighMemoryUsage
          expr: (1 - (node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes)) * 100 > 90
          for: 5m
          labels:
            severity: critical
            category: resource
          annotations:
            summary: "High memory usage detected on {{ $labels.instance }}"
            description: "Memory usage is {{ $value | humanize }}% (threshold: 90%)"

        - alert: DiskSpaceLow
          expr: (1 - (node_filesystem_avail_bytes{mountpoint="/"} / node_filesystem_size_bytes{mountpoint="/"})) * 100 > 85
          for: 5m
          labels:
            severity: warning
            category: resource
          annotations:
            summary: "Low disk space on {{ $labels.instance }}"
            description: "Disk usage is {{ $value | humanize }}% (threshold: 85%)"

        - alert: ContainerDown
          expr: up{job=~"adguard|n8n|ollama|wireguard"} == 0
          for: 1m
          labels:
            severity: critical
            category: availability
          annotations:
            summary: "Service {{ $labels.job }} is down"
            description: "Container has been down for more than 1 minute"

    # Service-Specific Alerts
    - name: service-specific-alerts
      interval: 30s
      rules:
        - alert: OllamaHighMemoryUsage
          expr: container_memory_usage_bytes{name="ollama"} / container_spec_memory_limit_bytes{name="ollama"} * 100 > 90
          for: 5m
          labels:
            severity: warning
            category: service
            service: ollama
          annotations:
            summary: "Ollama using high memory"
            description: "Ollama memory usage: {{ $value | humanize }}%"

        - alert: N8NHighRestartRate
          expr: rate(kube_pod_container_status_restarts_total{pod=~"n8n.*"}[15m]) > 0.1
          for: 5m
          labels:
            severity: warning
            category: service
            service: n8n
          annotations:
            summary: "n8n restarting frequently"
            description: "n8n has restarted {{ $value }} times in 15 minutes"

        - alert: AdGuardDNSFailures
          expr: rate(adguard_dns_queries_total{status="failed"}[5m]) > 10
          for: 2m
          labels:
            severity: critical
            category: service
            service: adguard
          annotations:
            summary: "AdGuard DNS experiencing failures"
            description: "DNS failure rate: {{ $value | humanize }} queries/sec"

    # Resource Alerts
    - name: resource-alerts
      interval: 60s
      rules:
        - alert: HighDiskIO
          expr: rate(node_disk_io_time_seconds_total[5m]) > 0.8
          for: 5m
          labels:
            severity: warning
            category: resource
          annotations:
            summary: "High disk I/O on {{ $labels.instance }}"
            description: "Disk I/O utilization: {{ $value | humanize }}"

        - alert: HighNetworkTraffic
          expr: rate(node_network_receive_bytes_total[5m]) > 100000000
          for: 5m
          labels:
            severity: info
            category: resource
          annotations:
            summary: "High network traffic on {{ $labels.instance }}"
            description: "Receiving {{ $value | humanize }}B/s"
EOF

# Apply the alert rules
kubectl apply -f ~/alert-rules-migrated.yaml

# Verify rules are loaded
kubectl get prometheusrule -n monitoring
```

### 2.4 Configure AlertManager

Create AlertManager configuration:

```bash
cat > ~/alertmanager-config.yaml <<'EOF'
apiVersion: v1
kind: Secret
metadata:
  name: alertmanager-kube-prometheus-stack-alertmanager
  namespace: monitoring
type: Opaque
stringData:
  alertmanager.yaml: |
    global:
      resolve_timeout: 5m

    route:
      receiver: 'webhook-default'
      group_by: ['alertname', 'severity', 'category']
      group_wait: 10s
      group_interval: 5m
      repeat_interval: 4h
      routes:
        - match:
            severity: critical
          receiver: 'webhook-critical'
          repeat_interval: 5m
        - match:
            severity: warning
          receiver: 'webhook-default'
          repeat_interval: 30m

    inhibit_rules:
      - source_match:
          severity: 'critical'
        target_match:
          severity: 'warning'
        equal: ['alertname', 'instance']

    receivers:
      - name: 'webhook-default'
        webhook_configs:
          - url: 'http://127.0.0.1:5001/alerts'
            send_resolved: true

      - name: 'webhook-critical'
        webhook_configs:
          - url: 'http://127.0.0.1:5001/alerts'
            send_resolved: true
        # Optional: Add email for critical alerts
        # email_configs:
        #   - to: 'admin@yourdomain.com'
        #     from: 'alerts@yourdomain.com'
        #     smarthost: 'smtp.gmail.com:587'
        #     auth_username: '<EMAIL_USER>'
        #     auth_password: '<EMAIL_PASS>'
EOF

# Apply the configuration
kubectl apply -f ~/alertmanager-config.yaml

# Restart AlertManager to pick up config
kubectl rollout restart statefulset alertmanager-kube-prometheus-stack-alertmanager -n monitoring
```

### 2.5 Access Monitoring UIs

```bash
# Port-forward to access dashboards (temporary)
kubectl port-forward -n monitoring svc/kube-prometheus-stack-prometheus 9090:9090 &
kubectl port-forward -n monitoring svc/kube-prometheus-stack-grafana 3000:80 &
kubectl port-forward -n monitoring svc/kube-prometheus-stack-alertmanager 9093:9093 &

# Access at:
# Prometheus: http://localhost:9090
# Grafana: http://localhost:3000 (admin/<GRAFANA_PASSWORD>)
# AlertManager: http://localhost:9093
```

**Validation**:
- [ ] All monitoring pods running
- [ ] Prometheus targets showing up
- [ ] Grafana accessible with dashboards
- [ ] Alert rules loaded in Prometheus
- [ ] AlertManager configuration valid

---

## Phase 3: Migrate Services

**Time**: 6-8 hours
**Risk**: Medium (services will have brief downtime)

### 3.1 Test Migration with Simple Service (nginx)

```bash
# Create test deployment
cat > ~/test-nginx.yaml <<'EOF'
apiVersion: apps/v1
kind: Deployment
metadata:
  name: nginx-test
  namespace: homeserver
spec:
  replicas: 1
  selector:
    matchLabels:
      app: nginx-test
  template:
    metadata:
      labels:
        app: nginx-test
    spec:
      containers:
      - name: nginx
        image: nginx:1.25-alpine
        ports:
        - containerPort: 80
---
apiVersion: v1
kind: Service
metadata:
  name: nginx-test
  namespace: homeserver
spec:
  selector:
    app: nginx-test
  ports:
  - port: 80
    targetPort: 80
  type: ClusterIP
EOF

kubectl apply -f ~/test-nginx.yaml

# Test
kubectl get pods -n homeserver
kubectl port-forward -n homeserver svc/nginx-test 8080:80
curl http://localhost:8080

# Cleanup
kubectl delete -f ~/test-nginx.yaml
```

### 3.2 Migrate Ollama (High Resource Service)

**Strategy**: Pin to Server 2 (compute node), migrate data volume

```bash
# Step 1: Stop Docker Compose Ollama (on Server 1)
cd /path/to/home-server-stack
docker compose stop ollama
docker compose rm -f ollama

# Step 2: Copy Ollama data to Server 2
# From Server 1:
ssh user@<SERVER_2_IP> "sudo mkdir -p /var/lib/rancher/k3s/storage/ollama-data"
sudo rsync -avz --progress ./data/ollama/ user@<SERVER_2_IP>:/tmp/ollama-data/
ssh user@<SERVER_2_IP> "sudo mv /tmp/ollama-data/* /var/lib/rancher/k3s/storage/ollama-data/ && sudo chown -R 1000:1000 /var/lib/rancher/k3s/storage/ollama-data"

# Step 3: Create Ollama deployment (from Server 1)
cat > ~/ollama-deployment.yaml <<'EOF'
apiVersion: v1
kind: PersistentVolume
metadata:
  name: ollama-pv
spec:
  capacity:
    storage: 50Gi
  accessModes:
    - ReadWriteOnce
  persistentVolumeReclaimPolicy: Retain
  storageClassName: local-path
  local:
    path: /var/lib/rancher/k3s/storage/ollama-data
  nodeAffinity:
    required:
      nodeSelectorTerms:
      - matchExpressions:
        - key: kubernetes.io/hostname
          operator: In
          values:
          - server2
---
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: ollama-pvc
  namespace: homeserver
spec:
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      storage: 50Gi
  storageClassName: local-path
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: ollama
  namespace: homeserver
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
      nodeSelector:
        homeserver.local/role: compute
      containers:
      - name: ollama
        image: ollama/ollama:0.1.23@sha256:your-digest-here
        ports:
        - containerPort: 11434
          name: http
        env:
        - name: OLLAMA_HOST
          value: "0.0.0.0"
        - name: OLLAMA_NUM_PARALLEL
          value: "1"
        - name: OLLAMA_MAX_LOADED_MODELS
          value: "1"
        - name: OLLAMA_LOAD_TIMEOUT
          value: "600"
        volumeMounts:
        - name: ollama-data
          mountPath: /root/.ollama
        resources:
          requests:
            memory: "4Gi"
            cpu: "1000m"
          limits:
            memory: "8Gi"
            cpu: "4000m"
      volumes:
      - name: ollama-data
        persistentVolumeClaim:
          claimName: ollama-pvc
---
apiVersion: v1
kind: Service
metadata:
  name: ollama
  namespace: homeserver
spec:
  selector:
    app: ollama
  ports:
  - port: 11434
    targetPort: 11434
  type: ClusterIP
EOF

kubectl apply -f ~/ollama-deployment.yaml

# Step 4: Verify
kubectl get pods -n homeserver -l app=ollama
kubectl logs -n homeserver -l app=ollama --tail=50

# Step 5: Test Ollama API
kubectl exec -n homeserver deploy/ollama -- curl -s http://localhost:11434/api/version
```

### 3.3 Migrate n8n (Automation with SSL)

**Strategy**: Migrate data + SSL certs, maintain external webhook access

```bash
# Step 1: Stop Docker Compose n8n
docker compose stop n8n n8n-init
docker compose rm -f n8n n8n-init

# Step 2: Copy n8n data and SSL certs
sudo rsync -avz --progress ./data/n8n/ user@<SERVER_1_IP>:/tmp/n8n-data/
sudo rsync -avz --progress ./ssl/ user@<SERVER_1_IP>:/tmp/n8n-ssl/

ssh user@<SERVER_1_IP> "sudo mkdir -p /var/lib/rancher/k3s/storage/n8n-data /var/lib/rancher/k3s/storage/n8n-ssl"
ssh user@<SERVER_1_IP> "sudo mv /tmp/n8n-data/* /var/lib/rancher/k3s/storage/n8n-data/ && sudo chown -R 1000:1000 /var/lib/rancher/k3s/storage/n8n-data"
ssh user@<SERVER_1_IP> "sudo mv /tmp/n8n-ssl/* /var/lib/rancher/k3s/storage/n8n-ssl/ && sudo chmod 644 /var/lib/rancher/k3s/storage/n8n-ssl/*"

# Step 3: Create n8n secrets and deployment
cat > ~/n8n-deployment.yaml <<'EOF'
apiVersion: v1
kind: Secret
metadata:
  name: n8n-secrets
  namespace: homeserver
type: Opaque
stringData:
  N8N_USER: "admin"
  N8N_PASSWORD: "<N8N_PASSWORD>"
---
apiVersion: v1
kind: PersistentVolume
metadata:
  name: n8n-data-pv
spec:
  capacity:
    storage: 10Gi
  accessModes:
    - ReadWriteOnce
  persistentVolumeReclaimPolicy: Retain
  storageClassName: local-path
  local:
    path: /var/lib/rancher/k3s/storage/n8n-data
  nodeAffinity:
    required:
      nodeSelectorTerms:
      - matchExpressions:
        - key: kubernetes.io/hostname
          operator: In
          values:
          - server1
---
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: n8n-data-pvc
  namespace: homeserver
spec:
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      storage: 10Gi
  storageClassName: local-path
---
apiVersion: v1
kind: PersistentVolume
metadata:
  name: n8n-ssl-pv
spec:
  capacity:
    storage: 1Gi
  accessModes:
    - ReadOnlyMany
  persistentVolumeReclaimPolicy: Retain
  storageClassName: local-path
  local:
    path: /var/lib/rancher/k3s/storage/n8n-ssl
  nodeAffinity:
    required:
      nodeSelectorTerms:
      - matchExpressions:
        - key: kubernetes.io/hostname
          operator: In
          values:
          - server1
---
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: n8n-ssl-pvc
  namespace: homeserver
spec:
  accessModes:
    - ReadOnlyMany
  resources:
    requests:
      storage: 1Gi
  storageClassName: local-path
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: n8n
  namespace: homeserver
spec:
  replicas: 1
  selector:
    matchLabels:
      app: n8n
  template:
    metadata:
      labels:
        app: n8n
    spec:
      securityContext:
        fsGroup: 1000
      containers:
      - name: n8n
        image: n8nio/n8n:1.19.4@sha256:your-digest-here
        ports:
        - containerPort: 5678
          name: https
        env:
        - name: N8N_BASIC_AUTH_ACTIVE
          value: "true"
        - name: N8N_BASIC_AUTH_USER
          valueFrom:
            secretKeyRef:
              name: n8n-secrets
              key: N8N_USER
        - name: N8N_BASIC_AUTH_PASSWORD
          valueFrom:
            secretKeyRef:
              name: n8n-secrets
              key: N8N_PASSWORD
        - name: N8N_HOST
          value: "0.0.0.0"
        - name: N8N_PORT
          value: "5678"
        - name: N8N_PROTOCOL
          value: "https"
        - name: N8N_SSL_KEY
          value: "/ssl/server.key"
        - name: N8N_SSL_CERT
          value: "/ssl/server.crt"
        - name: WEBHOOK_URL
          value: "https://<YOUR_DOMAIN>:5678/"
        - name: N8N_EDITOR_BASE_URL
          value: "https://<YOUR_DOMAIN>:5678"
        - name: GENERIC_TIMEZONE
          value: "UTC"
        - name: N8N_SECURE_COOKIE
          value: "true"
        - name: N8N_RUNNERS_ENABLED
          value: "true"
        - name: N8N_BLOCK_ENV_ACCESS_IN_NODE
          value: "false"
        - name: N8N_ENFORCE_SETTINGS_FILE_PERMISSIONS
          value: "true"
        - name: N8N_RUNNERS_TASK_TIMEOUT
          value: "1800"
        - name: EXECUTIONS_TIMEOUT
          value: "1800"
        - name: EXECUTIONS_TIMEOUT_MAX
          value: "3600"
        volumeMounts:
        - name: n8n-data
          mountPath: /home/node/.n8n
        - name: n8n-ssl
          mountPath: /ssl
          readOnly: true
        resources:
          requests:
            memory: "512Mi"
            cpu: "250m"
          limits:
            memory: "2Gi"
            cpu: "1000m"
      volumes:
      - name: n8n-data
        persistentVolumeClaim:
          claimName: n8n-data-pvc
      - name: n8n-ssl
        persistentVolumeClaim:
          claimName: n8n-ssl-pvc
---
apiVersion: v1
kind: Service
metadata:
  name: n8n
  namespace: homeserver
spec:
  selector:
    app: n8n
  ports:
  - port: 5678
    targetPort: 5678
  type: ClusterIP
EOF

kubectl apply -f ~/n8n-deployment.yaml

# Step 4: Verify
kubectl get pods -n homeserver -l app=n8n
kubectl logs -n homeserver -l app=n8n --tail=50

# Step 5: Test n8n (via port-forward temporarily)
kubectl port-forward -n homeserver svc/n8n 5678:5678
# Access: https://localhost:5678
```

### 3.4 Migrate AdGuard Home (Critical DNS Service)

**Strategy**: Careful migration with DNS fallback plan

```bash
# Step 1: IMPORTANT - Setup DNS fallback BEFORE stopping AdGuard
# Update your router or /etc/resolv.conf to use 8.8.8.8 temporarily

# Step 2: Stop Docker Compose AdGuard
docker compose stop adguard
docker compose rm -f adguard

# Step 3: Copy AdGuard data
sudo rsync -avz --progress ./data/adguard/ user@<SERVER_1_IP>:/tmp/adguard-data/
ssh user@<SERVER_1_IP> "sudo mkdir -p /var/lib/rancher/k3s/storage/adguard-work /var/lib/rancher/k3s/storage/adguard-conf"
ssh user@<SERVER_1_IP> "sudo mv /tmp/adguard-data/work/* /var/lib/rancher/k3s/storage/adguard-work/"
ssh user@<SERVER_1_IP> "sudo mv /tmp/adguard-data/conf/* /var/lib/rancher/k3s/storage/adguard-conf/"

# Step 4: Create AdGuard deployment
cat > ~/adguard-deployment.yaml <<'EOF'
apiVersion: v1
kind: PersistentVolume
metadata:
  name: adguard-work-pv
spec:
  capacity:
    storage: 5Gi
  accessModes:
    - ReadWriteOnce
  persistentVolumeReclaimPolicy: Retain
  storageClassName: local-path
  local:
    path: /var/lib/rancher/k3s/storage/adguard-work
  nodeAffinity:
    required:
      nodeSelectorTerms:
      - matchExpressions:
        - key: kubernetes.io/hostname
          operator: In
          values:
          - server1
---
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: adguard-work-pvc
  namespace: homeserver
spec:
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      storage: 5Gi
  storageClassName: local-path
---
apiVersion: v1
kind: PersistentVolume
metadata:
  name: adguard-conf-pv
spec:
  capacity:
    storage: 1Gi
  accessModes:
    - ReadWriteOnce
  persistentVolumeReclaimPolicy: Retain
  storageClassName: local-path
  local:
    path: /var/lib/rancher/k3s/storage/adguard-conf
  nodeAffinity:
    required:
      nodeSelectorTerms:
      - matchExpressions:
        - key: kubernetes.io/hostname
          operator: In
          values:
          - server1
---
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: adguard-conf-pvc
  namespace: homeserver
spec:
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      storage: 1Gi
  storageClassName: local-path
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: adguard
  namespace: homeserver
spec:
  replicas: 1
  selector:
    matchLabels:
      app: adguard
  template:
    metadata:
      labels:
        app: adguard
    spec:
      # Pin to server1 for DNS stability
      nodeSelector:
        homeserver.local/role: infrastructure
      containers:
      - name: adguard
        image: adguard/adguardhome:v0.107.43@sha256:your-digest-here
        ports:
        - containerPort: 53
          name: dns-tcp
          protocol: TCP
        - containerPort: 53
          name: dns-udp
          protocol: UDP
        - containerPort: 80
          name: http
        - containerPort: 3000
          name: setup
        volumeMounts:
        - name: adguard-work
          mountPath: /opt/adguardhome/work
        - name: adguard-conf
          mountPath: /opt/adguardhome/conf
        resources:
          requests:
            memory: "256Mi"
            cpu: "100m"
          limits:
            memory: "512Mi"
            cpu: "500m"
      volumes:
      - name: adguard-work
        persistentVolumeClaim:
          claimName: adguard-work-pvc
      - name: adguard-conf
        persistentVolumeClaim:
          claimName: adguard-conf-pvc
---
apiVersion: v1
kind: Service
metadata:
  name: adguard
  namespace: homeserver
spec:
  selector:
    app: adguard
  ports:
  - port: 53
    targetPort: 53
    protocol: TCP
    name: dns-tcp
  - port: 53
    targetPort: 53
    protocol: UDP
    name: dns-udp
  - port: 80
    targetPort: 80
    name: http
  - port: 3000
    targetPort: 3000
    name: setup
  type: ClusterIP
EOF

kubectl apply -f ~/adguard-deployment.yaml

# Step 5: Verify and test
kubectl get pods -n homeserver -l app=adguard
kubectl logs -n homeserver -l app=adguard --tail=50

# Test DNS resolution
kubectl run -n homeserver dns-test --rm -it --image=busybox --restart=Never -- nslookup google.com <ADGUARD_POD_IP>

# Step 6: Update your DNS settings back to point to AdGuard IP
# (Will be done properly with LoadBalancer in Phase 4)
```

**Validation**:
- [ ] Ollama accessible and models present
- [ ] n8n accessible with existing workflows
- [ ] AdGuard DNS resolving queries
- [ ] All data migrated successfully

---

## Phase 4: Networking & Ingress

**Time**: 3-4 hours
**Risk**: Medium (network configuration changes)

### 4.1 Deploy MetalLB (LoadBalancer)

```bash
# Install MetalLB
kubectl apply -f https://raw.githubusercontent.com/metallb/metallb/v0.13.12/config/manifests/metallb-native.yaml

# Wait for pods
kubectl wait --namespace metallb-system \
  --for=condition=ready pod \
  --selector=app=metallb \
  --timeout=90s

# Configure IP pool (adjust to your network)
cat > ~/metallb-config.yaml <<'EOF'
apiVersion: metallb.io/v1beta1
kind: IPAddressPool
metadata:
  name: homeserver-pool
  namespace: metallb-system
spec:
  addresses:
  - 192.168.1.240-192.168.1.250  # ADJUST TO YOUR NETWORK
---
apiVersion: metallb.io/v1beta1
kind: L2Advertisement
metadata:
  name: homeserver-l2
  namespace: metallb-system
spec:
  ipAddressPools:
  - homeserver-pool
EOF

kubectl apply -f ~/metallb-config.yaml

# Verify
kubectl get ipaddresspool -n metallb-system
```

### 4.2 Expose Services with LoadBalancer

```bash
# Update AdGuard to use LoadBalancer (for DNS)
cat > ~/adguard-loadbalancer.yaml <<'EOF'
apiVersion: v1
kind: Service
metadata:
  name: adguard-lb
  namespace: homeserver
  annotations:
    metallb.universe.tf/loadBalancerIPs: 192.168.1.240
spec:
  selector:
    app: adguard
  type: LoadBalancer
  ports:
  - port: 53
    targetPort: 53
    protocol: TCP
    name: dns-tcp
  - port: 53
    targetPort: 53
    protocol: UDP
    name: dns-udp
  - port: 80
    targetPort: 80
    name: http
  - port: 3000
    targetPort: 3000
    name: setup
EOF

kubectl apply -f ~/adguard-loadbalancer.yaml

# Get external IP
kubectl get svc -n homeserver adguard-lb
# Update your router/DNS to use this IP (192.168.1.240)
```

### 4.3 Deploy NGINX Ingress Controller

```bash
# Install NGINX Ingress via Helm
helm repo add ingress-nginx https://kubernetes.github.io/ingress-nginx
helm repo update

helm install ingress-nginx ingress-nginx/ingress-nginx \
  --namespace ingress-nginx \
  --set controller.service.type=LoadBalancer \
  --set controller.service.loadBalancerIP=192.168.1.241 \
  --version 4.8.3

# Wait for LoadBalancer IP
kubectl wait --namespace ingress-nginx \
  --for=condition=ready pod \
  --selector=app.kubernetes.io/component=controller \
  --timeout=120s

kubectl get svc -n ingress-nginx ingress-nginx-controller
```

### 4.4 Create Ingress Rules (VPN-First Strategy)

```bash
# Create Ingress with IP whitelisting for VPN-first
cat > ~/homeserver-ingress.yaml <<'EOF'
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: n8n-ingress
  namespace: homeserver
  annotations:
    nginx.ingress.kubernetes.io/backend-protocol: "HTTPS"
    nginx.ingress.kubernetes.io/ssl-passthrough: "true"
    # Rate limiting for public webhooks
    nginx.ingress.kubernetes.io/limit-rps: "20"
    nginx.ingress.kubernetes.io/limit-burst-multiplier: "5"
spec:
  ingressClassName: nginx
  rules:
  - host: n8n.homeserver.local
    http:
      paths:
      # PUBLIC: Webhook endpoints (external services like GitHub)
      - path: /webhook
        pathType: Prefix
        backend:
          service:
            name: n8n
            port:
              number: 5678
      # PRIVATE: Admin UI (VPN/Local only)
      - path: /
        pathType: Prefix
        backend:
          service:
            name: n8n
            port:
              number: 5678
---
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: n8n-network-policy
  namespace: homeserver
spec:
  podSelector:
    matchLabels:
      app: n8n
  policyTypes:
  - Ingress
  ingress:
  # Allow from ingress controller
  - from:
    - namespaceSelector:
        matchLabels:
          name: ingress-nginx
    ports:
    - protocol: TCP
      port: 5678
  # Allow from within namespace
  - from:
    - podSelector: {}
    ports:
    - protocol: TCP
      port: 5678
---
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: grafana-ingress
  namespace: monitoring
  annotations:
    nginx.ingress.kubernetes.io/whitelist-source-range: "192.168.0.0/16,10.13.13.0/24"
spec:
  ingressClassName: nginx
  rules:
  - host: grafana.homeserver.local
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: kube-prometheus-stack-grafana
            port:
              number: 80
---
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: prometheus-ingress
  namespace: monitoring
  annotations:
    nginx.ingress.kubernetes.io/whitelist-source-range: "192.168.0.0/16,10.13.13.0/24"
spec:
  ingressClassName: nginx
  rules:
  - host: prometheus.homeserver.local
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: kube-prometheus-stack-prometheus
            port:
              number: 9090
EOF

kubectl apply -f ~/homeserver-ingress.yaml

# Test ingress
curl -H "Host: grafana.homeserver.local" http://192.168.1.241
```

### 4.5 Deploy WireGuard VPN as DaemonSet

```bash
# Create WireGuard deployment
cat > ~/wireguard-daemonset.yaml <<'EOF'
apiVersion: v1
kind: PersistentVolume
metadata:
  name: wireguard-config-pv
spec:
  capacity:
    storage: 1Gi
  accessModes:
    - ReadWriteOnce
  persistentVolumeReclaimPolicy: Retain
  storageClassName: local-path
  local:
    path: /var/lib/rancher/k3s/storage/wireguard-config
  nodeAffinity:
    required:
      nodeSelectorTerms:
      - matchExpressions:
        - key: kubernetes.io/hostname
          operator: In
          values:
          - server1
---
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: wireguard-config-pvc
  namespace: homeserver
spec:
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      storage: 1Gi
  storageClassName: local-path
---
apiVersion: apps/v1
kind: DaemonSet
metadata:
  name: wireguard
  namespace: homeserver
spec:
  selector:
    matchLabels:
      app: wireguard
  template:
    metadata:
      labels:
        app: wireguard
    spec:
      hostNetwork: true
      containers:
      - name: wireguard
        image: lscr.io/linuxserver/wireguard:1.0.20210914@sha256:your-digest-here
        securityContext:
          capabilities:
            add:
            - NET_ADMIN
            - SYS_MODULE
          privileged: false
        env:
        - name: PUID
          value: "1000"
        - name: PGID
          value: "1000"
        - name: TZ
          value: "UTC"
        - name: SERVERURL
          value: "<YOUR_PUBLIC_IP_OR_DOMAIN>"
        - name: SERVERPORT
          value: "51820"
        - name: PEERS
          value: "5"
        - name: PEERDNS
          value: "192.168.1.240"  # AdGuard LB IP
        - name: INTERNAL_SUBNET
          value: "10.13.13.0"
        - name: ALLOWEDIPS
          value: "192.168.1.0/24,10.13.13.0/24"
        - name: LOG_CONFS
          value: "true"
        ports:
        - containerPort: 51820
          protocol: UDP
          hostPort: 51820
        volumeMounts:
        - name: wireguard-config
          mountPath: /config
        - name: lib-modules
          mountPath: /lib/modules
          readOnly: true
        resources:
          requests:
            memory: "128Mi"
            cpu: "100m"
          limits:
            memory: "256Mi"
            cpu: "500m"
      volumes:
      - name: wireguard-config
        persistentVolumeClaim:
          claimName: wireguard-config-pvc
      - name: lib-modules
        hostPath:
          path: /lib/modules
          type: Directory
      nodeSelector:
        homeserver.local/role: infrastructure
EOF

# Copy existing WireGuard config before deployment
ssh user@<SERVER_1_IP> "sudo mkdir -p /var/lib/rancher/k3s/storage/wireguard-config"
sudo rsync -avz --progress ./data/wireguard/ user@<SERVER_1_IP>:/tmp/wireguard-config/
ssh user@<SERVER_1_IP> "sudo mv /tmp/wireguard-config/* /var/lib/rancher/k3s/storage/wireguard-config/"

kubectl apply -f ~/wireguard-daemonset.yaml

# Verify
kubectl get pods -n homeserver -l app=wireguard
kubectl logs -n homeserver -l app=wireguard --tail=50

# Get QR codes for peers
kubectl exec -n homeserver -l app=wireguard -- cat /config/peer1/peer1.png | base64 -d > peer1.png
```

**Validation**:
- [ ] MetalLB assigning IPs correctly
- [ ] AdGuard accessible via LoadBalancer IP
- [ ] NGINX Ingress responding
- [ ] WireGuard VPN accessible
- [ ] IP whitelisting working (test from outside VPN)

---

## Phase 5: Cleanup & Optimization

**Time**: 2 hours
**Risk**: Low

### 5.1 Remove Docker Compose Services

```bash
# Final verification that k3s services are working
kubectl get pods -A
kubectl get svc -A

# Stop and remove Docker Compose
cd /path/to/home-server-stack
docker compose down

# Optional: Remove Docker images
docker system prune -a

# Optional: Uninstall Docker if no longer needed
# sudo apt remove docker-ce docker-ce-cli containerd.io
```

### 5.2 Create Helper Scripts

```bash
# Create kubectl alias
cat >> ~/.bashrc <<'EOF'
alias k='kubectl'
alias kgp='kubectl get pods'
alias kgs='kubectl get svc'
alias kl='kubectl logs'
alias kx='kubectl exec -it'
complete -F __start_kubectl k
EOF

source ~/.bashrc

# Create status check script
cat > ~/k3s-status.sh <<'EOF'
#!/bin/bash
echo "=== k3s Cluster Status ==="
kubectl get nodes -o wide
echo ""
echo "=== Homeserver Pods ==="
kubectl get pods -n homeserver -o wide
echo ""
echo "=== Monitoring Pods ==="
kubectl get pods -n monitoring
echo ""
echo "=== Services with External IPs ==="
kubectl get svc -A | grep LoadBalancer
echo ""
echo "=== Recent Events ==="
kubectl get events -n homeserver --sort-by='.lastTimestamp' | tail -10
EOF

chmod +x ~/k3s-status.sh

# Create backup script
cat > ~/k3s-backup.sh <<'EOF'
#!/bin/bash
BACKUP_DIR="/backup/k3s-$(date +%Y%m%d-%H%M%S)"
mkdir -p "$BACKUP_DIR"

echo "Backing up k3s data..."
sudo rsync -az /var/lib/rancher/k3s/storage/ "$BACKUP_DIR/storage/"
sudo rsync -az /etc/rancher/k3s/ "$BACKUP_DIR/config/"

echo "Backing up cluster resources..."
kubectl get all -A -o yaml > "$BACKUP_DIR/all-resources.yaml"
kubectl get pv,pvc -A -o yaml > "$BACKUP_DIR/volumes.yaml"
kubectl get configmap,secret -A -o yaml > "$BACKUP_DIR/configs.yaml"

echo "Backup completed: $BACKUP_DIR"
EOF

chmod +x ~/k3s-backup.sh
```

### 5.3 Setup Automated Backups (Cron)

```bash
# Add to crontab
crontab -e

# Add this line (daily backup at 2 AM)
0 2 * * * /home/user/k3s-backup.sh >> /var/log/k3s-backup.log 2>&1
```

### 5.4 Documentation Updates

Create `docs/K3S_OPERATIONS.md`:

```markdown
# k3s Operations Guide

## Common Tasks

### Accessing Services
- Grafana: http://grafana.homeserver.local (VPN/LAN only)
- Prometheus: http://prometheus.homeserver.local (VPN/LAN only)
- n8n: https://n8n.homeserver.local (webhooks public, UI VPN/LAN)
- AdGuard: http://192.168.1.240

### Viewing Logs
```bash
kubectl logs -n homeserver deploy/n8n --tail=100 -f
kubectl logs -n homeserver deploy/ollama --tail=100 -f
```

### Restarting Services
```bash
kubectl rollout restart deployment/n8n -n homeserver
kubectl rollout restart deployment/ollama -n homeserver
```

### Scaling Services
```bash
kubectl scale deployment/ollama -n homeserver --replicas=2
```

### Getting Shell Access
```bash
kubectl exec -it -n homeserver deploy/n8n -- /bin/sh
```

### Checking Resource Usage
```bash
kubectl top nodes
kubectl top pods -n homeserver
```

## Troubleshooting

### Pod Not Starting
```bash
kubectl describe pod <pod-name> -n homeserver
kubectl logs <pod-name> -n homeserver --previous
```

### Service Not Accessible
```bash
kubectl get svc -n homeserver
kubectl get endpoints -n homeserver
kubectl describe ingress -n homeserver
```

### Storage Issues
```bash
kubectl get pv,pvc -A
kubectl describe pvc <pvc-name> -n homeserver
```

## Backups

Daily automated backups run at 2 AM via cron.
Manual backup: `~/k3s-backup.sh`

## Upgrades

### Upgrade k3s
```bash
curl -sfL https://get.k3s.io | INSTALL_K3S_VERSION=v1.29.0+k3s1 sh -
```

### Upgrade Services
```bash
kubectl set image deployment/n8n n8n=n8nio/n8n:1.20.0 -n homeserver
```
```

**Validation**:
- [ ] Docker Compose removed
- [ ] Helper scripts working
- [ ] Backups automated
- [ ] Documentation complete

---

## Rollback Procedures

### Rollback from Phase 5 (Cleanup)
```bash
# Restart Docker Compose
cd /path/to/home-server-stack
docker compose up -d

# Services will resume with original configuration
```

### Rollback from Phase 4 (Networking)
```bash
# Remove ingress and MetalLB
kubectl delete -f ~/homeserver-ingress.yaml
kubectl delete -f ~/wireguard-daemonset.yaml
kubectl delete -f ~/metallb-config.yaml
kubectl delete -f https://raw.githubusercontent.com/metallb/metallb/v0.13.12/config/manifests/metallb-native.yaml

# Services still accessible via port-forward
```

### Rollback from Phase 3 (Services)
```bash
# Delete migrated services
kubectl delete -f ~/ollama-deployment.yaml
kubectl delete -f ~/n8n-deployment.yaml
kubectl delete -f ~/adguard-deployment.yaml

# Restart Docker Compose
cd /path/to/home-server-stack
docker compose up -d adguard n8n ollama

# Data is preserved in ./data/ directory
```

### Rollback from Phase 2 (Monitoring)
```bash
# Uninstall kube-prometheus-stack
helm uninstall kube-prometheus-stack -n monitoring

# Restart Docker Compose monitoring
docker compose -f docker-compose.yml -f docker-compose.monitoring.yml up -d
```

### Rollback from Phase 1 (Cluster)
```bash
# Uninstall k3s on Server 2
ssh user@<SERVER_2_IP>
/usr/local/bin/k3s-agent-uninstall.sh

# Uninstall k3s on Server 1
ssh user@<SERVER_1_IP>
/usr/local/bin/k3s-uninstall.sh

# All Docker Compose services still running
```

### Emergency: Full Rollback
```bash
# 1. Uninstall k3s completely
/usr/local/bin/k3s-uninstall.sh  # Server 1
/usr/local/bin/k3s-agent-uninstall.sh  # Server 2

# 2. Ensure Docker Compose is running
cd /path/to/home-server-stack
docker compose up -d

# 3. Restore backups if needed
sudo rsync -az /backup/latest/ ./data/

# 4. Verify all services
docker compose ps
```

---

## Helper Scripts

### Service Health Check
```bash
cat > ~/check-services.sh <<'EOF'
#!/bin/bash
echo "Checking k3s services..."

SERVICES=("adguard" "n8n" "ollama" "wireguard")
NAMESPACE="homeserver"

for svc in "${SERVICES[@]}"; do
  echo -n "Checking $svc... "
  POD=$(kubectl get pod -n $NAMESPACE -l app=$svc -o jsonpath='{.items[0].metadata.name}' 2>/dev/null)

  if [ -z "$POD" ]; then
    echo "❌ NOT FOUND"
    continue
  fi

  STATUS=$(kubectl get pod -n $NAMESPACE "$POD" -o jsonpath='{.status.phase}')

  if [ "$STATUS" == "Running" ]; then
    echo "✅ $STATUS"
  else
    echo "⚠️  $STATUS"
  fi
done

echo ""
echo "External IPs:"
kubectl get svc -n homeserver -o wide | grep LoadBalancer
EOF

chmod +x ~/check-services.sh
```

### Quick Port Forward
```bash
cat > ~/port-forward.sh <<'EOF'
#!/bin/bash
# Quick port forwarding for development/testing

case "$1" in
  grafana)
    kubectl port-forward -n monitoring svc/kube-prometheus-stack-grafana 3000:80
    ;;
  prometheus)
    kubectl port-forward -n monitoring svc/kube-prometheus-stack-prometheus 9090:9090
    ;;
  n8n)
    kubectl port-forward -n homeserver svc/n8n 5678:5678
    ;;
  ollama)
    kubectl port-forward -n homeserver svc/ollama 11434:11434
    ;;
  *)
    echo "Usage: $0 {grafana|prometheus|n8n|ollama}"
    exit 1
esac
EOF

chmod +x ~/port-forward.sh
```

### Pod Logs Viewer
```bash
cat > ~/view-logs.sh <<'EOF'
#!/bin/bash
# View logs for a service

if [ -z "$1" ]; then
  echo "Usage: $0 <service-name> [namespace]"
  echo "Example: $0 n8n homeserver"
  exit 1
fi

SERVICE=$1
NAMESPACE=${2:-homeserver}

POD=$(kubectl get pod -n $NAMESPACE -l app=$SERVICE -o jsonpath='{.items[0].metadata.name}')

if [ -z "$POD" ]; then
  echo "No pod found for service: $SERVICE"
  exit 1
fi

echo "Viewing logs for $POD..."
kubectl logs -n $NAMESPACE "$POD" -f --tail=100
EOF

chmod +x ~/view-logs.sh
```

---

## Troubleshooting

### Issue: Pod stuck in Pending
```bash
# Check events
kubectl describe pod <pod-name> -n homeserver

# Common causes:
# 1. PVC not bound
kubectl get pvc -n homeserver

# 2. Node affinity not matching
kubectl get nodes --show-labels

# 3. Resource constraints
kubectl describe node <node-name>
```

### Issue: Service not accessible
```bash
# Check service endpoints
kubectl get endpoints -n homeserver

# Check if pods are ready
kubectl get pods -n homeserver -o wide

# Test from within cluster
kubectl run -n homeserver curl-test --rm -it --image=curlimages/curl -- sh
# Then: curl http://service-name:port
```

### Issue: LoadBalancer stuck in Pending
```bash
# Check MetalLB status
kubectl get pods -n metallb-system
kubectl logs -n metallb-system -l app=metallb

# Verify IP pool
kubectl get ipaddresspool -n metallb-system -o yaml

# Check if IPs are available
kubectl get svc -A | grep LoadBalancer
```

### Issue: Ingress not routing
```bash
# Check ingress controller
kubectl get pods -n ingress-nginx
kubectl logs -n ingress-nginx -l app.kubernetes.io/component=controller

# Verify ingress rules
kubectl describe ingress -n homeserver

# Test with curl
curl -v -H "Host: n8n.homeserver.local" http://<INGRESS_IP>
```

### Issue: Data not persisting
```bash
# Check PV/PVC status
kubectl get pv,pvc -n homeserver

# Verify mount points
kubectl exec -n homeserver deploy/n8n -- df -h

# Check data on host
ssh user@<SERVER_IP>
ls -la /var/lib/rancher/k3s/storage/
```

### Issue: High memory usage
```bash
# Check resource usage
kubectl top nodes
kubectl top pods -n homeserver

# Identify memory hog
kubectl top pods -n homeserver --sort-by=memory

# Adjust resource limits
kubectl edit deployment/<deployment-name> -n homeserver
```

### Issue: DNS not resolving
```bash
# Check AdGuard status
kubectl get pods -n homeserver -l app=adguard
kubectl logs -n homeserver -l app=adguard

# Test DNS from pod
kubectl run -n homeserver dns-test --rm -it --image=busybox --restart=Never -- nslookup google.com

# Check if AdGuard LB has IP
kubectl get svc -n homeserver adguard-lb
```

---

## Performance Optimization

### Tune k3s for Homelab
```bash
# Edit k3s config
sudo vim /etc/systemd/system/k3s.service

# Add flags:
# --kube-controller-manager-arg=node-monitor-period=10s
# --kube-controller-manager-arg=node-monitor-grace-period=30s
# --kubelet-arg=max-pods=150

# Restart k3s
sudo systemctl daemon-reload
sudo systemctl restart k3s
```

### Optimize Pod Resources
```bash
# Review resource requests/limits
kubectl describe pod -n homeserver | grep -A 5 "Limits\|Requests"

# Adjust based on actual usage (after monitoring for a week)
kubectl edit deployment/<deployment-name> -n homeserver
```

### Enable Pod Autoscaling (HPA)
```bash
# For CPU-based autoscaling (example: Ollama)
kubectl autoscale deployment ollama -n homeserver --cpu-percent=70 --min=1 --max=3

# Verify HPA
kubectl get hpa -n homeserver
```

---

## Security Hardening (Post-Migration)

### Network Policies (Additional)
```bash
# Deny all ingress by default, allow explicitly
cat > ~/network-policy-deny-all.yaml <<'EOF'
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: deny-all-ingress
  namespace: homeserver
spec:
  podSelector: {}
  policyTypes:
  - Ingress
EOF

kubectl apply -f ~/network-policy-deny-all.yaml

# Then add specific allow rules for each service
```

### Pod Security Standards
```bash
# Enforce restricted pod security
kubectl label namespace homeserver pod-security.kubernetes.io/enforce=restricted
kubectl label namespace homeserver pod-security.kubernetes.io/audit=restricted
kubectl label namespace homeserver pod-security.kubernetes.io/warn=restricted
```

### RBAC for Service Accounts
```bash
# Create read-only user for monitoring
kubectl create serviceaccount monitoring-reader -n monitoring
kubectl create clusterrolebinding monitoring-reader-binding \
  --clusterrole=view \
  --serviceaccount=monitoring:monitoring-reader
```

---

## Monitoring k3s Cluster Health

### Setup k3s Metrics in Prometheus
The kube-prometheus-stack automatically monitors k3s components. Additional custom metrics:

```yaml
# Add to PrometheusRule
apiVersion: monitoring.coreos.com/v1
kind: PrometheusRule
metadata:
  name: k3s-cluster-alerts
  namespace: monitoring
spec:
  groups:
    - name: k3s-health
      rules:
        - alert: K3sNodeNotReady
          expr: kube_node_status_condition{condition="Ready",status="true"} == 0
          for: 5m
          labels:
            severity: critical
          annotations:
            summary: "k3s node {{ $labels.node }} not ready"

        - alert: K3sHighPodCount
          expr: count(kube_pod_info) > 100
          for: 10m
          labels:
            severity: warning
          annotations:
            summary: "High pod count: {{ $value }}"
```

### Grafana Dashboards for k3s
Import these dashboard IDs in Grafana:
- **Node Exporter Full**: 1860
- **Kubernetes Cluster Monitoring**: 7249
- **k3s Cluster**: 13770

---

## Next Steps After Migration

1. **VPN-First Security** (security-tickets/17-wireguard-hardening.md)
   - Implement Fail2ban for WireGuard
   - Setup peer management
   - Configure VPN monitoring alerts

2. **Let's Encrypt for n8n** (security-tickets/04-tls-certificate-monitoring.md)
   - Use cert-manager for automated certificate renewal
   - Replace self-signed certs

3. **Network Segmentation** (security-tickets/05-network-segmentation.md)
   - Implement NetworkPolicies for service isolation
   - Setup frontend/backend/monitoring network tiers

4. **Add More Services**
   - Migrate planned services from SERVICES.md
   - Use k3s-native deployments

5. **Disaster Recovery Planning**
   - Test restoration from backups
   - Document recovery procedures
   - Setup offsite backup replication

---

## Cost/Benefit Analysis

### Pros of k3s Migration
- **Scalability**: Easy to add more nodes (Server 3, 4, etc.)
- **High Availability**: Can run multiple replicas of critical services
- **Industry Standard**: Learn production Kubernetes skills
- **Better Resource Management**: CPU/memory limits enforced
- **Service Discovery**: Built-in DNS, load balancing
- **Rolling Updates**: Zero-downtime deployments
- **Ecosystem**: Access to Helm charts, operators

### Cons of k3s Migration
- **Complexity**: Steeper learning curve than Docker Compose
- **Resource Overhead**: ~500MB RAM for k3s vs ~50MB for Docker
- **Single Points of Failure**: Only 1 control plane (can be HA with 3+ nodes)
- **Network Complexity**: Pod networking, ingress, policies
- **Troubleshooting**: More moving parts to debug

### When to Stay with Docker Compose
- Only 1-2 servers with no plans to expand
- Simple stack with < 10 services
- Prefer simplicity over scalability
- Limited time for learning k8s

### When k3s Makes Sense
- **You're here**: Already planning 2 servers ✅
- Want to learn Kubernetes
- Plan to add more services/servers
- Need high availability for critical services
- Want industry-standard infrastructure skills

---

## References

- [k3s Documentation](https://docs.k3s.io/)
- [Kubernetes Documentation](https://kubernetes.io/docs/)
- [Helm Charts](https://artifacthub.io/)
- [kube-prometheus-stack](https://github.com/prometheus-community/helm-charts/tree/main/charts/kube-prometheus-stack)
- [MetalLB](https://metallb.universe.tf/)
- [NGINX Ingress Controller](https://kubernetes.github.io/ingress-nginx/)
- [k3s Resource Requirements](https://docs.k3s.io/installation/requirements)

---

## Appendix: Quick Command Reference

### Cluster Management
```bash
# Node status
kubectl get nodes -o wide

# Cluster info
kubectl cluster-info

# Component status
kubectl get componentstatuses

# k3s version
k3s --version
```

### Pod Operations
```bash
# List all pods
kubectl get pods -A

# Pod details
kubectl describe pod <pod-name> -n <namespace>

# Pod logs
kubectl logs <pod-name> -n <namespace> -f

# Execute command in pod
kubectl exec -it <pod-name> -n <namespace> -- /bin/sh

# Copy files to/from pod
kubectl cp <local-file> <namespace>/<pod>:/path/to/file
kubectl cp <namespace>/<pod>:/path/to/file <local-file>
```

### Service & Networking
```bash
# List services
kubectl get svc -A

# Service endpoints
kubectl get endpoints -n <namespace>

# Ingress rules
kubectl get ingress -A

# NetworkPolicies
kubectl get networkpolicy -A
```

### Storage
```bash
# Persistent volumes
kubectl get pv

# Persistent volume claims
kubectl get pvc -A

# Storage classes
kubectl get storageclass
```

### Debugging
```bash
# Events (last hour)
kubectl get events -A --sort-by='.lastTimestamp'

# Resource usage
kubectl top nodes
kubectl top pods -A

# API resources
kubectl api-resources

# Explain resource
kubectl explain pod.spec.containers
```

### Cleanup
```bash
# Delete pod (will be recreated by deployment)
kubectl delete pod <pod-name> -n <namespace>

# Delete deployment
kubectl delete deployment <deployment-name> -n <namespace>

# Force delete stuck pod
kubectl delete pod <pod-name> -n <namespace> --grace-period=0 --force

# Prune unused resources
kubectl delete pod --field-selector status.phase=Failed -A
```

---

**End of Migration Plan**

**Total Estimated Time**: 15-19 hours over 2-3 weekends
**Risk Level**: Medium (with rollback at each phase)
**Recommended Approach**: Execute phases sequentially, validate thoroughly before proceeding

Good luck with the migration! 🚀
