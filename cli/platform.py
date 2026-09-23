import sys
import subprocess
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]

if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from cli.ssm import deploy_with_ssm

import yaml

# ---------------------------------------------------------
# Project paths
# ---------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CLI_DIR = Path(__file__).resolve().parent

# Allow importing cli/kubernetes.py when running:
# python cli/platform.py ...
sys.path.insert(0, str(CLI_DIR))

from kubernetes import (
    deploy_to_kubernetes,
    kubernetes_status,
    kubernetes_pod_health,
    kubernetes_service_health,
)


TERRAFORM_DIR = PROJECT_ROOT / "terraform"
ANSIBLE_DIR = PROJECT_ROOT / "ansible"
INVENTORY_FILE = ANSIBLE_DIR / "inventory.ini"


# ---------------------------------------------------------
# Configuration
# ---------------------------------------------------------

def load_config(filename):
    """Load the main platform configuration."""
    with open(filename, "r") as file:
        return yaml.safe_load(file)


def load_environment_config(config):
    """Load environment-specific configuration."""
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


def apply_environment_config(config, environment_config):
    """Override environment-specific values."""
    config["infrastructure"]["instance_type"] = (
        environment_config["infrastructure"]["instance_type"]
    )

    config["kubernetes"]["replicas"] = (
        environment_config["kubernetes"]["replicas"]
    )


# ---------------------------------------------------------
# Validation
# ---------------------------------------------------------

def validate_config(config):
    """Validate platform configuration."""

    required_sections = [
        "application",
        "infrastructure",
        "kubernetes",
        "deployment",
    ]

    for section in required_sections:
        if section not in config:
            raise ValueError(
                f"Missing required section: {section}"
            )

    # Application
    required_application = [
        "name",
        "environment",
    ]

    for field in required_application:
        if field not in config["application"]:
            raise ValueError(
                f"Missing application field: {field}"
            )

    # Infrastructure
    required_infrastructure = [
        "cloud",
        "region",
        "instance_type",
    ]

    for field in required_infrastructure:
        if field not in config["infrastructure"]:
            raise ValueError(
                f"Missing infrastructure field: {field}"
            )

    # Kubernetes
    required_kubernetes = [
        "replicas",
        "port",
    ]

    for field in required_kubernetes:
        if field not in config["kubernetes"]:
            raise ValueError(
                f"Missing Kubernetes field: {field}"
            )

    # Deployment
    if "image" not in config["deployment"]:
        raise ValueError(
            "Missing deployment image"
        )

    # Supported cloud
    if config["infrastructure"]["cloud"] != "aws":
        raise ValueError(
            "Currently only AWS is supported."
        )

    # Replica validation
    if config["kubernetes"]["replicas"] < 1:
        raise ValueError(
            "Kubernetes replicas must be at least 1"
        )

    # Port validation
    port = config["kubernetes"]["port"]

    if not isinstance(port, int):
        raise ValueError(
            "Kubernetes port must be an integer"
        )

    if port < 1 or port > 65535:
        raise ValueError(
            "Kubernetes port must be between 1 and 65535"
        )

    print()
    print("Configuration validation: PASSED")
    print()
    print("======================================")
    print("       PLATFORM CONFIGURATION")
    print("======================================")
    print()
    print(
        f"Application : "
        f"{config['application']['name']}"
    )
    print(
        f"Environment : "
        f"{config['application']['environment']}"
    )
    print(
        f"Cloud       : "
        f"{config['infrastructure']['cloud']}"
    )
    print(
        f"Region      : "
        f"{config['infrastructure']['region']}"
    )
    print(
        f"Instance    : "
        f"{config['infrastructure']['instance_type']}"
    )
    print(
        f"Replicas    : "
        f"{config['kubernetes']['replicas']}"
    )
    print(
        f"Port        : "
        f"{config['kubernetes']['port']}"
    )
    print(
        f"Image       : "
        f"{config['deployment']['image']}"
    )

    return True


# ---------------------------------------------------------
# Terraform
# ---------------------------------------------------------

def run_terraform_command(command):
    """Run a Terraform command inside terraform directory."""

    print()
    print(
        f"Running: {' '.join(command)}"
    )
    print()

    result = subprocess.run(
        command,
        cwd=TERRAFORM_DIR,
        text=True,
    )

    if result.returncode != 0:
        print()
        print("Terraform command failed.")
        sys.exit(result.returncode)

    return result


def terraform_init():
    """Initialize Terraform."""

    print()
    print("Initializing Terraform...")

    run_terraform_command(
        ["terraform", "init"]
    )


