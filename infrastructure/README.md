# VerifyOps infrastructure

[Container topology](containers/compose.yaml) is launched from the repository root:

```sh
scripts/deployment/compose.sh up --build -d
```

The wrapper keeps the root build context, private configuration, and volume names. [Kubernetes](kubernetes/) separates base resources and environment overlays. [Terraform](terraform/) is validated in CI. Image and topology checks run in the required CI jobs.
