from pathlib import Path
import subprocess
import yaml
import json


PROJECT_ROOT = Path(__file__).resolve().parent.parent
KUBERNETES_DIR = PROJECT_ROOT / "kubernetes"

def generate_manifests(config):
    app = config["application"]
    k8s = config["kubernetes"]
    deployment = config["deployment"]

    app_name = app["name"]
    replicas = k8s["replicas"]
    port = k8s["port"]
    image = deployment["image"]

    deployment_yaml = f"""apiVersion: apps/v1
kind: Deployment

metadata:
  name: {app_name}

spec:
  replicas: {replicas}

  selector:
    matchLabels:
      app: {app_name}

  template:
    metadata:
      labels:
        app: {app_name}

    spec:
      containers:
        - name: {app_name}
          image: {image}
          imagePullPolicy: Always

          ports:
            - containerPort: {port}
          readinessProbe:
            httpGet:
              path: /health
              port: {port}
            initialDelaySeconds: 5
            periodSeconds: 5

          livenessProbe:
            httpGet:
              path: /health
              port: {port}
            initialDelaySeconds: 10
            periodSeconds: 10
          envFrom:
            - secretRef:
                name: {app_name}-secret

          resources:
            requests:
              cpu: "100m"
              memory: "128Mi"

            limits:
              cpu: "500m"
              memory: "256Mi"
"""

    service_yaml = f"""apiVersion: v1
kind: Service

metadata:
  name: {app_name}-service

spec:
  selector:
    app: {app_name}

  ports:
    - protocol: TCP
      port: {port}
      targetPort: {port}

  type: NodePort
"""

    deployment_file = KUBERNETES_DIR / "deployment.generated.yaml"
    service_file = KUBERNETES_DIR / "service.generated.yaml"

    deployment_file.write_text(deployment_yaml)
    service_file.write_text(service_yaml)

    return deployment_file, service_file

def deploy_to_kubernetes(config):
    deployment_file, service_file = generate_manifests(config)

    app_name = config["application"]["name"]

    print()
    print("Generated Kubernetes manifests:")
    print(deployment_file)
    print(service_file)

    print()
    print("Deploying application to Kubernetes...")

    secret_file = KUBERNETES_DIR / "secret.yaml"

    subprocess.run(
        ["kubectl", "apply", "-f", str(secret_file)],
        check=True
    )

    subprocess.run(
        ["kubectl", "apply", "-f", str(deployment_file)],
        check=True
    )

    subprocess.run(
        ["kubectl", "apply", "-f", str(service_file)],
        check=True
    )

    print()
    print("Waiting for deployment rollout...")

    try:
        subprocess.run(
            [
                "kubectl",
                "rollout",
                "status",
                f"deployment/{app_name}",
                "--timeout=120s",
            ],
            check=True,
        )

    except subprocess.CalledProcessError:
        print("\nDeployment rollout failed.")
        print("Rolling back to previous revision...")

        subprocess.run(
            ["kubectl", "rollout", "undo", f"deployment/{app_name}"],
            check=True,
        )

        subprocess.run(
            [
                "kubectl",
                "rollout",
                "status",
                f"deployment/{app_name}",
                "--timeout=120s",
            ],
            check=True,
        )

        print("Rollback completed successfully.")
        raise

    print()
    print("Kubernetes deployment completed successfully.")
    print()
    print("Application URL:")

    result = subprocess.run(
        [
            "minikube",
            "ip"
        ],
        capture_output=True,
        text=True,
        check=True
    )

    minikube_ip = result.stdout.strip()

    result = subprocess.run(
        [
            "kubectl",
            "get",
            "service",
            f"{app_name}-service",
            "-o",
            "jsonpath={.spec.ports[0].nodePort}"
        ],
        capture_output=True,
        text=True,
        check=True
    )

    node_port = result.stdout.strip()

    print(f"http://{minikube_ip}:{node_port}")