def terraform_workspace(environment):
    """Select Terraform workspace."""

    print()
    print(
        f"Selecting Terraform workspace: "
        f"{environment}"
    )

    result = subprocess.run(
        [
            "terraform",
            "workspace",
            "select",
            environment,
        ],
        cwd=TERRAFORM_DIR,
        text=True,
    )

    if result.returncode != 0:
        print()
        print(
            f"Workspace '{environment}' does not exist."
        )
        print()
        print(
            "Create it with:"
        )
        print(
            f"terraform workspace new {environment}"
        )

        sys.exit(1)


def terraform_variables(config):
    """Build Terraform variables from platform config."""

    application = config["application"]
    infrastructure = config["infrastructure"]

    return [
        f"-var=aws_region="
        f"{infrastructure['region']}",

        f"-var=instance_type="
        f"{infrastructure['instance_type']}",

        f"-var=application_name="
        f"{application['name']}",

        f"-var=environment="
        f"{application['environment']}",
    ]


def terraform_plan(config):
    """Create Terraform execution plan."""

    print()
    print("Creating Terraform plan...")

    run_terraform_command(
        [
            "terraform",
            "plan",
        ]
        + terraform_variables(config)
    )


def terraform_apply(config):
    """Create/update AWS infrastructure."""

    print()
    print("Applying Terraform infrastructure...")

    run_terraform_command(
        [
            "terraform",
            "apply",
            "-auto-approve",
        ]
        + terraform_variables(config)
    )


def terraform_destroy(config):
    """Destroy AWS infrastructure."""

    environment = (
        config["application"]["environment"]
    )

    application_name = (
        config["application"]["name"]
    )

    print()
    print("======================================")
    print("       DESTRUCTIVE OPERATION")
    print("======================================")
    print()
    print(
        f"Environment : {environment}"
    )
    print(
        f"Application : {application_name}"
    )
    print()

    confirmation = input(
        f"Type '{environment}' "
        f"to confirm destruction: "
    )

    if confirmation != environment:
        print()
        print("Destruction cancelled.")
        return

    print()
    print("Destroying Terraform infrastructure...")

    run_terraform_command(
        [
            "terraform",
            "destroy",
            "-auto-approve",
        ]
        + terraform_variables(config)
    )

    print()
    print("======================================")
    print("       INFRASTRUCTURE DESTROYED")
    print("======================================")


def terraform_output(name):
    """Read a Terraform output value."""

    result = subprocess.run(
        [
            "terraform",
            "output",
            "-raw",
            name,
        ],
        cwd=TERRAFORM_DIR,
        text=True,
        capture_output=True,
    )

    if result.returncode != 0:
        print()
        print(
            f"Failed to get Terraform output: {name}"
        )
        print()

        if result.stderr:
            print(result.stderr)

        sys.exit(result.returncode)

    return result.stdout.strip()


def terraform_status():
    """Display Terraform outputs."""

    print()
    print("======================================")
    print("       TERRAFORM STATUS")
    print("======================================")

    result = subprocess.run(
        [
            "terraform",
            "output",
        ],
        cwd=TERRAFORM_DIR,
        text=True,
    )

    if result.returncode != 0:
        print()
        print(
            "Terraform status could not be retrieved."
        )
        sys.exit(result.returncode)


# ---------------------------------------------------------
# Ansible
# ---------------------------------------------------------

def generate_ansible_inventory():
    """Generate Ansible inventory from Terraform output."""

    print()
    print(
        "Generating Ansible inventory..."
    )

    public_ip = terraform_output(
        "instance_public_ip"
    )

    inventory = f"""[platform]

demo-app ansible_host={public_ip} ansible_user=ec2-user ansible_ssh_private_key_file=/home/tasrikan/.ssh/platform-lab

"""

    ANSIBLE_DIR.mkdir(
        exist_ok=True
    )

    with open(
        INVENTORY_FILE,
        "w",
    ) as file:
        file.write(inventory)

    print()
    print(
        "Ansible inventory generated:"
    )
    print(INVENTORY_FILE)

    print()
    print(inventory)

    return INVENTORY_FILE


def run_ansible(playbook, config):
    """Run Ansible playbook through WSL."""

    playbook_file = (
        ANSIBLE_DIR / playbook
    )

    if not playbook_file.exists():
        raise FileNotFoundError(
            f"Ansible playbook not found: "
            f"{playbook_file}"
        )

    wsl_inventory = (
        "/mnt/c/Users/tasrikan/"
        "platform-lab/ansible/inventory.ini"
    )

    wsl_playbook = (
        "/mnt/c/Users/tasrikan/"
        f"platform-lab/ansible/{playbook_file.name}"
    )

    app_image = (
        config["deployment"]["image"]
    )

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

    print()
    print(
        "Running Ansible..."
    )
    print()

    result = subprocess.run(
        command,
        cwd=PROJECT_ROOT,
    )

    if result.returncode != 0:
        print()
        print(
            "Ansible execution failed."
        )
        raise RuntimeError(
            "Ansible execution failed"
        )

    print()
    print(
        "Ansible configuration completed successfully."
    )


