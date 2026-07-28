# VerifyOps infrastructure

[Container topology](containers/compose.yaml) is launched from the repository root:

```sh
scripts/deployment/compose.sh up --build -d
```

The wrapper explicitly retains the root build context, private configuration and intended project/volume naming. [Kubernetes](kubernetes/) separates base resources and environment overlays. [Terraform](terraform/) is prepared and validated but remains unapplied. Actual image/topology checks belong to required CI; these files alone are not proof of monitored cloud delivery.
