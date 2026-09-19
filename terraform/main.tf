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

  root_block_device {
    volume_size = 10
    volume_type = "gp3"
  }

  tags = {
    Name        = "${var.application_name}-${var.environment}"
    Environment = var.environment
    ManagedBy   = "platform-lab"
  }
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