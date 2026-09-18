import importlib.util
from pathlib import Path

import yaml


PROJECT_ROOT = Path(__file__).resolve().parent.parent
KUBERNETES_FILE = PROJECT_ROOT / "cli" / "kubernetes.py"


def load_kubernetes_module():
    spec = importlib.util.spec_from_file_location(
        "kubernetes_cli",
        KUBERNETES_FILE
    )

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    return module


def load_config():
    config_path = PROJECT_ROOT / "config" / "app.yaml"

    with open(config_path, "r") as file:
        return yaml.safe_load(file)


def test_generated_deployment():
    kubernetes_cli = load_kubernetes_module()
    config = load_config()

    deployment_file, _ = kubernetes_cli.generate_manifests(config)

    with open(deployment_file, "r") as file:
        deployment = yaml.safe_load(file)

    assert deployment["kind"] == "Deployment"
    assert deployment["metadata"]["name"] == "demo-app"
    # assert deployment["spec"]["replicas"] == 3
    assert deployment["spec"]["replicas"] == config["kubernetes"]["replicas"]


def test_generated_service():
    kubernetes_cli = load_kubernetes_module()
    config = load_config()

    _, service_file = kubernetes_cli.generate_manifests(config)

    with open(service_file, "r") as file:
        service = yaml.safe_load(file)

    assert service["kind"] == "Service"
    assert service["metadata"]["name"] == "demo-app-service"
    assert service["spec"]["ports"][0]["port"] == 8000
    assert service["spec"]["ports"][0]["targetPort"] == 8000