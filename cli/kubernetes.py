from pathlib import Path
import subprocess
import yaml


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

          ports:
            - containerPort: {port}
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

    subprocess.run(
        [
            "kubectl",
            "rollout",
            "status",
            f"deployment/{app_name}"
        ],
        check=True
    )

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