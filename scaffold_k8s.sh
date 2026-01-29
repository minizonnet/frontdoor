#!/usr/bin/env bash
set -euo pipefail

ROOT="fd-portal"
NS="fd-portal"
APP="fd-portal"

# Image to deploy (edit later to your registry/tag)
IMAGE="fd-portal:01"

# Ingress
PORTAL_HOST="console.minizon.net"
TLS_SECRET="fd-portal-tls"
INGRESS_CLASS="nginx"

# OpenStack endpoints
KEYSTONE_URL="https://opole.minizon.net:5000/v3"
HORIZON_URL="https://opole.minizon.net/"
USER_DOMAIN="Default"

# Secret naming (must match deployment secretKeyRef)
SECRET_NAME="${APP}-secret"

# Generate a random FLASK_SECRET if not provided
FLASK_SECRET="${FLASK_SECRET:-}"
if [[ -z "${FLASK_SECRET}" ]]; then
  if command -v openssl >/dev/null 2>&1; then
    FLASK_SECRET="$(openssl rand -base64 48)"
  else
    # fallback (still ok, but install openssl for better randomness)
    FLASK_SECRET="$(python3 - <<'PY'
import secrets, base64
print(base64.b64encode(secrets.token_bytes(48)).decode())
PY
)"
  fi
fi

mkdir -p \
  "${ROOT}/k8s/base" \
  "${ROOT}/k8s/overlays/dev" \
  "${ROOT}/k8s/overlays/prod"

# --- base manifests ---
cat > "${ROOT}/k8s/base/namespace.yaml" <<EOF
apiVersion: v1
kind: Namespace
metadata:
  name: ${NS}
EOF

cat > "${ROOT}/k8s/base/configmap.yaml" <<EOF
apiVersion: v1
kind: ConfigMap
metadata:
  name: ${APP}-config
  namespace: ${NS}
data:
  KEYSTONE_URL: "${KEYSTONE_URL}"
  USER_DOMAIN: "${USER_DOMAIN}"
  HORIZON_URL: "${HORIZON_URL}"
EOF

cat > "${ROOT}/k8s/base/secret.yaml" <<EOF
apiVersion: v1
kind: Secret
metadata:
  name: ${SECRET_NAME}
  namespace: ${NS}
type: Opaque
stringData:
  FLASK_SECRET: "${FLASK_SECRET}"
EOF

cat > "${ROOT}/k8s/base/deployment.yaml" <<EOF
apiVersion: apps/v1
kind: Deployment
metadata:
  name: ${APP}
  namespace: ${NS}
spec:
  replicas: 2
  selector:
    matchLabels:
      app: ${APP}
  template:
    metadata:
      labels:
        app: ${APP}
    spec:
      containers:
        - name: ${APP}
          image: ${IMAGE}
          imagePullPolicy: IfNotPresent
          ports:
            - containerPort: 8000
          env:
            - name: KEYSTONE_URL
              valueFrom:
                configMapKeyRef:
                  name: ${APP}-config
                  key: KEYSTONE_URL
            - name: USER_DOMAIN
              valueFrom:
                configMapKeyRef:
                  name: ${APP}-config
                  key: USER_DOMAIN
            - name: HORIZON_URL
              valueFrom:
                configMapKeyRef:
                  name: ${APP}-config
                  key: HORIZON_URL
            - name: FLASK_SECRET
              valueFrom:
                secretKeyRef:
                  name: ${SECRET_NAME}
                  key: FLASK_SECRET
          readinessProbe:
            httpGet:
              path: /
              port: 8000
            initialDelaySeconds: 3
            periodSeconds: 10
          livenessProbe:
            httpGet:
              path: /
              port: 8000
            initialDelaySeconds: 10
            periodSeconds: 20
EOF

cat > "${ROOT}/k8s/base/service.yaml" <<EOF
apiVersion: v1
kind: Service
metadata:
  name: ${APP}
  namespace: ${NS}
spec:
  selector:
    app: ${APP}
  ports:
    - name: http
      port: 80
      targetPort: 8000
  type: ClusterIP
EOF

cat > "${ROOT}/k8s/base/ingress.yaml" <<EOF
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: ${APP}
  namespace: ${NS}
spec:
  ingressClassName: ${INGRESS_CLASS}
  tls:
    - hosts:
        - ${PORTAL_HOST}
      secretName: ${TLS_SECRET}
  rules:
    - host: ${PORTAL_HOST}
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: ${APP}
                port:
                  number: 80
EOF

cat > "${ROOT}/k8s/base/kustomization.yaml" <<EOF
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization

resources:
  - namespace.yaml
  - configmap.yaml
  - secret.yaml
  - deployment.yaml
  - service.yaml
  - ingress.yaml
EOF

# --- overlays ---
cat > "${ROOT}/k8s/overlays/dev/kustomization.yaml" <<EOF
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization

namespace: ${NS}

resources:
  - ../../base

patchesStrategicMerge:
  - patch.yaml
EOF

cat > "${ROOT}/k8s/overlays/dev/patch.yaml" <<EOF
apiVersion: apps/v1
kind: Deployment
metadata:
  name: ${APP}
  namespace: ${NS}
spec:
  replicas: 1
EOF

cat > "${ROOT}/k8s/overlays/prod/kustomization.yaml" <<EOF
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization

namespace: ${NS}

resources:
  - ../../base

patchesStrategicMerge:
  - patch.yaml
EOF

cat > "${ROOT}/k8s/overlays/prod/patch.yaml" <<EOF
apiVersion: apps/v1
kind: Deployment
metadata:
  name: ${APP}
  namespace: ${NS}
spec:
  replicas: 3
EOF

echo "Scaffold created under: ${ROOT}/k8s"
echo "Secret name: ${SECRET_NAME} (namespace: ${NS})"
echo "Next steps:"
echo "  1) Build image: docker build -t ${IMAGE} -f ${ROOT}/container/Dockerfile ${ROOT}"
echo "  2) If using a registry, tag/push and update IMAGE in ${ROOT}/k8s/base/deployment.yaml"
echo "  3) Deploy dev: kubectl apply -k ${ROOT}/k8s/overlays/dev"