def kubernetes_pod_health(config):

    app_name = config["application"]["name"]

    print()
    print("Checking pod health...")

    result = subprocess.run(
        [
            "kubectl",
            "get",
            "pods",
            "-l",
            f"app={app_name}",
            "-o",
            "json"
        ],
        capture_output=True,
        text=True
    )

    if result.returncode != 0:
        print("Pod Health : FAILED")
        return False

    data = json.loads(result.stdout)
    pods = data.get("items", [])

    if not pods:
        print("Pod Health : FAILED")
        print("Reason     : No pods found")
        return False

    healthy = True

    for pod in pods:

        pod_name = pod["metadata"]["name"]
        phase = pod["status"].get("phase", "Unknown")

        container_statuses = pod["status"].get(
            "containerStatuses",
            []
        )

        reason = "Unknown"
        message = ""

        if container_statuses:

            container = container_statuses[0]

            ready = container.get("ready", False)
            restart_count = container.get("restartCount", 0)

            waiting = container.get("state", {}).get("waiting")

            if waiting:
                reason = waiting.get("reason", "Unknown")
                message = waiting.get("message", "")
            else:
                reason = container.get(
                    "state", {}
                ).get(
                    "running", {}
                ).get(
                    "reason", "Running"
                )

        else:
            ready = False
            restart_count = 0

        print()
        print(f"Pod        : {pod_name}")
        print(f"Status     : {phase}")
        print(f"Ready      : {ready}")
        print(f"Restarts   : {restart_count}")
        print(f"Reason     : {reason}")

        if message:
            print(f"Message    : {message}")

        if phase != "Running" or not ready:
            healthy = False

    print()

    if healthy:
        print("Pod Health : HEALTHY")
    else:
        print("Pod Health : UNHEALTHY")

    return healthy

def kubernetes_service_health(config):

    app_name = config["application"]["name"]
    service_name = f"{app_name}-service"

    print()
    print("Checking service health...")

    result = subprocess.run(
        [
            "kubectl",
            "get",
            "service",
            service_name,
            "-o",
            "json"
        ],
        capture_output=True,
        text=True
    )

    if result.returncode != 0:
        print("Service Health : FAILED")
        print("Reason         : Service not found")
        return False

    data = json.loads(result.stdout)

    service_type = data["spec"].get("type", "Unknown")
    ports = data["spec"].get("ports", [])

    if not ports:
        print("Service Health : FAILED")
        print("Reason         : No ports configured")
        return False

    node_port = ports[0].get("nodePort")

    print()
    print(f"Service        : {service_name}")
    print(f"Type           : {service_type}")
    print(f"NodePort       : {node_port}")

    if service_type != "NodePort" or not node_port:
        print()
        print("Service Health : UNHEALTHY")
        return False

    print()
    print("Service Health : HEALTHY")

    return True

def kubernetes_status(config):
    app_name = config["application"]["name"]

    print()
    print("======================================")
    print("          PLATFORM STATUS")
    print("======================================")
    print()

    print(f"Application : {app_name}")

    result = subprocess.run(
        [
            "kubectl",
            "get",
            "deployment",
            app_name,
            "-o",
            "jsonpath={.spec.replicas},{.status.readyReplicas},{.status.availableReplicas}"
        ],
        capture_output=True,
        text=True
    )

    if result.returncode != 0:
        print("Status      : NOT DEPLOYED")
        return

    values = result.stdout.strip().split(",")

    replicas = int(values[0])
    ready = int(values[1] or 0)
    available = int(values[2] or 0)

    print(f"Replicas    : {replicas}")
    print(f"Ready       : {ready}")
    print(f"Available   : {available}")

    if ready == replicas and available == replicas:
        print()
        print("Status      : HEALTHY")
    else:
        print()
        print("Status      : UNHEALTHY")

def kubernetes_rollout_history(config):
    app_name = config["application"]["name"]

    print()
    print("======================================")
    print("       DEPLOYMENT HISTORY")
    print("======================================")
    print()
    print(f"Application : {app_name}")
    print()

    result = subprocess.run(
        ["kubectl", "rollout", "history", f"deployment/{app_name}"],
        capture_output=True,
        text=True,
        check=True,
    )

    print(result.stdout)

    revision_result = subprocess.run(
        [
            "kubectl",
            "get",
            "deployment",
            app_name,
            "-o",
            "jsonpath={.metadata.annotations.deployment\\.kubernetes\\.io/revision}",
        ],
        capture_output=True,
        text=True,
        check=True,
    )

    current_revision = revision_result.stdout.strip()

    print(f"Current revision : {current_revision}")