# ---------------------------------------------------------
# Kubernetes verification
# ---------------------------------------------------------

def verify_kubernetes(config):
    """Verify Kubernetes deployment, pods and service."""

    print()
    print("======================================")
    print("       KUBERNETES VERIFICATION")
    print("======================================")

    print()
    print("Checking deployment status...")

    kubernetes_status(config)

    print()
    print("Checking pod health...")

    pod_healthy = (
        kubernetes_pod_health(config)
    )

    if not pod_healthy:
        print()
        print("======================================")
        print("        DEPLOYMENT FAILED")
        print("======================================")

        sys.exit(1)

    print()
    print("Pod health: PASSED")

    print()
    print("Checking service health...")

    service_healthy = (
        kubernetes_service_health(config)
    )

    if not service_healthy:
        print()
        print("======================================")
        print("        DEPLOYMENT FAILED")
        print("======================================")

        sys.exit(1)

    print()
    print("Service health: PASSED")

    print()
    print("======================================")
    print("       KUBERNETES HEALTHY")
    print("======================================")


# ---------------------------------------------------------
# Full platform deployment
# ---------------------------------------------------------

def deploy_full(config):
    """Run complete platform deployment."""

    environment = (
        config["application"]["environment"]
    )

    print()
    print("======================================")
    print("       PLATFORM DEPLOYMENT")
    print("======================================")
    print()
    print(
        f"Environment : {environment}"
    )
    print(
        f"Application : "
        f"{config['application']['name']}"
    )

    # -----------------------------------------------------
    # Stage 1
    # -----------------------------------------------------

    print()
    print("[1/6] Initializing Terraform...")

    terraform_init()

    terraform_workspace(
        environment
    )

    # -----------------------------------------------------
    # Stage 2
    # -----------------------------------------------------

    print()
    print(
        "[2/6] Provisioning AWS infrastructure..."
    )

    terraform_apply(config)

    # -----------------------------------------------------
    # Stage 3
    # -----------------------------------------------------

    print()
    print(
        "[3/6] Deploying application to EC2 with AWS SSM..."
    )

    instance_id = terraform_output(
        "instance_id"
    )

    region = config["infrastructure"]["region"]

    image = config["deployment"]["image"]

    deploy_with_ssm(
        instance_id,
        region,
        image,
    )
    # -----------------------------------------------------
    # Stage 4
    # -----------------------------------------------------

    print()
    print(
        "[4/6] Generating Kubernetes manifests..."
    )

    print(
        "Kubernetes manifests will be generated "
        "during deployment."
    )

    # -----------------------------------------------------
    # Stage 5
    # -----------------------------------------------------

    print()
    print(
        "[5/6] Deploying application to Kubernetes..."
    )

    deploy_to_kubernetes(config)

    # -----------------------------------------------------
    # Stage 6
    # -----------------------------------------------------

    print()
    print(
        "[6/6] Verifying Kubernetes deployment..."
    )

    verify_kubernetes(config)

    # -----------------------------------------------------
    # Success
    # -----------------------------------------------------

    print()
    print("======================================")
    print("       DEPLOYMENT SUCCESSFUL")
    print("======================================")
    print()
    print(
        "Platform deployment completed successfully."
    )


# ---------------------------------------------------------
# Command execution
# ---------------------------------------------------------

