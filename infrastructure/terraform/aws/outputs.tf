output "cluster_name" { value = aws_eks_cluster.this.name }
output "cluster_endpoint" { value = aws_eks_cluster.this.endpoint }
output "ecr_repository_url" { value = aws_ecr_repository.app.repository_url }
output "artifact_bucket" { value = aws_s3_bucket.artifacts.id }
output "database_secret_arn" { value = aws_secretsmanager_secret.database.arn }
output "efs_file_system_id" { value = aws_efs_file_system.state.id }
output "kms_key_arn" { value = aws_kms_key.platform.arn }
