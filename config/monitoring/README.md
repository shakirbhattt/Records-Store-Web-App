# Monitoring and Observability Configuration

This directory contains all configuration files for the observability stack in the KodeKloud Records Store application.

## Directory Structure

- **grafana-provisioning/**
  - **dashboards/**: Grafana dashboard definitions
    - `observability-dashboard.json`: Main dashboard for monitoring metrics, logs, and traces
  - **datasources/**: Grafana datasource configurations
    - `prometheus.yml`: Prometheus datasource
    - `loki.yml`: Loki datasource for logs
    - `jaeger.yml`: Jaeger datasource for traces

- **logging/**
  - `loki-config.yaml`: Loki server configuration
  - `fluent-bit-config.yaml`: Fluent Bit log collector configuration

- `prometheus.yml`: Prometheus server configuration with scrape targets
- `alert_rules.yml`: Prometheus alerting rules
- `alertmanager.yml`: Alert Manager configuration for notifications
- `sli_rules.yml`: Service Level Indicator definitions
- `blackbox.yml`: Black-box exporter configuration for synthetic monitoring

## Usage in Docker Compose

These configuration files are mounted into the respective containers in the `docker-compose.yaml` file:

```yaml
prometheus:
  volumes:
    - ./config/monitoring/prometheus.yml:/etc/prometheus/prometheus.yml
    - ./config/monitoring/alert_rules.yml:/etc/prometheus/alert_rules.yml
    - ./config/monitoring/sli_rules.yml:/etc/prometheus/sli_rules.yml

grafana:
  volumes:
    - ./config/monitoring/grafana-provisioning:/etc/grafana/provisioning

alertmanager:
  volumes:
    - ./config/monitoring/alertmanager.yml:/etc/alertmanager/alertmanager.yml

blackbox-exporter:
  volumes:
    - ./config/monitoring/blackbox.yml:/etc/blackbox_exporter/config.yml

loki:
  volumes:
    - ./config/monitoring/logging/loki-config.yaml:/etc/loki/local-config.yaml

fluent-bit:
  volumes:
    - ./config/monitoring/logging/fluent-bit-config.yaml:/fluent-bit/etc/fluent-bit.conf
```

## Customization

To modify the observability stack:

1. Edit the relevant configuration file
2. Restart the corresponding service:
   ```bash
   docker-compose restart prometheus|grafana|alertmanager|loki|fluent-bit
   ```

For adding new Grafana dashboards, place the JSON definition in the `grafana-provisioning/dashboards/` directory. 