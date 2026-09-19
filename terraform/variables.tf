variable "aws_region" {
  type = string
}

variable "instance_type" {
  type = string
}

variable "application_name" {
  type = string
}

variable "environment" {
  type = string
}

variable "ssh_public_key" {
  type        = string
  description = "SSH public key for EC2 access"
}

variable "ssh_allowed_cidr" {
  type        = string
  description = "CIDR allowed to SSH to the EC2 instance"
}