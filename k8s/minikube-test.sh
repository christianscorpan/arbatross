#!/bin/bash
set -e

echo "Starting minikube if not already running..."
minikube status || minikube start

echo "Configuring docker to use minikube's docker daemon..."
eval $(minikube docker-env)

echo "Building backend image in minikube..."
# We build a single backend image that will be used by both services
# The SERVICE env var is set in the deployment
docker build -t arbatross-backend:latest -f Dockerfile.backend .

echo "Building frontend image in minikube..."
docker build -t arbatross-frontend:latest -f Dockerfile.frontend .

echo "Deleting existing resources..."
kubectl delete deployment,pod,service -n arbatross --all 2>/dev/null || true
kubectl delete configmap -n arbatross nginx-config 2>/dev/null || true

echo "Deploying to minikube using kustomize with dev overlay..."
kubectl apply -k k8s/overlays/dev/

echo "Checking pod status..."
kubectl get pods -n arbatross
sleep 10
echo "Checking pod status again after 10 seconds..."
kubectl get pods -n arbatross

echo "Checking logs for diff-eye pod..."
kubectl logs -n arbatross $(kubectl get pods -n arbatross -l app=diff-eye -o jsonpath='{.items[0].metadata.name}') || echo "Failed to get logs for diff-eye pod"

echo "Checking logs for voltic-eye pod..."
kubectl logs -n arbatross $(kubectl get pods -n arbatross -l app=voltic-eye -o jsonpath='{.items[0].metadata.name}') || echo "Failed to get logs for voltic-eye pod"

echo "Checking logs for frontend pod..."
kubectl logs -n arbatross $(kubectl get pods -n arbatross -l app=frontend -o jsonpath='{.items[0].metadata.name}') || echo "Failed to get logs for frontend pod"

echo "Enabling ingress addon if not already enabled..."
minikube addons enable ingress 2>/dev/null || true

echo "Getting URL to access the application..."
minikube service frontend-service -n arbatross --url

echo "Deployment to minikube completed!"
echo "You can also access the application through the ingress by adding the following to your /etc/hosts file:"
echo "$(minikube ip) arbatross.local"
echo "Then open http://arbatross.local in your browser."
