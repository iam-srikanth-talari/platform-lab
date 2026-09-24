import json
import subprocess
import time
import os

os.environ["PYTHONIOENCODING"] = "utf-8"

def send_command(instance_id, commands, region):
    """Execute shell commands on an EC2 instance through AWS SSM."""

    command_json = json.dumps({
        "commands": commands
    })

    command = [
        "aws",
        "ssm",
        "send-command",
        "--instance-ids",
        instance_id,
        "--document-name",
        "AWS-RunShellScript",
        "--parameters",
        command_json,
        "--region",
        region,
        "--query",
        "Command.CommandId",
        "--output",
        "text",
    ]

    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )

    if result.returncode != 0:
        raise RuntimeError(
            f"SSM send-command failed:\n{result.stderr}"
        )

    command_id = result.stdout.strip()

    if not command_id:
        raise RuntimeError(
            "SSM did not return a command ID."
        )

    return command_id


def wait_for_command(
    command_id,
    instance_id,
    region,
    timeout=300,
):
    """Wait for an SSM command and return its output."""

    start_time = time.time()

    while time.time() - start_time < timeout:

        command = [
            "aws",
            "ssm",
            "get-command-invocation",
            "--command-id",
            command_id,
            "--instance-id",
            instance_id,
            "--region",
            region,
            "--output",
            "json",
        ]

        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            raise RuntimeError(
                f"Failed to get SSM command status:\n"
                f"{result.stderr}"
            )

        response = json.loads(result.stdout)

        status = response.get("Status")

        if status == "Success":
            return response.get("StandardOutputContent", "")

        if status in {
            "Failed",
            "Cancelled",
            "TimedOut",
            "Cancelling",
        }:
            stderr = response.get(
                "StandardErrorContent",
                "",
            )

            raise RuntimeError(
                f"SSM command failed.\n"
                f"Status: {status}\n"
                f"Error:\n{stderr}"
            )

        print(
            f"SSM command status: {status}..."
        )

        time.sleep(5)

    raise TimeoutError(
        "SSM command timed out."
    )

def deploy_with_ssm(instance_id, region, image):
    """Deploy application to EC2 through AWS SSM."""
    if not image or ":" not in image:
        raise ValueError("A valid container image with a tag is required.")

    commands = [
        "sudo dnf install -y docker",
        "sudo systemctl enable docker",
        "sudo systemctl start docker",
        f"sudo docker pull {image}",
        "sudo docker rm -f demo-app || true",
        (
            f"sudo docker run -d "
            f"--name demo-app "
            f"--restart unless-stopped "
            f"-p 8000:8000 "
            f"{image}"
        ),
        "sudo docker ps",
                    """
            for i in {1..12}; do
            if curl -fsS http://localhost:8000/health; then
                exit 0
            fi
            sleep 2
            done
            exit 1
            """,
                ]

    command_id = send_command(
        instance_id,
        commands,
        region,
    )

    print()
    print(f"SSM command started: {command_id}")
    print()

    output = wait_for_command(
        command_id,
        instance_id,
        region,
    )

    print()
    print("SSM deployment output:")
    print(output)
    print()

    return output