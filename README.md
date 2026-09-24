# Platform Engineering Lab

A hands-on Platform Engineering lab that demonstrates how an internal deployment workflow can automate application validation, infrastructure provisioning, container publishing, deployment, health verification, rollback, and monitoring.

The project demonstrates practical Platform Engineering concepts using Python, Terraform, Docker, Kubernetes, GitHub Actions, AWS, AWS Systems Manager (SSM), Prometheus, and Grafana.

> **Scope:** This is a personal hands-on lab project. AWS deployment is implemented for learning and validation; it is not presented as production experience.

---

## Architecture

```text
                         Developer
                             |
                             v
                    +------------------+
                    |    GitHub Repo   |
                    +--------+---------+
                             |
                             v
                    +------------------+
                    | GitHub Actions   |
                    |    CI/CD         |
                    +--------+---------+
                             |
              +--------------+--------------+
              |              |              |
              v              v              v
        Python Tests   Terraform Validate  Docker Build
              |              |              |
              |              |              v
              |              |       +---------------+
              |              |       |      GHCR     |
              |              |       | Container Reg.|
              |              |       +-------+-------+
              |              |               |
              +--------------+---------------+
                                             |
                                             v
                                    GitHub OIDC Token
                                             |
                                             v
                                      +-------------+
                                      |   AWS IAM   |
                                      | Deployment  |
                                      |    Role     |
                                      +------+------+
                                             |
                                             v
                                      AWS SSM Command
                                             |
                                             v
                                      AWS EC2 Instance
                                             |
                                             v
                                        Docker App
                                             |
                                             v
                                      /health check
                                             |
                                             v
                                   Deployment Verification


              Local Kubernetes / Minikube
                         |
                         v
                Kubernetes Deployment
                         |
              +----------+----------+
              |                     |
              v                     v
       Readiness Probe       Liveness Probe
              |                     |
              +----------+----------+
                         |
                         v
                      /health


                     Monitoring
                         |
              +----------+----------+
              |                     |
              v                     v
         Prometheus             cAdvisor
              |                     |
              +----------+----------+
                         |
                         v
                      Grafana
```

For a more detailed architecture and deployment flow, see [`docs/architecture.md`](docs/architecture.md).

---

## What This Project Demonstrates

### 1. Platform CLI

A Python CLI provides a single interface for common platform operations.

Examples:

```powershell
python cli/platform.py validate config/app.yaml --env dev

python cli/platform.py plan config/app.yaml --env dev

python cli/platform.py k8s config/app.yaml --env dev --image <IMAGE>

python cli/platform.py k8s-status config/app.yaml --env dev

python cli/platform.py history config/app.yaml --env dev
```

The CLI handles configuration validation, Terraform operations, Kubernetes deployment, deployment status, health checks, and rollback-related workflows.

---

## 2. Infrastructure as Code

Terraform manages the AWS infrastructure required by the application.

The project separates environment configuration:

```text
terraform/
├── main.tf
├── variables.tf
├── outputs.tf
└── environments/
    ├── dev.tfvars
    ├── staging.tfvars
    └── prod.tfvars
```

Supported environments:

* Development
* Staging
* Production

Different instance sizes can be selected per environment.

Terraform workspaces are also used to isolate environment state.

---

## 3. Containerization

The application is packaged as a Docker image.

```text
app/
├── app.py
├── Dockerfile
└── requirements.txt
```

The application exposes:

```text
GET /
GET /health
GET /metrics
```

`/health` is used by deployment health checks and Kubernetes probes.

`/metrics` exposes Prometheus-compatible application metrics.

---

## 4. Immutable Container Images

GitHub Actions builds and publishes the application image to GitHub Container Registry.

Images are tagged using the Git commit SHA:

```text
ghcr.io/<owner>/platform-lab-app:<git-sha>
```

For example:

```text
ghcr.io/iam-srikanth-talari/platform-lab-app:<commit-sha>
```

Using the commit SHA makes the deployed application version traceable to a specific source-code revision.

This provides a simple immutable-versioning model for deployments.

---

## 5. CI/CD Pipeline

The GitHub Actions workflow performs the following stages:

```text
Checkout
   |
   v
Python validation
   |
   v
Pytest
   |
   v
Terraform format
   |
   v
Terraform validation
   |
   v
Kubernetes YAML validation
   |
   v
Docker build
   |
   v
Publish image to GHCR
   |
   v
Authenticate to AWS using OIDC
   |
   v
Discover EC2
   |
   v
Deploy through AWS SSM
   |
   v
Application health check
```

The validation stage runs before the container image is published.

The workflow also supports manual environment selection for:

```text
dev
staging
prod
```

---

## 6. AWS OIDC Authentication

GitHub Actions authenticates to AWS using GitHub's OIDC identity instead of storing long-lived AWS access keys in GitHub Secrets.

The deployment role is environment-specific:

```text
demo-app-dev-github-actions-role
demo-app-staging-github-actions-role
demo-app-prod-github-actions-role
```

The workflow obtains short-lived AWS credentials through the configured IAM role.

This avoids storing long-lived AWS access keys in the GitHub repository.

---

## 7. AWS Systems Manager

The deployment workflow uses AWS Systems Manager Run Command instead of SSH for CI/CD deployment.

The workflow:

1. Discovers the running EC2 instance using tags.
2. Sends deployment commands through SSM.
3. Pulls the immutable container image.
4. Starts the Docker container.
5. Checks the `/health` endpoint.
6. Reports deployment success or failure.

This keeps SSH out of the CI/CD deployment path.

The repository still contains an Ansible-based configuration path for manual/secondary use.

---

## 8. Kubernetes Deployment

The project also supports local Kubernetes deployment using Minikube.

The generated Deployment includes:

* Replica configuration
* RollingUpdate strategy
* Readiness probe
* Liveness probe
* CPU/memory requests
* CPU/memory limits
* Environment configuration
* Immutable container image

Example strategy:

```yaml
strategy:
  type: RollingUpdate
  rollingUpdate:
    maxUnavailable: 0
    maxSurge: 1
```

This configuration allows new pods to become ready before old pods are removed.

---

## 9. Health Checks

The platform checks deployment health using Kubernetes deployment status and pod status.

Example status:

```text
Application : demo-app
Replicas    : 2
Updated     : 2
Ready       : 2
Available   : 2
Status      : HEALTHY
```

The application also exposes:

```text
/health
```

which is used by Kubernetes readiness and liveness probes.

The EC2 deployment workflow also calls the same endpoint after starting the Docker container.

---

## 10. Deployment Rollback

The Kubernetes deployment workflow supports rollback when a rollout fails.

Example flow:

```text
New deployment
      |
      v
Rolling update
      |
      v
Health checks
      |
   +--+--+
   |     |
Healthy Failed
   |     |
   v     v
 Done  Rollback
         |
         v
   Previous revision
```

A failed rollout can be reverted using Kubernetes rollout history and rollback mechanisms.

Deployment history can be inspected with:

```powershell
python cli/platform.py history config/app.yaml --env dev
```

The rollback workflow was also tested by introducing an unhealthy probe configuration, allowing the rollout to fail, and then reverting to the previous healthy revision.

---

## 11. Monitoring

The project includes a local monitoring stack:

```text
Demo Application
      |
      +----> /metrics
      |
      v
 Prometheus
      |
      +----> Grafana
      |
      +----> cAdvisor
```

Prometheus collects application metrics and container metrics.

Grafana provides dashboards for:

* Request rate
* Health requests
* Prometheus scrape status
* CPU usage
* Memory usage
* Running containers

The Flask application exposes Prometheus-compatible metrics through:

```text
/metrics
```

The Prometheus `up` metric represents whether Prometheus can successfully scrape the configured target. It is distinct from the application's `/health` endpoint.

---

## 12. Testing

The project includes automated Python tests.

Current test coverage includes:

* Configuration validation
* Kubernetes Deployment generation
* Kubernetes Service generation
* Healthy deployment status
* Unhealthy deployment status

Run:

```powershell
python -m pytest
```

Current project test result:

```text
6 passed
```

The CI workflow also executes the test suite as part of platform validation.

---

## 13. Repository Structure

