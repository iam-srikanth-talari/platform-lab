import sys
import subprocess
from pathlib import Path

import yaml
import json

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CLI_DIR = Path(__file__).resolve().parent

sys.path.insert(0, str(CLI_DIR))

# from kubernetes import deploy_to_kubernetes, kubernetes_status
from kubernetes import (
    deploy_to_kubernetes,
    kubernetes_status,
    kubernetes_pod_health,
    kubernetes_service_health,
)

TERRAFORM_DIR = PROJECT_ROOT / "terraform"
ANSIBLE_DIR = PROJECT_ROOT / "ansible"
INVENTORY_FILE = ANSIBLE_DIR / "inventory.ini"

# from kubernetes import deploy_to_kubernetes, kubernetes_status
# from cli.kubernetes import deploy_to_kubernetes, kubernetes_status
# from .kubernetes import deploy_to_kubernetes, kubernetes_status

def load_config(filename):
    with open(filename, "r") as file:
        return yaml.safe_load(file)

def load_environment_config(config):
    environment = config["application"]["environment"]

    environment_file = (
        PROJECT_ROOT
        / "config"
        / "environments"
        / f"{environment}.yaml"
    )

    if not environment_file.exists():
        raise ValueError(
            f"Environment configuration not found: {environment}"
        )

    with open(environment_file, "r") as file:
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
    print()
    print("======================================")
    print("       PLATFORM CONFIGURATION")
    print("======================================")
    print()
    print(f"Application : {config['application']['name']}")
    print(f"Environment : {config['application']['environment']}")
    print(f"Cloud       : {config['infrastructure']['cloud']}")
    print(f"Region      : {config['infrastructure']['region']}")
    print(f"Instance    : {config['infrastructure']['instance_type']}")
    print(f"Replicas    : {config['kubernetes']['replicas']}")


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

def terraform_workspace(environment):
    print()
    print(f"Selecting Terraform workspace: {environment}")

    result = subprocess.run(
        ["terraform", "workspace", "select", environment],
        cwd=TERRAFORM_DIR,
        text=True
    )

    if result.returncode != 0:
        print(f"Workspace '{environment}' does not exist.")
        sys.exit(1)

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
    environment = config["application"]["environment"]

    print()
    print("======================================")
    print("       DESTRUCTIVE OPERATION")
    print("======================================")
    print()
    print(f"Environment : {environment}")
    print(f"Application : {config['application']['name']}")
    print()

    confirmation = input(
        f"Type '{environment}' to confirm destruction: "
    )

    if confirmation != environment:
        print()
        print("Destruction cancelled.")
        return

    print()
    print("Destroying Terraform infrastructure...")

    run_command(
        [
            "terraform",
            "destroy",
            "-auto-approve"
        ] + terraform_variables(config)
    )


def terraform_status():
    print()
    print("Terraform outputs:")

    run_command(["terraform", "output"])

def terraform_output(name):
    result = subprocess.run(
        ["terraform", "output", "-raw", name],
        cwd=TERRAFORM_DIR,
        text=True,
        capture_output=True
    )

    if result.returncode != 0:
        print("Failed to get Terraform output.")
        print(result.stderr)
        sys.exit(result.returncode)

    return result.stdout.strip()

def generate_ansible_inventory():
    public_ip = terraform_output("instance_public_ip")

    inventory = f"""[platform]
demo-app ansible_host={public_ip} ansible_user=ec2-user ansible_ssh_private_key_file=/home/tasrikan/.ssh/platform-lab
"""

    ANSIBLE_DIR.mkdir(exist_ok=True)

    with open(INVENTORY_FILE, "w") as file:
        file.write(inventory)

    print()
    print("Ansible inventory generated:")
    print(INVENTORY_FILE)
    print()
    print(inventory)

def run_ansible(playbook, config):
    playbook_file = ANSIBLE_DIR / playbook

    wsl_inventory = "/mnt/c/Users/tasrikan/platform-lab/ansible/inventory.ini"
    wsl_playbook = f"/mnt/c/Users/tasrikan/platform-lab/ansible/{playbook_file.name}"

    app_image = config["deployment"]["image"]

    command = [
        "wsl",
        "-d",
        "Ubuntu",
        "--",
        "ansible-playbook",
        "-i",
        wsl_inventory,
        wsl_playbook,
        "-e",
        f"platform_image={app_image}",
    ]

    result = subprocess.run(command, cwd=PROJECT_ROOT)

    if result.returncode != 0:
        raise RuntimeError("Ansible execution failed")

