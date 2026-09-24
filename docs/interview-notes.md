# Platform Engineering Lab - Interview Notes

## 1. 30-Second Project Explanation

I built a Platform Engineering lab that automates application delivery from source control to deployment and monitoring.

A developer pushes code to GitHub. GitHub Actions runs Python tests, Terraform validation, Kubernetes YAML validation, and a Docker build. For a successful main-branch build, the application is packaged into an immutable Docker image tagged with the Git commit SHA and published to GitHub Container Registry.

For AWS deployment, GitHub Actions authenticates using AWS OIDC, discovers the target EC2 instance, and uses AWS Systems Manager to deploy the container without SSH. The deployment validates the application's health endpoint.

I also use Kubernetes with Minikube to demonstrate rolling updates, health probes, deployment history, and rollback. Prometheus, cAdvisor, and Grafana provide application and container monitoring.

---

## 2. Two-Minute Project Explanation

The goal of the project is to demonstrate a small internal developer platform rather than requiring developers to manually perform infrastructure and deployment operations.

The project has a Python-based CLI that acts as a platform interface. Configuration is maintained in YAML and includes the application, environment, infrastructure, Kubernetes, and deployment information.

Terraform manages AWS infrastructure as code. The project separates dev, staging, and prod configuration using environment-specific variables.

The application is packaged using Docker. Instead of deploying a mutable `latest` image, GitHub Actions creates an image using the Git commit SHA. This gives each deployment a unique and traceable image reference.

The CI pipeline validates the platform before publishing anything. It runs Python compilation, pytest, configuration validation, Terraform formatting and validation, Kubernetes YAML validation, and a Docker build.

For main-branch pushes, the pipeline publishes the image to GHCR. The deployment job then uses GitHub's OIDC integration to assume an AWS IAM role. This avoids storing long-lived AWS access keys in GitHub.

The workflow dynamically discovers the correct EC2 instance using environment and role tags. It sends deployment commands through AWS Systems Manager rather than using SSH. The EC2 instance pulls the exact image associated with the Git commit, starts the container, and validates `/health`.

For Kubernetes, I use Minikube locally. The deployment has readiness and liveness probes, resource requests and limits, and a RollingUpdate strategy. I also implemented rollout status, deployment history, and rollback handling.

For observability, the application exposes Prometheus metrics. Prometheus collects application and container metrics, cAdvisor provides container metrics, and Grafana visualizes the information.

---

# 3. Why did you build this project?

I wanted to understand the responsibilities of a Platform Engineer beyond individual tools.

Instead of learning Terraform, Docker, Kubernetes, CI/CD, and monitoring separately, I connected them into one workflow where each component has a specific purpose.

The project also focuses on developer experience: a developer should be able to push code and have the platform handle validation, image creation, deployment, health validation, and monitoring.

---

# 4. Why Python?

Python is used for the platform CLI and automation logic.

It is useful because it has strong support for:

* infrastructure automation
* API integration
* Kubernetes automation
* testing
* CLI development
* cloud SDKs

The CLI provides a consistent interface over Terraform and Kubernetes operations.

---

# 5. Why Terraform?

Terraform provides Infrastructure as Code.

Instead of manually creating AWS resources through the console, infrastructure is defined declaratively.

Benefits include:

* repeatability
* version control
* reviewable infrastructure changes
* environment separation
* predictable provisioning and destruction

I also use `terraform validate` and `terraform fmt -check` in CI.

---

# 6. Why Docker?

Docker packages the application and its runtime dependencies into a consistent unit.

This reduces differences between environments.

The same image can be built once and then referenced by its immutable Git SHA during deployment.

---

# 7. Why use Git SHA image tags?

I don't use `latest` for deployment.

For example:

```text
ghcr.io/<owner>/platform-lab-app:<git-sha>
```

The Git SHA gives every image a unique identity.

This provides:

* traceability
* reproducibility
* easier rollback
* clear mapping between source code and deployed artifact

If an interviewer asks which version is running, I can identify the exact Git commit associated with the image.

---

# 8. Why GHCR?

GHCR provides a container registry integrated with GitHub.

The CI pipeline builds the image and publishes it after validation succeeds.

The deployment then consumes the image produced by the publish stage rather than rebuilding it.

This separates:

```text
Build artifact
      |
      v
Container registry
      |
      v
Deployment
```

---

# 9. Why OIDC instead of AWS access keys?

I use GitHub Actions OIDC to authenticate to AWS.

The workflow assumes an AWS IAM role instead of storing long-lived AWS access keys.

The basic flow is:

```text
GitHub Actions
      |
      | OIDC identity
      v
AWS IAM
      |
      | AssumeRole
      v
Temporary AWS credentials
```

This reduces the need for permanent AWS credentials in GitHub.

---

# 10. Why AWS Systems Manager instead of SSH?

The deployment uses AWS Systems Manager to execute commands on the EC2 instance.

The workflow does not need to manage SSH private keys or expose SSH access for deployment.

The flow is:

```text
GitHub Actions
      |
      v
AWS SSM
      |
      v
EC2
      |
      v
Docker
```

SSM executes the deployment commands remotely and returns the command status.

---

# 11. How does the deployment find the EC2 instance?

The workflow does not hardcode the instance ID.

It discovers the instance using tags such as:

```text
Role=platform-app
Environment=dev
```

and requires the instance to be running.

This means the workflow can locate the correct environment even if the EC2 instance ID changes.

---

# 12. What happens after deployment?

The deployment sends commands to the EC2 instance to:

1. ensure Docker is running
2. pull the immutable image
3. remove the previous `demo-app` container
4. start the new container
5. verify the running container
6. repeatedly check `/health`

If the health check fails, the deployment command fails.

---

# 13. Why Kubernetes?

