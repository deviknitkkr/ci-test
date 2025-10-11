helm repo add argo https://argoproj.github.io/argo-helm
kubectl create namespace argocd
helm upgrade --install argocd argo/argo-cd -n argocd --version 8.6.0

kubectl -n argocd port-forward svc/argocd-server 8081:80 &
kubectl -n argocd get secret argocd-initial-admin-secret -o jsonpath="{.data.password}" | base64 --decode
k3d image import ecr-public.aws.com/docker/library/redis:7.2.11-alpine