terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
  }

  required_version = ">= 1.5.0"
}

provider "aws" {
  region = var.aws_region
}

resource "aws_vpc" "platform_vpc" {
  cidr_block = "10.0.0.0/16"

  tags = {
    Name        = "${var.application_name}-${var.environment}-vpc"
    Environment = var.environment
    ManagedBy   = "platform-lab"
  }
}

resource "aws_subnet" "platform_subnet" {
  vpc_id     = aws_vpc.platform_vpc.id
  cidr_block = "10.0.1.0/24"

  map_public_ip_on_launch = true

  tags = {
    Name = "${var.application_name}-${var.environment}-subnet"
  }
}

resource "aws_key_pair" "platform_key" {
  key_name   = "${var.application_name}-${var.environment}-key"
  public_key = var.ssh_public_key
}


resource "aws_instance" "platform_instance" {
  ami           = data.aws_ami.amazon_linux.id
  instance_type = var.instance_type

  subnet_id              = aws_subnet.platform_subnet.id
  vpc_security_group_ids = [aws_security_group.platform_sg.id]

  key_name = aws_key_pair.platform_key.key_name

  iam_instance_profile = aws_iam_instance_profile.platform_ssm_profile.name

  user_data = <<-EOF
              #!/bin/bash
              dnf install -y amazon-ssm-agent
              systemctl enable amazon-ssm-agent
              systemctl start amazon-ssm-agent
              EOF

  root_block_device {
    volume_size = 30
    volume_type = "gp3"
  }

  tags = {
    Name        = "${var.application_name}-${var.environment}"
    Environment = var.environment
    ManagedBy   = "platform-lab"
    Role        = "platform-app"
  }
}


resource "aws_iam_role" "platform_ssm_role" {
  name = "${var.application_name}-${var.environment}-ssm-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"

    Statement = [
      {
        Effect = "Allow"

        Principal = {
          Service = "ec2.amazonaws.com"
        }

        Action = "sts:AssumeRole"
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "platform_ssm_policy" {
  role       = aws_iam_role.platform_ssm_role.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

resource "aws_iam_instance_profile" "platform_ssm_profile" {
  name = "${var.application_name}-${var.environment}-ssm-profile"
  role = aws_iam_role.platform_ssm_role.name
}


data "aws_ami" "amazon_linux" {
  most_recent = true

  owners = ["amazon"]

  filter {
    name   = "name"
    values = ["al2023-ami-*-x86_64"]
  }

  filter {
    name   = "state"
    values = ["available"]
  }
}

resource "aws_internet_gateway" "platform_igw" {
  vpc_id = aws_vpc.platform_vpc.id

  tags = {
    Name = "${var.application_name}-${var.environment}-igw"
  }
}

resource "aws_route_table" "platform_route_table" {
  vpc_id = aws_vpc.platform_vpc.id

  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.platform_igw.id
  }

  tags = {
    Name = "${var.application_name}-${var.environment}-rt"
  }
}

resource "aws_route_table_association" "platform_subnet_association" {
  subnet_id      = aws_subnet.platform_subnet.id
  route_table_id = aws_route_table.platform_route_table.id
}

resource "aws_security_group" "platform_sg" {
  name        = "${var.application_name}-${var.environment}-sg"
  description = "Security group for platform demo"
  vpc_id      = aws_vpc.platform_vpc.id

  ingress {
    description = "HTTP"
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    description = "SSH"
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = [var.ssh_allowed_cidr]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "${var.application_name}-${var.environment}-sg"
  }
}

# Shared GitHub Actions OIDC provider
# The provider is account-level and already exists in AWS.
# Terraform reads it instead of creating one per environment.
data "aws_iam_openid_connect_provider" "github" {
  url = "https://token.actions.githubusercontent.com"
}

# IAM role assumed by GitHub Actions through OIDC
resource "aws_iam_role" "github_actions_role" {
  name = "${var.application_name}-${var.environment}-github-actions-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"

    Statement = [
      {
        Effect = "Allow"

        Principal = {
          Federated = data.aws_iam_openid_connect_provider.github.arn
        }

        Action = "sts:AssumeRoleWithWebIdentity"

        Condition = {
          StringEquals = {
            "token.actions.githubusercontent.com:aud" = "sts.amazonaws.com"
          }

          StringLike = {
            "token.actions.githubusercontent.com:sub" = "repo:iam-srikanth-talari@242778939/platform-lab@1375942854:*"
          }
        }
      }
    ]
  })
}

# Permissions for GitHub Actions to deploy through AWS SSM
resource "aws_iam_role_policy" "github_actions_ssm" {
  name = "${var.application_name}-${var.environment}-github-actions-ssm"
  role = aws_iam_role.github_actions_role.id

  policy = jsonencode({
    Version = "2012-10-17"

    Statement = [
      {
        Effect = "Allow"

        Action = [
          "ssm:SendCommand",
          "ssm:GetCommandInvocation",
          "ec2:DescribeInstances"
        ]

        Resource = "*"
      },
    ]
  })
}