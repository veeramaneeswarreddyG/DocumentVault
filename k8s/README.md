# Document Vault — Kubernetes (K8s) Architecture & Deployment Guide

This directory contains the production-ready Kubernetes (K8s) manifests for **Document Vault — Persistent PDF Storage Engine**.

---

## 1. Kubernetes Architecture Overview

```
                      ┌──────────────────────────────────────────────┐
                      │              User Web Browser                │
                      └──────────────────────┬───────────────────────┘
                                             │ http://localhost:5000 (LoadBalancer)
                                             │ or http://localhost:30050 (NodePort)
                                             ▼
                      ┌──────────────────────────────────────────────┐
                      │          documentvault-service               │
                      │         (Type: LoadBalancer/NodePort)        │
                      └──────────────────────┬───────────────────────┘
                                             │
                      ┌──────────────────────┴───────────────────────┐
                      ▼                                              ▼
          ┌─────────────────────────┐                    ┌─────────────────────────┐
          │  Pod: documentvault-1   │                    │  Pod: documentvault-2   │
          │   (Flask App + Gunicorn)│                    │   (Flask App + Gunicorn)│
          └───────────┬─────────────┘                    └───────────┬─────────────┘
                      │                                              │
                      ├──────────────────────┬───────────────────────┤
                      │                      │                       │
                      ▼                      ▼                       ▼
            ┌──────────────────┐    ┌──────────────────┐    ┌──────────────────┐
            │   app-pdf-pvc    │    │ documentvault-   │    │ documentvault-   │
            │ (PersistentVolume│    │     config       │    │     secrets      │
            │  Claim for PDFs) │    │   (ConfigMap)    │    │     (Secret)     │
            └──────────────────┘    └──────────────────┘    └──────────────────┘
                      │
                      │ TCP Port 5432
                      ▼
          ┌─────────────────────────┐
          │    postgres-service     │
          │    (Type: ClusterIP)    │
          └───────────┬─────────────┘
                      │
                      ▼
          ┌─────────────────────────┐
          │      postgres-pod       │
          │   (PostgreSQL 16)       │
          └───────────┬─────────────┘
                      │
                      ▼
            ┌──────────────────┐
            │   postgres-pvc   │
            │ (PersistentVolume│
            │  Claim for DB)   │
            └──────────────────┘
```

---

## 2. Manifest Inventory

| Manifest | Kind | Description |
|---|---|---|
| `configmap.yaml` | `ConfigMap` | Non-sensitive runtime variables (`POSTGRES_HOST`, `POSTGRES_PORT`, `POSTGRES_DB`, etc.) |
| `secret.yaml` | `Secret` | Sensitive credentials (`POSTGRES_USER`, `POSTGRES_PASSWORD`, `SECRET_KEY`) |
| `postgres-pvc.yaml` | `PersistentVolumeClaim` | 1Gi persistent storage for PostgreSQL data directory |
| `postgres-service.yaml` | `Service` | Internal `ClusterIP` exposing PostgreSQL on port 5432 to the app pods |
| `postgres-deployment.yaml` | `Deployment` | Single-replica PostgreSQL deployment with readiness & liveness probes |
| `app-pvc.yaml` | `PersistentVolumeClaim` | 1Gi persistent storage for uploaded PDF files (`/app/uploads`) |
| `app-deployment.yaml` | `Deployment` | 2-replica high-availability Flask/Gunicorn app deployment with probes and `fsGroup` permissions |
| `app-service.yaml` | `Service` | `LoadBalancer` + `NodePort (30050)` service routing traffic to Document Vault pods |
| `kustomization.yaml` | `Kustomization` | Bundles all resources for one-command deployment (`kubectl apply -k k8s/`) |

---

## 3. Deployment Instructions (Docker Desktop)

### Step 1: Ensure Kubernetes is Running in Docker Desktop
1. Open **Docker Desktop**.
2. Click the gear icon (**Settings**) in the top right.
3. Select **Kubernetes** from the left sidebar.
4. Check **Enable Kubernetes** and click **Apply & restart**.
5. Wait until the Kubernetes status icon in the bottom left turns green.

### Step 2: Build the Local Docker Image
Build the container image so Kubernetes can use it locally:
```powershell
docker build -t documentvault-app:latest .
```

### Step 3: Deploy All Resources to Kubernetes
Deploy using `kubectl`:
```powershell
kubectl apply -f k8s/
```
*(Or use Kustomize: `kubectl apply -k k8s/`)*

### Step 4: Verify Deployment Status
Check the status of all pods, services, and PVCs:
```powershell
kubectl get pods
kubectl get services
kubectl get pvc
```

Expected output:
```
NAME                                        READY   STATUS    RESTARTS   AGE
documentvault-deployment-xxxxxxxxx-xxxxx    1/1     Running   0          30s
documentvault-deployment-xxxxxxxxx-xxxxx    1/1     Running   0          30s
postgres-deployment-xxxxxxxxx-xxxxx         1/1     Running   0          45s

NAME                    TYPE           CLUSTER-IP      EXTERNAL-IP   PORT(S)          AGE
documentvault-service   LoadBalancer   10.96.xxx.xxx   localhost     5000:30050/TCP   30s
postgres-service        ClusterIP      10.96.xxx.xxx   <none>        5432/TCP         45s
```

### Step 5: Access the Application
Open your browser and navigate to:
- **`http://localhost:5000`** (via LoadBalancer)
- or **`http://localhost:30050`** (via NodePort)

---

## 4. Verification & Testing

### 1. View App Logs
```powershell
kubectl logs -l app=documentvault,tier=frontend -f
```

### 2. Verify Storage Persistence
1. Open `http://localhost:5000` and upload a PDF.
2. Delete one of the pods to simulate a crash:
   ```powershell
   kubectl delete pod <pod-name>
   ```
3. Kubernetes will automatically start a replacement pod.
4. Refresh `http://localhost:5000` — your uploaded document and database records remain intact!

---

## 5. Teardown / Cleanup
To remove all Document Vault resources from your Kubernetes cluster:
```powershell
kubectl delete -f k8s/
```
