# VerifyOps infrastructure

| Folder | Contents |
| --- | --- |
| [containers](containers/compose.yaml) | Compose topology: PostgreSQL, Phoenix, migration, API, worker |
| [kubernetes](kubernetes/) | Kustomize base plus `kind` and `aws` overlays |
| [terraform/aws](terraform/aws/) | EKS, RDS PostgreSQL, EFS, S3, ECR, KMS, Secrets Manager |
| [supabase](supabase/) | Account snapshot migration and row-level security |

Launch Compose from the repository root:

```sh
scripts/deployment/compose.sh up --build -d
```

The wrapper keeps the root build context, private configuration, and volume names. CI builds both images, validates Terraform, renders every Kustomize overlay, and runs the Kind deployment smoke. [Runtime](../docs/operations/PRODUCTION-FOUNDATION.md).
