output "vpc_id" {
  value = aws_vpc.platform_vpc.id
}

output "subnet_id" {
  value = aws_subnet.platform_subnet.id
}

output "instance_id" {
  value = aws_instance.platform_instance.id
}

output "instance_private_ip" {
  value = aws_instance.platform_instance.private_ip
}
output "instance_public_ip" {
  value = aws_instance.platform_instance.public_ip
}
output "github_actions_role_arn" {
  value = aws_iam_role.github_actions_role.arn
}