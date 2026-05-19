# TrustVault deployment pack

This folder contains the first controlled-deployment scaffolding for TrustVault.

## Local

Use Docker Compose from the repository root:

```bash
docker compose up --build
```

## AWS target

The preferred first AWS deployment model is:

- ECS Fargate for `trustvault-api` and `trustvault-worker`;
- S3 for source imports, FITS containers and derived reports;
- RDS PostgreSQL;
- SQS for jobs/events;
- ECR for images;
- Secrets Manager for app configuration;
- KMS encryption;
- CloudWatch logs;
- private subnets and VPC endpoints where possible;
- ALB or private load balancer;
- Cognito or client OIDC/SAML.

See `deployment/aws/terraform` for the module scaffold.

## Azure target

The preferred first Azure deployment model is:

- Azure Container Apps for `trustvault-api` and `trustvault-worker`;
- Blob Storage for source imports, FITS containers and derived reports;
- Azure Database for PostgreSQL;
- Service Bus or Storage Queues;
- Azure Container Registry;
- Key Vault;
- Managed Identity;
- Azure Monitor / Log Analytics;
- Private Endpoints;
- Entra ID integration.

See `deployment/azure/bicep` for the module scaffold.

## Important

FITS containers are the archive/source of truth. Derived reports or approval packs are presentation artefacts only.
