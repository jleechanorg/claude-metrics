# 🚀 Quick Grafana Setup Guide

## Option 1: Docker Setup (Recommended)

### 1. Quick Start
```bash
# Set up dashboard files
./claude-metrics dashboard --setup-docker

# Start Grafana + Prometheus
docker-compose -f grafana/docker-compose.yml up -d

# Access Grafana
open http://localhost:3000
```

**Login**: admin/admin

### 2. Import Dashboard
1. Go to Dashboards → Import
2. Upload `grafana/claude-metrics-dashboard.json`
3. Select Prometheus data source
4. Click Import

### 3. Configure Data Source
1. Go to Configuration → Data Sources
2. Add Prometheus data source
3. URL: `http://prometheus:9090`
4. Test & Save

---

## Option 2: Manual Setup

### 1. Install Grafana
```bash
# Ubuntu/Debian
sudo apt-get install -y software-properties-common
sudo add-apt-repository "deb https://packages.grafana.com/oss/deb stable main"
wget -q -O - https://packages.grafana.com/gpg.key | sudo apt-key add -
sudo apt-get update
sudo apt-get install grafana

# Start Grafana
sudo systemctl start grafana-server
sudo systemctl enable grafana-server
```

### 2. Set Up Prometheus Export
```bash
# Export metrics every 5 minutes
./claude-metrics export --format prometheus --output /var/lib/prometheus/claude-metrics.prom

# Set up cron job
echo "*/5 * * * * /path/to/claude-metrics scan --since 1h && /path/to/claude-metrics export --format prometheus --output /var/lib/prometheus/claude-metrics.prom" | crontab -
```

### 3. Configure Prometheus
Add to `prometheus.yml`:
```yaml
scrape_configs:
  - job_name: 'claude-metrics'
    static_configs:
      - targets: ['localhost:8080']
    file_sd_configs:
      - files: ['/var/lib/prometheus/claude-metrics.prom']
```

---

## Option 3: JSON Data Source (Simple)

### 1. Install JSON Plugin
```bash
grafana-cli plugins install simpod-json-datasource
sudo systemctl restart grafana-server
```

### 2. Export JSON API
```bash
./claude-metrics export --format grafana-json --output /tmp/claude-api/

# Start simple HTTP server
cd /tmp/claude-api && python3 server.py
```

### 3. Configure Data Source
1. Add JSON data source
2. URL: `http://localhost:8080`
3. Import dashboard and select JSON data source

---

## 📊 Dashboard Features

### Main Panels
- **Total Conversations**: Overall activity across repositories
- **Error Detection**: Real-time error pattern monitoring  
- **Tool Usage**: Most frequently used Claude Code tools
- **Repository Activity**: Per-repository conversation trends

### Available Metrics
- `claude_conversations_total` - Conversations by repository
- `claude_errors_total` - Error patterns detected
- `claude_tools_used_total` - Tool usage frequency
- `claude_patterns_detected` - All pattern categories

### Time Ranges
- Last 24 hours
- Last 7 days  
- Last 30 days
- Custom ranges

---

## 🔄 Automation

### Continuous Updates
```bash
# Option 1: Cron job
*/15 * * * * /path/to/claude-metrics scan --since 1h && /path/to/claude-metrics export --format prometheus

# Option 2: Systemd service
sudo cp grafana/claude-metrics.service /etc/systemd/system/
sudo systemctl enable claude-metrics
sudo systemctl start claude-metrics
```

### Docker Auto-Update
The Docker Compose setup automatically:
- Scans conversations every 30 seconds
- Exports Prometheus metrics
- Serves metrics on port 8080
- Updates Grafana dashboards

---

## 🛠️ Troubleshooting

### Common Issues

**No data in dashboards**:
```bash
# Check export is working
./claude-metrics export --format prometheus --output /tmp/test.prom
cat /tmp/test.prom

# Verify Prometheus scraping
curl http://localhost:9090/api/v1/targets
```

**Dashboard import fails**:
- Ensure data source is configured first
- Check Grafana logs: `sudo journalctl -u grafana-server`

**Metrics not updating**:
```bash
# Check scan is working
./claude-metrics scan --since 1h
./claude-metrics status

# Verify cron job
crontab -l
```

---

## 📈 Next Steps

1. **Customize Dashboards**: Modify panels for your specific needs
2. **Set Up Alerts**: Configure Grafana alerts for error spikes
3. **Export & Share**: Export dashboard JSON for team sharing
4. **Advanced Queries**: Create custom Prometheus queries

For detailed configuration options, see `grafana/README.md`.