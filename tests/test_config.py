import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]

if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import importlib.util
import sys
from pathlib import Path

import yaml


PROJECT_ROOT = Path(__file__).resolve().parent.parent
CLI_DIR = PROJECT_ROOT / "cli"
PLATFORM_FILE = CLI_DIR / "platform.py"
KUBERNETES_FILE = CLI_DIR / "kubernetes.py"


def load_platform_module():
    # Load kubernetes.py first
    kubernetes_spec = importlib.util.spec_from_file_location(
        "cli.kubernetes",
        KUBERNETES_FILE
    )

    kubernetes_module = importlib.util.module_from_spec(kubernetes_spec)
    sys.modules["cli.kubernetes"] = kubernetes_module
    kubernetes_spec.loader.exec_module(kubernetes_module)

    # Load platform.py
    platform_spec = importlib.util.spec_from_file_location(
        "cli.platform",
        PLATFORM_FILE
    )

    platform_module = importlib.util.module_from_spec(platform_spec)
    sys.modules["cli.platform"] = platform_module
    platform_spec.loader.exec_module(platform_module)

    return platform_module


def load_config():
    config_path = PROJECT_ROOT / "config" / "app.yaml"

    with open(config_path, "r") as file:
        return yaml.safe_load(file)


def test_valid_config():
    platform_cli = load_platform_module()
    config = load_config()

    platform_cli.validate_config(config)


def test_invalid_replicas():
    platform_cli = load_platform_module()
    config = load_config()

    config["kubernetes"]["replicas"] = 0

    try:
        platform_cli.validate_config(config)
    except ValueError:
        return

    assert False, "Expected ValueError for replicas = 0"