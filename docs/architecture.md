# Platform Engineering Lab - Architecture

## Overview

This project is a small Platform Engineering lab demonstrating application delivery, infrastructure provisioning, deployment automation, Kubernetes operations, and monitoring.

The platform is built around automated validation and immutable container images.

## High-Level Architecture

```text
Developer
   |
   | Git push / Pull Request
   v
GitHub Repository
   |
   v
GitHub Actions
   |
   +--------------------------+
   | Validation               |
   |--------------------------|
   | Python compile           |
   | Pytest                   |
   | Config validation        |
   | Terraform validation    |
   | Kubernetes YAML          |
   | Docker build             |
   +------------+-------------+
                |
                v
       GHCR Container Registry
                |
                | Git SHA image
                v
        GitHub Actions Deploy
                |
                v
            AWS OIDC
                |
                v
              AWS
                |
                v
          EC2 Platform Host
                |
                v
        AWS Systems Manager
                |
                v
             Docker
                |
                v
            demo-app
                |
                v
          /health check


Monitoring

demo-app
   |
   v
cAdvisor
   |
   v
Prometheus
   |
   v
Grafana