# Kubernetes Deployment for Arbatross

This directory contains Kubernetes manifests and scripts to deploy the Arbatross application on a Kubernetes cluster.

## Prerequisites

- A Kubernetes cluster (e.g., minikube, kind, or a cloud provider's Kubernetes service)
- kubectl configured to communicate with your cluster
- Docker installed and configured
- Access to a container registry (Docker Hub, GCR, ECR, etc.)

## Directory Structure

```
k8s/
├── base/                 # Base Kubernetes configurations
│   ├── namespace.yaml
│   ├── configmap.yaml
│   ├── diff-eye-deployment.yaml
│   ├── voltic-eye-deployment.yaml
│   ├── frontend-deployment.yaml
│   ├── ingress.yaml
│   └── kustomization.yaml
├── overlays/             # Environment-specific overlays
│   ├── dev/              # Development environment
│   │   └── kustomization.yaml
│   └── production/       # Production environment
│       ├── kustomization.yaml
│       └── resource-limits.yaml
├── minikube-test.sh      # Script for testing with minikube (dev)
└── minikube-test-production.sh  # Script for testing with minikube (production)
```

## Deployment Steps

### Testing with Minikube

For local testing with minikube, you can use the provided scripts:

```bash
# For development environment (no resource limits)
./k8s/minikube-test.sh

# For production environment (with resource limits)
./k8s/minikube-test-production.sh
```

These scripts will:
1. Start minikube if it's not already running
2. Configure docker to use minikube's docker daemon
3. Build the images directly in minikube
4. Deploy the application to minikube using kustomize
5. Enable the ingress addon if needed
6. Provide the URL to access the application

### Deploying to a Kubernetes Cluster

You can deploy directly using kustomize:

```bash
# For development environment
kubectl apply -k k8s/overlays/dev/

# For production environment
kubectl apply -k k8s/overlays/production/
```

## Environment Differences

### Development Environment

- No resource limits or requests
- No health or readiness probes
- Labeled with `environment: development`

### Production Environment

- Resource limits and requests for all containers
- Health and readiness probes for all containers
- Labeled with `environment: production`

## Customizing Deployments

You can customize the deployments by:

1. Modifying the base YAML files in the `base/` directory
2. Adding environment-specific customizations in the overlay directories
3. Creating new overlays for different environments (e.g., staging, testing)

## Troubleshooting

If you encounter issues:

1. Check pod logs:
   ```bash
   kubectl logs -n arbatross <pod-name>
   ```

2. Check pod status:
   ```bash
   kubectl describe pod -n arbatross <pod-name>
   ```

3. Check service endpoints:
   ```bash
   kubectl get endpoints -n arbatross
   ```

4. Check ingress status:
   ```bash
   kubectl describe ingress -n arbatross
   ```

5. Validate your kustomize configurations:
   ```bash
   kubectl kustomize k8s/overlays/dev/
   kubectl kustomize k8s/overlays/production/
   ```