```text
platform-lab/
│
├── .github/
│   └── workflows/
│       └── ci.yml
│
├── app/
│   ├── app.py
│   ├── Dockerfile
│   └── requirements.txt
│
├── cli/
│   ├── platform.py
│   ├── kubernetes.py
│   ├── ssm.py
│   └── __init__.py
│
├── config/
│   ├── app.yaml
│   └── environments/
│       ├── dev.yaml
│       ├── staging.yaml
│       └── prod.yaml
│
├── kubernetes/
│   ├── deployment.yaml
│   ├── service.yaml
│   └── secret.yaml
│
├── monitoring/
│   └── prometheus/
│       └── prometheus.yml
│
├── terraform/
│   ├── main.tf
│   ├── variables.tf
│   ├── outputs.tf
│   ├── environments/
│   │   ├── dev.tfvars
│   │   ├── staging.tfvars
│   │   └── prod.tfvars
│   └── .terraform.lock.hcl
│
├── ansible/
│   ├── playbook.yml
│   ├── verify.yml
│   └── requirements.yml
│
├── tests/
│   ├── test_config.py
│   └── test_kubernetes.py
│
└── docs/
    ├── architecture.md
    └── interview-notes.md
```

---

## Technology Stack

| Area               | Technology                |
| ------------------ | ------------------------- |
| Application        | Python / Flask            |
| Automation         | Python                    |
| Infrastructure     | Terraform                 |
| Cloud              | AWS                       |
| Containers         | Docker                    |
| Container Registry | GitHub Container Registry |
| CI/CD              | GitHub Actions            |
| AWS Authentication | GitHub OIDC               |
| Remote Execution   | AWS Systems Manager       |
| Orchestration      | Kubernetes / Minikube     |
| Monitoring         | Prometheus                |
| Visualization      | Grafana                   |
| Container Metrics  | cAdvisor                  |
| Configuration      | YAML                      |
| Testing            | Pytest                    |
| Version Control    | Git / GitHub              |

---

## Key Engineering Concepts

This lab focuses on practical Platform Engineering concepts:

* Infrastructure as Code
* Environment separation
* Immutable container versions
* CI/CD automation
* Short-lived cloud authentication
* SSH-less CI/CD deployment
* Kubernetes rolling updates
* Health checks
* Deployment rollback
* Automated validation
* Observability
* Infrastructure and application automation
* Configuration-driven deployments

---

## Production Improvements

The current project is intentionally a lab implementation.

A production platform would require additional capabilities such as:

* Remote Terraform state with locking
* EKS or another managed Kubernetes platform
* Private container registry/networking
* Secrets management through AWS Secrets Manager or another dedicated solution
* Centralized logging
* Distributed tracing
* Alerting and incident integration
* Policy enforcement
* More comprehensive test coverage
* Multi-account AWS architecture
* Automated promotion between environments
* Stronger IAM least-privilege policies
* Disaster recovery and backup strategy

These are identified as future production improvements and are not represented as currently implemented features.

---

## Interview Preparation

Detailed interview explanations are available in:

[`docs/interview-notes.md`](docs/interview-notes.md)

The notes cover:

* 30-second project explanation
* 2-minute project explanation
* Architecture decisions
* CI/CD design
* Terraform
* Docker
* GHCR
* AWS OIDC
* SSM
* Kubernetes
* Rolling deployments
* Health checks
* Rollback
* Monitoring
* Testing
* Production improvements
* Honest boundaries around project experience

---

## Project Status

**Current status: Working**

Implemented and validated:

* Python platform CLI
* Terraform infrastructure
* Environment-specific configuration
* Docker application
* GHCR image publishing
* GitHub Actions CI/CD
* GitHub OIDC → AWS authentication
* AWS SSM deployment
* Kubernetes deployment
* Rolling update strategy
* Deployment status
* Deployment history
* Rollback testing
* Prometheus monitoring
* Grafana dashboard
* Automated tests
* Architecture documentation
* Interview documentation

AWS resources are intended to be destroyed when not actively being tested to avoid unnecessary Free Tier consumption.

---

## Project Positioning

This project is a personal hands-on Platform Engineering lab created to demonstrate practical understanding of infrastructure automation, CI/CD, containers, Kubernetes, cloud authentication, remote deployment, health checks, rollback, and observability.

It should be presented as **hands-on project experience**, not as production experience.