def execute(command, config, image_override=None):
    """Execute requested platform command."""

    if image_override:
        config["deployment"]["image"] = image_override

    if command == "deploy" and not config["deployment"]["image"]:
        raise ValueError(
            "Deployment image is required. "
            "Use --image <immutable-image>"
        )

    if command == "validate":
        validate_config(config)
        return

    # Validate before every operational command.
    validate_config(config)

    environment = (
        config["application"]["environment"]
    )

    # -----------------------------------------------------
    # Terraform plan
    # -----------------------------------------------------

    if command == "plan":

        terraform_init()

        terraform_workspace(
            environment
        )

        terraform_plan(config)

    # -----------------------------------------------------
    # Terraform apply
    # -----------------------------------------------------

    elif command == "apply":

        terraform_init()

        terraform_workspace(
            environment
        )

        terraform_apply(config)

    # -----------------------------------------------------
    # Terraform destroy
    # -----------------------------------------------------

    elif command == "destroy":

        terraform_init()

        terraform_workspace(
            environment
        )

        terraform_destroy(config)

    # -----------------------------------------------------
    # Terraform status
    # -----------------------------------------------------

    elif command == "status":

        terraform_init()

        terraform_workspace(
            environment
        )

        terraform_status()

    # -----------------------------------------------------
    # Configure existing EC2
    # -----------------------------------------------------

    elif command == "configure":

        terraform_init()

        terraform_workspace(
            environment
        )

        print()
        print(
            "Configuring existing AWS infrastructure..."
        )

        generate_ansible_inventory()

        run_ansible(
            "playbook.yml",
            config,
        )

        print()
        print("======================================")
        print("       CONFIGURATION SUCCESSFUL")
        print("======================================")

    # -----------------------------------------------------
    # Kubernetes deployment
    # -----------------------------------------------------

    elif command == "k8s":

        print()
        print(
            "Deploying application to Kubernetes..."
        )

        deploy_to_kubernetes(config)

        verify_kubernetes(config)

    # -----------------------------------------------------
    # Kubernetes status
    # -----------------------------------------------------

    elif command == "k8s-status":

        kubernetes_status(config)

    # -----------------------------------------------------
    # Full deployment
    # -----------------------------------------------------

    elif command == "deploy":

        deploy_full(config)

    # -----------------------------------------------------
    # Backward-compatible create command
    # -----------------------------------------------------

    elif command == "create":

        print()
        print(
            "NOTE: 'create' is an alias for 'deploy'."
        )

        deploy_full(config)

    # -----------------------------------------------------
    # Unknown command
    # -----------------------------------------------------

    else:

        print(
            f"Unknown command: {command}"
        )

        print()
        print("Available commands:")
        print(
            "  validate    Validate configuration"
        )
        print(
            "  plan        Create Terraform plan"
        )
        print(
            "  apply       Create/update AWS infrastructure"
        )
        print(
            "  configure   Configure existing EC2"
        )
        print(
            "  k8s         Deploy application to Kubernetes"
        )
        print(
            "  deploy      Full platform deployment"
        )
        print(
            "  create      Alias for deploy"
        )
        print(
            "  status      Show Terraform/AWS outputs"
        )
        print(
            "  k8s-status  Show Kubernetes status"
        )
        print(
            "  destroy     Destroy AWS infrastructure"
        )

        sys.exit(1)


# ---------------------------------------------------------
# Main
# ---------------------------------------------------------

def main():

    if (
        len(sys.argv) not in [5, 7]
        or sys.argv[3] != "--env"
        or (len(sys.argv) == 7 and sys.argv[5] != "--image")
    ):
        print()
        print(
            "Usage:"
        )
        print(
            "python cli/platform.py "
            "<command> <config.yaml> "
            "--env <environment> "
            "[--image <image>]"
        )

        print()
        print("Commands:")
        print("  validate")
        print("  plan")
        print("  apply")
        print("  configure")
        print("  k8s")
        print("  deploy")
        print("  create")
        print("  status")
        print("  k8s-status")
        print("  destroy")

        sys.exit(1)
        print()
        print(
            "Usage:"
        )
        print(
            "python cli/platform.py "
            "<command> <config.yaml> "
            "--env <environment>"
        )

        print()
        print("Commands:")
        print(
            "  validate"
        )
        print(
            "  plan"
        )
        print(
            "  apply"
        )
        print(
            "  configure"
        )
        print(
            "  k8s"
        )
        print(
            "  deploy"
        )
        print(
            "  create"
        )
        print(
            "  status"
        )
        print(
            "  k8s-status"
        )
        print(
            "  destroy"
        )

        sys.exit(1)

    command = sys.argv[1]
    config_file = sys.argv[2]
    environment = sys.argv[4]

    image_override = None

    if len(sys.argv) == 7:
        image_override = sys.argv[6]

    try:

        # -------------------------------------------------
        # Load main configuration
        # -------------------------------------------------

        config = load_config(
            config_file
        )

        # -------------------------------------------------
        # Validate requested environment
        # -------------------------------------------------

        supported_environments = [
            "dev",
            "staging",
            "prod",
        ]

        if environment not in supported_environments:
            raise ValueError(
                f"Unsupported environment: "
                f"{environment}. "
                f"Supported environments: "
                f"{', '.join(supported_environments)}"
            )

        # -------------------------------------------------
        # Override environment
        # -------------------------------------------------

        config["application"]["environment"] = (
            environment
        )

        # -------------------------------------------------
        # Load environment configuration
        # -------------------------------------------------

        environment_config = (
            load_environment_config(config)
        )

        # -------------------------------------------------
        # Apply environment-specific values
        # -------------------------------------------------

        apply_environment_config(
            config,
            environment_config,
        )

        # -------------------------------------------------
        # Execute command
        # -------------------------------------------------

        execute(
        command,
        config,
        image_override,
    )

    except ValueError as error:

        print()
        print(
            f"Configuration error: {error}"
        )

        sys.exit(1)

    except FileNotFoundError as error:

        print()
        print(
            f"File error: {error}"
        )

        sys.exit(1)

    except RuntimeError as error:

        print()
        print(
            f"Execution error: {error}"
        )

        sys.exit(1)


# ---------------------------------------------------------
# Entry point
# ---------------------------------------------------------

if __name__ == "__main__":
    main()