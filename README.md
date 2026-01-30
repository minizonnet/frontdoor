# Front Door Portal (fd-portal)

A lightweight “front door” web portal that validates **OpenStack Keystone v3 username/password** and, on success, grants access to a landing page with a link to **Horizon**.

This is **not SSO** yet. Horizon will still have its own login/session. The portal is intended as a **controlled entry point** (optionally extended later with authorization checks, reverse-proxying, or federation/WebSSO).

---

## Features

- Keystone v3 **password authentication** (`POST /v3/auth/tokens`)
- Minizon-themed UI (branding + animated background)
- Session cookie hardening (Secure/HttpOnly/SameSite)
- Basic security headers
- In-memory login rate limiting (per pod)

---

## What this is (and isn’t)

✅ Validates credentials against Keystone  
✅ Creates a portal session (Flask signed session cookie)  
✅ Provides a “go to Horizon” entry point  

❌ Does **not** create a Horizon session (no SSO)  
❌ Does **not** store Keystone tokens in the browser  
❌ Rate limiting is **per pod** (for strict multi-replica rate limiting, use Redis later)

---

## Repository layout

```text
fd-portal/
  app/
    app.py
    app_legacy.py
    config.py
    keystone.py
    routes.py
    security.py
    ratelimit.py
    templates/
      base.html
      login.html
      home.html
    static/
      css/
        main.css
  container/
    Dockerfile
  k8s/
    base/
      namespace.yaml
      configmap.yaml
      secret.yaml
      deployment.yaml
      service.yaml
      ingress.yaml
      kustomization.yaml
    overlays/
      dev/
      prod/
```

---

## Configuration (Environment Variables)

| Variable | Default | Description |
|---|---:|---|
| `KEYSTONE_URL` | `https://keystone.example.com/v3` | Keystone v3 base URL (must include `/v3`) |
| `USER_DOMAIN` | `Default` | Keystone user domain name |
| `HORIZON_URL` | `https://opole.minizon.net/` | Horizon URL to link to after login |
| `FLASK_SECRET` | `CHANGE_ME_LONG_RANDOM` | Flask session signing key (must be long + random) |
| `LOGIN_WINDOW_SEC` | `60` | Rate limit window |
| `LOGIN_MAX_ATTEMPTS` | `10` | Max attempts per window (per IP, per pod) |
| `SESSION_COOKIE_SECURE` | `true` | Sets `Secure` on cookies (should be true behind TLS) |
| `TRUST_X_FORWARDED_FOR` | `true` | Trust `X-Forwarded-For` (set `false` if not behind LB/Ingress) |
| `BRAND_NAME` | `MINIZON` | Branding text |
| `PRODUCT_NAME` | `Front Door` | Branding text |
| `LOGO_URL` | minizon.net logo | Logo image URL |
| `BG_IMG_URL` | minizon.net image | Background image URL |
| `ACCENT_IMG_URL` | minizon.net image | Accent image URL |
| `HERO_IMG_URL` | minizon.net image | Side panel image URL |

---

## Local run (venv)

```bash
cd fd-portal/app
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

export KEYSTONE_URL="https://opole.minizon.net:5000/v3"
export USER_DOMAIN="Default"
export HORIZON_URL="https://opole.minizon.net/"
export FLASK_SECRET="$(openssl rand -base64 48)"

python app.py
```

Open: `http://127.0.0.1:8000/login`

---

## Container build/run

### Build (from repo root)

```bash
docker build -t tomtek/fd-portal:01 -f fd-portal/container/Dockerfile fd-portal
```

### Run

```bash
docker run --rm -p 8000:8000   -e KEYSTONE_URL="https://opole.minizon.net:5000/v3"   -e USER_DOMAIN="Default"   -e HORIZON_URL="https://opole.minizon.net/"   -e FLASK_SECRET="$(openssl rand -base64 48)"   tomtek/fd-portal:01
```

Open: `http://localhost:8000/login`

---

## Kubernetes deployment (Kustomize)

> You can deploy either via **Ingress** (typical) or **Service type: LoadBalancer** (Octavia). Pick one approach.

### Prerequisites

- Working `kubectl` context for the cluster
- Image accessible from the cluster: `tomtek/fd-portal:01`
- Namespace is `fd-portal` (from manifests)
- If using Octavia: cluster must support `Service type: LoadBalancer`

### Set image

Edit `fd-portal/k8s/base/deployment.yaml`:

```yaml
image: tomtek/fd-portal:01
```

### Set endpoints

Edit `fd-portal/k8s/base/configmap.yaml`:

```yaml
KEYSTONE_URL: "https://opole.minizon.net:5000/v3"
USER_DOMAIN: "Default"
HORIZON_URL: "https://opole.minizon.net/"
```

### Set secret

Edit `fd-portal/k8s/base/secret.yaml`:

```yaml
FLASK_SECRET: "<LONG_RANDOM_VALUE>"
```

Generate a strong secret:

```bash
openssl rand -base64 48
```

### Deploy (dev overlay)

```bash
kubectl apply -k fd-portal/k8s/overlays/dev
```

### Watch rollout

```bash
kubectl -n fd-portal get pods -w
kubectl -n fd-portal logs deploy/fd-portal -f
```

---

## Exposing the service

### Option A: Octavia LoadBalancer (no Ingress)

Set in `fd-portal/k8s/base/service.yaml`:

```yaml
spec:
  type: LoadBalancer
```

Apply and check external IP:

```bash
kubectl -n fd-portal get svc fd-portal
kubectl -n fd-portal describe svc fd-portal
```

If your OpenStack integration supports it, you may try a specific IP:

```yaml
spec:
  loadBalancerIP: 91.103.87.28
```

Note: many OpenStack CCM implementations ignore or reject `loadBalancerIP`.

### Option B: Ingress (recommended for production)

- Keep app Service as `ClusterIP`
- Expose the ingress controller via Octavia (`LoadBalancer`)
- Use `fd-portal/k8s/base/ingress.yaml` for host/TLS routing

---

## Troubleshooting

### `kubectl apply` fails with `localhost:8080` OpenAPI error

If you see:

```text
failed to download openapi: Get "http://localhost:8080/openapi/v2" ... connection refused
```

your current kubeconfig/context is pointing to `localhost:8080` instead of the real API server.

Check:

```bash
kubectl config current-context
kubectl config view --minify -o jsonpath='{.clusters[0].cluster.server}{"\n"}'
kubectl get nodes
```

Fix by switching context or using the correct kubeconfig.

### Keystone TLS verify errors in the pod

If Keystone uses an internal CA, the container may fail TLS verification. The correct fix is to mount your CA bundle and set:

- `REQUESTS_CA_BUNDLE=/path/to/ca.crt`

(Do not disable TLS verification in production.)

---

## Roadmap ideas

- Authorization: allowlist by Keystone project/role before granting portal access
- Central logging/audit of login attempts
- Replace in-memory rate limit with Redis
- Move to true SSO: Keystone federation + OIDC/SAML + Horizon WebSSO