def execute(command, config):
    validate_config(config)

    # if command == "plan":
    #     terraform_init()
    #     terraform_plan(config)
    if command == "plan":
        terraform_init()
        terraform_workspace(config["application"]["environment"])
        terraform_plan(config)

    elif command == "apply":
        terraform_init()
        terraform_workspace(config["application"]["environment"])
        terraform_apply(config)

    elif command == "destroy":
        terraform_init()
        terraform_workspace(config["application"]["environment"])
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
        print("[1/6] Provisioning infrastructure...")
        terraform_apply(config)

        print()
        print("[2/6] Generating Ansible inventory...")
        generate_ansible_inventory()

        print()
        print("[3/6] Configuring EC2 with Ansible...")
        run_ansible("playbook.yml", config)

        print()
        print("[4/6] Generating Kubernetes manifests...")
        print("Kubernetes manifests will be generated during deployment.")

        print()
        print("[5/6] Deploying application to Kubernetes...")
        deploy_to_kubernetes(config)

        print()
        print("[6/6] Verifying Kubernetes deployment...")
        kubernetes_status(config)

        print()
        print("Checking pod health...")

        if not kubernetes_pod_health(config):
            print()
            print("======================================")
            print("        DEPLOYMENT FAILED")
            print("======================================")
            sys.exit(1)

        print()
        print("Pod health: PASSED")

        print()
        print("Checking service health...")

        if not kubernetes_service_health(config):
            print()
            print("======================================")
            print("        DEPLOYMENT FAILED")
            print("======================================")
            sys.exit(1)

        print()
        print("Service health: PASSED")

        print()
        print("======================================")
        print("       DEPLOYMENT SUCCESSFUL")
        print("======================================")

    
    elif command == "k8s-status":
        kubernetes_status(config)


    elif command == "deploy":
        terraform_init()

        terraform_workspace(
            config["application"]["environment"]
        )

        print()
        print("======================================")
        print("       PLATFORM DEPLOYMENT")
        print("======================================")

        print()
        print("[1/6] Provisioning infrastructure...")
        terraform_apply(config)

        print()
        print("[2/6] Generating Ansible inventory...")
        generate_ansible_inventory()

        print()
        print("[3/6] Configuring EC2 with Ansible...")
        run_ansible("playbook.yml")

        print()
        print("[4/6] Generating Kubernetes manifests...")
        print("Kubernetes manifests will be generated during deployment.")

        print()
        print("[5/6] Deploying application to Kubernetes...")
        deploy_to_kubernetes(config)

        print()
        print("[6/6] Verifying Kubernetes deployment...")
        kubernetes_status(config)

        print()
        print("Checking pod health...")

        if not kubernetes_pod_health(config):
            print()
            print("======================================")
            print("        DEPLOYMENT FAILED")
            print("======================================")
            sys.exit(1)

        print("Pod health: PASSED")

        print()
        print("Checking service health...")

        if not kubernetes_service_health(config):
            print()
            print("======================================")
            print("        DEPLOYMENT FAILED")
            print("======================================")
            sys.exit(1)

        print("Service health: PASSED")

        print()
        print("======================================")
        print("       DEPLOYMENT SUCCESSFUL")
        print("======================================")

    elif command == "validate":
        print()
        print("Configuration validation: PASSED")
        print()
        print("======================================")
        print("       PLATFORM CONFIGURATION")
        print("======================================")
        print()
        print(f"Application : {config['application']['name']}")
        print(f"Environment : {config['application']['environment']}")
        print(f"Cloud       : {config['infrastructure']['cloud']}")
        print(f"Region      : {config['infrastructure']['region']}")
        print(f"Instance    : {config['infrastructure']['instance_type']}")
        print(f"Replicas    : {config['kubernetes']['replicas']}")

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
    if len(sys.argv) != 5 or sys.argv[3] != "--env":
        print("Usage: python cli/platform.py <command> <config.yaml> --env <environment>")
        print()
        print("Commands:")
        print("  create")
        print("  plan")
        print("  apply")
        print("  destroy")
        print("  status")
        print("  deploy")
        print("  k8s-status")
        sys.exit(1)

    command = sys.argv[1]
    config_file = sys.argv[2]
    environment = sys.argv[4]

    try:
        config = load_config(config_file)

        config["application"]["environment"] = environment

        environment_config = load_environment_config(config)

        config["infrastructure"]["instance_type"] = (
            environment_config["infrastructure"]["instance_type"]
        )

        config["kubernetes"]["replicas"] = (
            environment_config["kubernetes"]["replicas"]
        )

        execute(command, config)

    except ValueError as error:
        print(f"Configuration error: {error}")
        sys.exit(1)

if __name__ == "__main__":
    main()
