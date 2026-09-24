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

    test_image = (
        "ghcr.io/iam-srikanth-talari/platform-lab-app:test123456"
    )

    config["deployment"]["image"] = test_image

    deployment_file, _ = kubernetes_cli.generate_manifests(config)

    with open(deployment_file, "r") as file:
        deployment = yaml.safe_load(file)
    assert deployment["kind"] == "Deployment"
    assert deployment["metadata"]["name"] == "demo-app"
    expected_tag = test_image.split(":")[-1][:8]

    assert (
        deployment["metadata"]["annotations"]["kubernetes.io/change-cause"]
        == f"Deploy image {expected_tag}"
    )
    # assert deployment["spec"]["replicas"] == 3
    assert deployment["spec"]["replicas"] == config["kubernetes"]["replicas"]
    assert deployment["spec"]["strategy"]["type"] == "RollingUpdate"
    assert deployment["spec"]["strategy"]["rollingUpdate"]["maxUnavailable"] == 0
    assert deployment["spec"]["strategy"]["rollingUpdate"]["maxSurge"] == 1


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



def test_kubernetes_status_rolling_out(monkeypatch, capsys):
    kubernetes_cli = load_kubernetes_module()
    config = load_config()

    class MockResult:
        returncode = 0
        stdout = (
            "2,1,1,1,1,"
            "ghcr.io/iam-srikanth-talari/platform-lab-app:test123456,"
            "12"
        )

    def mock_run(*args, **kwargs):
        return MockResult()

    monkeypatch.setattr(
        kubernetes_cli.subprocess,
        "run",
        mock_run,
    )

    kubernetes_cli.kubernetes_status(config)

    output = capsys.readouterr().out

    assert "Replicas    : 2" in output
    assert "Updated     : 1" in output
    assert "Ready       : 1" in output
    assert "Available   : 1" in output
    assert "Revision    : 12" in output
    assert "Status      : ROLLING OUT" in output



def test_kubernetes_status_unhealthy(monkeypatch, capsys):
    kubernetes_cli = load_kubernetes_module()
    config = load_config()

    class MockResult:
        returncode = 0
        stdout = (
            "2,2,0,0,2,"
            "ghcr.io/iam-srikanth-talari/platform-lab-app:test123456,"
            "13"
        )

    def mock_run(*args, **kwargs):
        return MockResult()

    monkeypatch.setattr(
        kubernetes_cli.subprocess,
        "run",
        mock_run,
    )

    kubernetes_cli.kubernetes_status(config)

    output = capsys.readouterr().out

    assert "Replicas    : 2" in output
    assert "Updated     : 2" in output
    assert "Ready       : 0" in output
    assert "Available   : 0" in output
    assert "Revision    : 13" in output
    assert "Status      : UNHEALTHY" in output