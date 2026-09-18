import sys
import subprocess
from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CLI_DIR = Path(__file__).resolve().parent

sys.path.insert(0, str(CLI_DIR))

from kubernetes import deploy_to_kubernetes, kubernetes_status

TERRAFORM_DIR = PROJECT_ROOT / "terraform"

# from kubernetes import deploy_to_kubernetes, kubernetes_status
# from cli.kubernetes import deploy_to_kubernetes, kubernetes_status
# from .kubernetes import deploy_to_kubernetes, kubernetes_status

def load_config(filename):
    with open(filename, "r") as file:
        return yaml.safe_load(file)

def validate_config(config):
    required_sections = [
        "application",
        "infrastructure",
        "kubernetes",
        "deployment"
    ]

    for section in required_sections:
        if section not in config:
            raise ValueError(f"Missing required section: {section}")

    required_application = ["name", "environment"]
    for field in required_application:
        if field not in config["application"]:
            raise ValueError(
                f"Missing application field: {field}"
            )

    required_infrastructure = [
        "cloud",
        "region",
        "instance_type"
    ]

    for field in required_infrastructure:
        if field not in config["infrastructure"]:
            raise ValueError(
                f"Missing infrastructure field: {field}"
            )

    if config["infrastructure"]["cloud"] != "aws":
        raise ValueError("Currently only AWS is supported.")

    if config["kubernetes"]["replicas"] < 1:
        raise ValueError("Kubernetes replicas must be at least 1")

    print("Configuration validation: PASSED")


def run_command(command):
    print()
    print(f"Running: {' '.join(command)}")
    print()

    result = subprocess.run(
        command,
        cwd=TERRAFORM_DIR,
        text=True
    )

    if result.returncode != 0:
        print("Command failed.")
        sys.exit(result.returncode)


def terraform_variables(config):
    app = config["application"]
    infra = config["infrastructure"]

    return [
        f"-var=aws_region={infra['region']}",
        f"-var=instance_type={infra['instance_type']}",
        f"-var=application_name={app['name']}",
        f"-var=environment={app['environment']}",
    ]


def terraform_init():
    print()
    print("Initializing Terraform...")
    run_command(["terraform", "init"])


def terraform_plan(config):
    print()
    print("Creating Terraform plan...")

    run_command(
        ["terraform", "plan"] + terraform_variables(config)
    )


def terraform_apply(config):
    print()
    print("Applying Terraform infrastructure...")

    run_command(
        ["terraform", "apply", "-auto-approve"]
        + terraform_variables(config)
    )


def terraform_destroy(config):
    print()
    print("Destroying Terraform infrastructure...")

    run_command(
        ["terraform", "destroy", "-auto-approve"]
        + terraform_variables(config)
    )


def terraform_status():
    print()
    print("Terraform outputs:")

    run_command(["terraform", "output"])


def execute(command, config):
    validate_config(config)

    if command == "plan":
        terraform_init()
        terraform_plan(config)

    elif command == "apply":
        terraform_init()
        terraform_apply(config)

    elif command == "destroy":
        terraform_init()
        terraform_destroy(config)

    elif command == "status":
        terraform_status()

    elif command == "create":
        terraform_init()

        print()
        print("======================================")
        print("       PLATFORM DEPLOYMENT")
        print("======================================")

        print()
        print("[1/4] Provisioning infrastructure...")
        terraform_apply(config)

        print()
        print("[2/4] Generating Kubernetes manifests...")

        print("Kubernetes manifests will be generated during deployment.")

        print()
        print("[3/4] Deploying application...")
        deploy_to_kubernetes(config)

        print()
        print("[4/4] Verifying deployment...")
        kubernetes_status(config)

        print()
        print("======================================")
        print("       DEPLOYMENT COMPLETED")
        print("======================================")

    elif command == "deploy":
        deploy_to_kubernetes(config)

    elif command == "k8s-status":
        kubernetes_status(config)

    else:
        print(f"Unknown command: {command}")
        print()
        print("Available commands:")
        print("  create")
        print("  plan")
        print("  apply")
        print("  destroy")
        print("  status")
        print("  deploy")
        print("  k8s-status")
        sys.exit(1)


def main():
    if len(sys.argv) != 3:
        print("Usage: python cli/platform.py <command> <config.yaml>")
        print()
        print("Commands:")
        print("  create")
        print("  plan")
        print("  apply")
        print("  destroy")
        print("  status")
        sys.exit(1)

    command = sys.argv[1]
    config_file = sys.argv[2]

    config = load_config(config_file)

    try:
        execute(command, config)
    except ValueError as error:
        print(f"Configuration error: {error}")
        sys.exit(1)


if __name__ == "__main__":
    main()