Kubernetes demonstrates the orchestration side of the platform.

The project uses Kubernetes to manage:

* replicas
* rolling updates
* health probes
* service exposure
* deployment history
* rollback

The current lab uses Minikube locally.

---

# 14. What is the RollingUpdate strategy?

The deployment uses:

```yaml
strategy:
  type: RollingUpdate
  rollingUpdate:
    maxUnavailable: 0
    maxSurge: 1
```

This means Kubernetes is configured to avoid intentionally reducing the number of available replicas during the update while allowing one additional pod above the desired replica count.

The goal is to reduce service disruption during deployments.

---

# 15. What are readiness and liveness probes?

The application exposes:

```text
/health
```

The readiness probe determines whether a pod should receive traffic.

The liveness probe helps Kubernetes determine whether the container needs to be restarted.

They serve different purposes:

```text
Readiness
    |
    +--> Should this pod receive traffic?

Liveness
    |
    +--> Is this container still healthy?
```

---

# 16. How does rollback work?

The Kubernetes deployment automation waits for the rollout to complete.

If the rollout fails, the automation attempts:

```text
kubectl rollout undo deployment/demo-app
```

The project also exposes deployment history through the CLI.

The workflow is:

```text
New deployment
      |
      v
Rollout
   /     \
Success  Failure
  |         |
  v         v
Continue   Rollback
```

I tested the rollback flow by intentionally making the health probe fail and verifying that Kubernetes returned to the previous working deployment.

---

# 17. How do you know a Kubernetes deployment is healthy?

The CLI checks deployment status including:

* desired replicas
* updated replicas
* ready replicas
* available replicas
* unavailable replicas
* deployed image
* deployment revision

It classifies the deployment as:

```text
HEALTHY
ROLLING OUT
UNHEALTHY
```

For example, if the desired replicas are 2 and updated, ready, and available replicas are all 2, the deployment is considered healthy.

---

# 18. What testing did you implement?

The project currently uses pytest for Python and Kubernetes manifest-related tests.

The tests validate things such as:

* configuration validation
* generated Kubernetes Deployment
* generated Kubernetes Service
* replica configuration
* RollingUpdate configuration
* rollout status handling
* unhealthy deployment handling

The CI pipeline runs the tests automatically.

---

# 19. What does your CI pipeline validate?

The validation job performs:

```text
Python
 ├── py_compile
 └── pytest

Configuration
 └── platform validation

Terraform
 ├── fmt -check
 └── validate

Kubernetes
 └── YAML validation

Docker
 └── image build
```

Only after validation succeeds does the main-branch workflow publish the container image.

---

# 20. How does monitoring work?

The application exposes Prometheus metrics through:

```text
/metrics
```

Prometheus scrapes the application metrics.

cAdvisor provides container-level metrics.

Grafana reads the Prometheus data and provides dashboards.

The current dashboard includes:

* request rate
* health request count
* Prometheus target status
* CPU usage
* memory usage
* running containers

---

# 21. What is the difference between application health and Prometheus target health?

This is an important distinction.

The application's `/health` endpoint tells us whether the application itself responds successfully.

Prometheus `up` indicates whether Prometheus was able to successfully scrape the target.

They are related but not identical.

For example:

```text
Application /health
        |
        v
Application health

Prometheus scrape
        |
        v
Monitoring target health
```

---

# 22. Why monitor both application and container metrics?

Application metrics tell us what the application is doing.

Container metrics tell us how the runtime environment is behaving.

For example:

```text
Application
 └── request rate

Container
 ├── CPU
 ├── memory
 └── container count
```

Looking at both helps correlate application behavior with infrastructure/resource usage.

---

# 23. What would you improve for production?

The current project is a lab/portfolio implementation, so I would make several changes before calling it production-ready.

Potential improvements include:

* Amazon EKS instead of Minikube
* managed database where required
* centralized logging
* secrets management using AWS Secrets Manager or another dedicated solution
* stronger IAM least-privilege policies
* image vulnerability scanning
* policy checks for infrastructure
* deployment approvals for production
* blue/green or canary deployment where appropriate
* remote Terraform state with locking
* automated integration tests
* stronger observability and alerting
* autoscaling
* disaster recovery procedures

I would introduce these based on actual operational requirements rather than adding them simply for complexity.

---

# 24. What is currently implemented versus future scope?

## Implemented

* Python platform CLI
* Terraform infrastructure
* environment-specific configuration
* Docker application
* GHCR image publishing
* immutable Git SHA image tags
* GitHub Actions CI/CD
* AWS OIDC authentication
* EC2 discovery using tags
* AWS Systems Manager deployment
* deployment health validation
* Minikube Kubernetes deployment
* Kubernetes rolling updates
* readiness/liveness probes
* rollout history
* rollback
* pytest tests
* Prometheus
* cAdvisor
* Grafana

## Future scope

* Amazon EKS
* production-grade logging
* vulnerability scanning
* advanced deployment strategies
* autoscaling
* centralized secrets management
* production-grade Terraform remote state
* advanced alerting

---

# 25. Important Interview Honesty

This project is a hands-on Platform Engineering lab.

When discussing it in an interview, I should clearly distinguish between:

* what I implemented and tested myself
* what I understand conceptually
* what I would implement in a production environment

I should not claim that this platform is running in production or that I operated a production EKS environment if that is not true.

A strong answer can still explain the architecture, implementation decisions, trade-offs, failures, testing, and future improvements honestly.

---

# 26. One-Line Project Summary

Built a Python-based Platform Engineering lab integrating Terraform, Docker, Kubernetes, GitHub Actions, GHCR, AWS OIDC, AWS Systems Manager, Prometheus, cAdvisor, and Grafana to automate application validation, immutable image delivery, deployment, health validation, rollback, and observability.
