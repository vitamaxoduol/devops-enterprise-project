# DevOps Enterprise Project

A production-style microservices platform designed to demonstrate backend engineering, containerization, asynchronous messaging, reliability engineering, observability, CI/CD, GitOps, Kubernetes, security, and AWS infrastructure practices.

The project is being built incrementally, beginning with a fully functional local distributed system before moving to AWS and Kubernetes.

> **Current status:** Phase 1 is in progress.  
> Checkpoints 1–5 are implemented. Checkpoint 6, the observability foundation, is currently being implemented.

---

## Project Goal

The long-term goal is to build a platform where every approved application change can be:

- tested automatically,
- scanned for security issues,
- built into an immutable container image,
- published to a container registry,
- promoted through GitOps,
- deployed to Kubernetes,
- observed through metrics, logs, and traces,
- validated against reliability objectives,
- and safely rolled back or recovered when failures occur.

The project intentionally separates application development, CI, deployment, infrastructure, security, and observability concerns.

---

# Architecture

## Current Local Architecture

```text
                           CLIENT
                             │
        ┌────────────────────┼─────────────────────┐
        │                    │                     │
        ▼                    ▼                     ▼
  User Service         Order Service        Payment Service
      :8001                :8002                :8003
        │                    │                     │
        │                    │ HTTP                │ HTTP
        │                    ▼                     ▼
        │              User Service          Order Service
        │
        ▼                    ▼                     ▼
     user_db              order_db              payment_db
                                                   │
                                                   │
                                          Transactional Outbox
                                                   │
                                                   ▼
                                          Outbox Publisher
                                                   │
                                                   ▼
                                              LocalStack
                                                 SQS
                                                   │
                                                   ▼
                                         Notification Worker
                                                   │
                                                   ▼
                                          notification_db
                                                   │
                                                   ▼
                                       Notification Service
                                                :8004
```

The system currently demonstrates both:

```text
Synchronous communication
    Order Service → User Service
    Payment Service → Order Service

Asynchronous communication
    Payment Service → Outbox → SQS → Notification Worker
```

---

# Microservices

## User Service

The User Service owns user information and its own PostgreSQL database.

### Endpoints

```text
POST /users
GET  /users/{user_id}

GET /health/live
GET /health/ready
GET /metrics
```

### Responsibilities

- create users,
- retrieve users,
- validate unique email addresses,
- expose health information,
- expose Prometheus-compatible metrics.

### Database ownership

```text
user_db
└── users
```

No other service accesses `user_db` directly.

---

## Order Service

The Order Service manages orders and order items.

### Endpoints

```text
POST /orders
GET  /orders/{order_id}

GET /health/live
GET /health/ready
GET /health/dependencies
GET /metrics
```

### Responsibilities

- validate users through the User Service API,
- calculate order totals,
- persist orders,
- persist order items,
- report User Service dependency health.

### Database ownership

```text
order_db
├── orders
└── order_items
```

The Order Service does not query `user_db`.

Instead:

```text
Order Service
     │
     │ GET /users/{id}
     ▼
User Service
```

This keeps the services independently owned.

---

## Payment Service

The Payment Service validates orders and simulates payment processing.

### Endpoints

```text
POST /payments
GET  /payments/{payment_id}

GET /health/live
GET /health/ready
GET /health/dependencies
GET /metrics
```

### Responsibilities

- validate an order through the Order Service,
- retrieve the authoritative order amount,
- simulate payment processing,
- persist successful payments,
- enforce payment idempotency,
- create transactional outbox events.

### Database ownership

```text
payment_db
├── payments
└── outbox_events
```

Payment requests require:

```text
Idempotency-Key
```

Example:

```http
POST /payments
Idempotency-Key: payment-order-123
Content-Type: application/json
```

```json
{
  "order_id": "..."
}
```

The amount is deliberately not supplied by the client.

Instead:

```text
Payment Service
      │
      │ GET /orders/{id}
      ▼
Order Service
      │
      ▼
authoritative order amount
```

This prevents the client from deciding how much an order should cost.

---

## Notification Service

The Notification Service consumes payment events asynchronously and stores simulated notifications.

### Endpoints

```text
GET /notifications
GET /notifications/{notification_id}

GET /health/live
GET /health/ready
GET /health/dependencies
GET /metrics
```

### Database ownership

```text
notification_db
└── notifications
```

The service currently simulates email notifications rather than contacting an external email provider.

---

# Transactional Outbox

The project uses the **Transactional Outbox Pattern** for reliable event publication.

A payment and its corresponding event are written in one PostgreSQL transaction:

```text
BEGIN

INSERT payment

INSERT outbox_event

COMMIT
```

This avoids a common dual-write problem.

A direct implementation such as:

```text
save payment
     ↓
publish SQS message
```

could result in:

```text
payment saved successfully
        +
SQS publication failed
```

leaving the system inconsistent.

Instead, the durable outbox ensures the event remains available for later publishing if SQS is temporarily unavailable.

---

# Payment Event Publisher

The Payment Event Publisher is a background process built from the Payment Service codebase.

It reads unpublished records from:

```text
payment_db.outbox_events
```

and publishes them to SQS.

```text
outbox_events
      │
      ▼
Payment Event Publisher
      │
      ▼
SQS
```

The publisher records when an event has successfully been published.

Because delivery can occur more than once, consumers are designed to be idempotent.

---

# AWS SQS Simulation with LocalStack

AWS SQS is currently simulated locally using LocalStack.

Queues:

```text
payment-events
payment-events-dlq
```

The main queue receives:

```text
payment.succeeded
```

events.

Example event:

```json
{
  "event_id": "...",
  "event_type": "payment.succeeded",
  "schema_version": 1,
  "occurred_at": "...",
  "data": {
    "payment_id": "...",
    "order_id": "...",
    "user_id": "...",
    "amount_cents": 5000
  }
}
```

---

# At-Least-Once Delivery

The messaging design assumes **at-least-once delivery**.

Duplicates can happen when:

```text
Publisher
    │
    ├── sends message successfully
    │
    X crashes before marking event published
```

or when SQS redelivers a message.

Notification Service therefore enforces:

```text
UNIQUE(event_id)
```

Duplicate events are ignored rather than creating duplicate notifications.

---

# Dead-Letter Queue

Malformed or repeatedly failing messages are not deleted from the main queue.

The local queue is configured to move them to:

```text
payment-events-dlq
```

after repeated processing attempts.

This prevents poison messages from being retried forever.

---

# Failure Isolation

The project distinguishes between:

```text
Liveness
Readiness
Dependency health
```

For example, if User Service is unavailable:

```text
Order Service
    │
    ├── /health/live        → healthy
    ├── /health/ready       → healthy if order_db is healthy
    └── /health/dependencies → degraded
```

This prevents one downstream failure from unnecessarily removing otherwise healthy services from traffic.

The same principle is used for:

```text
Payment Service → Order Service
Notification Service → SQS
```

---

# SQS Failure Recovery

Payment processing does not synchronously depend on SQS.

If SQS becomes unavailable:

```text
Payment Service
      │
      ├── payment committed
      └── outbox event committed

SQS
      X unavailable
```

The payment request can still succeed.

The unpublished event remains in:

```text
outbox_events
```

Once SQS recovers, the publisher automatically sends the pending event.

---

# Current Observability Work

Checkpoint 6 is currently adding a proper observability foundation.

The system already exposes basic Prometheus-compatible HTTP metrics and structured JSON logging.

The current work expands this into:

```text
Request IDs
Correlation IDs
Structured logs
Business metrics
OpenTelemetry traces
HTTP trace propagation
Asynchronous trace propagation
Worker metrics
```

---

## Request Correlation

Services are being updated to support:

```text
X-Request-ID
```

Example:

```text
Client
   │
   │ X-Request-ID: req-123
   ▼
Order Service
   │
   │ X-Request-ID: req-123
   ▼
User Service
```

The same identifier appears in structured logs.

---

## Distributed Tracing

OpenTelemetry is being introduced for:

- FastAPI,
- HTTPX,
- SQLAlchemy,
- boto3/SQS,
- asynchronous producer and consumer operations.

The intended trace flow is:

```text
POST /payments
      │
      ▼
Payment Service
      │
      ▼
Order Service
      │
      ▼
PostgreSQL
      │
      ▼
Transactional Outbox
      │
      ▼
Outbox Publisher
      │
      ▼
SQS
      │
      ▼
Notification Worker
      │
      ▼
notification_db
```

Trace context is also being propagated across the asynchronous SQS boundary.

---

# Metrics

Current and planned application metrics include:

## User Service

```text
users_created_total
```

## Order Service

```text
orders_created_total
order_value_cents
order_upstream_failures_total
```

## Payment Service

```text
payments_succeeded_total
payment_idempotency_replays_total
payment_upstream_failures_total
outbox_events_created_total
```

## Payment Event Publisher

```text
outbox_publish_total
outbox_pending_events
```

## Notification Worker

```text
notification_events_received_total
notifications_created_total
notification_duplicate_events_total
notification_event_processing_failures_total
```

High-cardinality identifiers such as:

```text
user_id
order_id
payment_id
event_id
```

are deliberately not used as Prometheus metric labels.

They belong in logs and traces.

---

# Metrics Endpoints

The target local endpoints are:

```text
User Service
http://localhost:8001/metrics

Order Service
http://localhost:8002/metrics

Payment Service
http://localhost:8003/metrics

Notification Service
http://localhost:8004/metrics

Payment Event Publisher
http://localhost:9101/metrics

Notification Worker
http://localhost:9102/metrics
```

---

# OpenTelemetry Collector

A local OpenTelemetry Collector is being added to receive OTLP traces.

Current design:

```text
Services / Workers
        │
        │ OTLP
        ▼
OpenTelemetry Collector
        │
        ▼
Debug exporter
```

Later this evolves into:

```text
Logs    → Loki
Metrics → Prometheus
Traces  → Tempo
              │
              ▼
            Grafana
```

---

# Technology Stack

## Application

- Python
- FastAPI
- SQLAlchemy
- Pydantic
- HTTPX
- Structlog
- Pytest

## Data

- PostgreSQL

## Messaging

- AWS SQS
- LocalStack for local development

## Containers

- Docker
- Docker Compose

## Observability

- Prometheus client libraries
- OpenTelemetry
- OpenTelemetry Collector
- structured JSON logging

## Planned Platform Stack

- Terraform
- AWS
- EKS
- ECR
- RDS
- AWS Secrets Manager
- EKS Pod Identity
- Jenkins
- Argo CD
- Helm
- Gateway API
- Istio
- Kyverno
- Argo Rollouts
- Prometheus
- Grafana
- Loki
- Tempo

---

# Repository Structure

```text
DevOps_Enterprise_Project/
│
├── README.md
├── .env.example
├── .gitignore
├── docker-compose.yml
│
├── services/
│   │
│   ├── user-service/
│   │   ├── app/
│   │   ├── tests/
│   │   ├── requirements.txt
│   │   └── Dockerfile
│   │
│   ├── order-service/
│   │   ├── app/
│   │   ├── tests/
│   │   ├── requirements.txt
│   │   └── Dockerfile
│   │
│   ├── payment-service/
│   │   ├── app/
│   │   ├── tests/
│   │   ├── requirements.txt
│   │   └── Dockerfile
│   │
│   └── notification-service/
│       ├── app/
│       ├── tests/
│       ├── requirements.txt
│       └── Dockerfile
│
├── docker/
│   ├── postgres/
│   │   └── init.sql
│   │
│   ├── localstack/
│   │   └── init-aws.sh
│   │
│   └── otel-collector/
│       └── config.yaml
│
├── tests/
│   ├── integration/
│   ├── smoke/
│   └── resilience/
│
├── scripts/
│
└── docs/
    ├── architecture/
    ├── adr/
    ├── runbooks/
    ├── postmortems/
    ├── reliability/
    └── security/
```

Some directories are intentionally reserved for later phases of the project.

---

# Running Locally

## Requirements

Install:

```text
Docker
Docker Compose
Git
```

Python is only required when running service tests directly outside containers.

---

## Environment

Create the local environment file:

```bash
cp .env.example .env
```

The real `.env` file must never be committed.

---

## Start the platform

Validate Compose configuration:

```bash
docker compose config
```

Build and start:

```bash
docker compose up --build
```

Check running containers:

```bash
docker compose ps
```

---

# Local Service Endpoints

```text
User Service
http://localhost:8001

Order Service
http://localhost:8002

Payment Service
http://localhost:8003

Notification Service
http://localhost:8004
```

Swagger:

```text
http://localhost:8001/docs
http://localhost:8002/docs
http://localhost:8003/docs
http://localhost:8004/docs
```

LocalStack:

```text
http://localhost:4566
```

---

# Example Application Flow

## 1. Create User

```http
POST /users
```

```json
{
  "name": "Example User",
  "email": "example@example.com"
}
```

---

## 2. Create Order

```http
POST /orders
```

```json
{
  "user_id": "...",
  "items": [
    {
      "sku": "BOOK-001",
      "quantity": 2,
      "unit_price_cents": 1500
    }
  ]
}
```

Order Service verifies the user through User Service before persisting the order.

---

## 3. Create Payment

```http
POST /payments
Idempotency-Key: payment-order-123
```

```json
{
  "order_id": "..."
}
```

Payment Service:

```text
retrieves Order
       ↓
validates status
       ↓
gets authoritative amount
       ↓
processes simulated payment
       ↓
stores payment
       +
stores PaymentSucceeded outbox event
```

---

## 4. Event Publication

```text
Outbox Publisher
       ↓
payment-events SQS queue
```

---

## 5. Notification Processing

```text
Notification Worker
       ↓
validates event
       ↓
checks event_id
       ↓
creates notification
       ↓
deletes SQS message
```

---

# Implemented Milestones

## Checkpoint 1 — Local Foundation

Completed:

- service directory structure,
- PostgreSQL,
- Docker Compose,
- environment configuration,
- isolated service databases.

---

## Checkpoint 2 — User Service

Completed:

- FastAPI User Service,
- user persistence,
- health endpoints,
- Docker image,
- PostgreSQL integration.

---

## Checkpoint 3 — Order Service

Completed:

- Order Service,
- service-to-service HTTP,
- User Service validation,
- order items,
- authoritative order total calculation,
- upstream timeout handling,
- dependency-health reporting,
- service-level tests.

---

## Checkpoint 4 — Payment Service

Completed:

- Payment Service,
- Order Service validation,
- mock payment provider,
- payment idempotency,
- database uniqueness constraints,
- graceful Order Service failure handling,
- payment tests.

---

## Checkpoint 5 — Asynchronous Events

Completed:

- LocalStack,
- SQS,
- dead-letter queue,
- transactional outbox,
- Payment Event Publisher,
- `payment.succeeded` event contract,
- Notification Worker,
- Notification Service,
- idempotent event consumption,
- automatic event delivery after SQS recovery.

---

## Checkpoint 6 — Observability Foundation

**Status: In progress**

Being implemented:

- request IDs,
- correlation IDs,
- improved structured JSON logs,
- OpenTelemetry,
- FastAPI tracing,
- HTTPX tracing,
- SQLAlchemy tracing,
- boto3/SQS tracing,
- distributed context propagation,
- asynchronous trace propagation,
- business metrics,
- publisher metrics,
- worker metrics,
- local OpenTelemetry Collector.

---

# Yet to Be Implemented

## Checkpoint 7 — Automated Distributed-System Testing

Planned:

- expanded unit tests,
- client/contract tests,
- integration tests,
- full end-to-end checkout test,
- automated idempotency tests,
- SQS integration tests,
- duplicate-event tests,
- dependency-failure tests,
- SQS recovery tests,
- DLQ tests.

The target end-to-end automated flow will prove:

```text
Create User
     ↓
Create Order
     ↓
Create Payment
     ↓
Transactional Outbox
     ↓
SQS
     ↓
Notification
     ↓
Assert exactly one correct notification exists
```

---

## Checkpoint 8 — Local Platform Completion

Planned:

- clean-environment bootstrap testing,
- Docker Compose cleanup,
- Makefile,
- helper scripts,
- dependency version pinning,
- container image version pinning,
- startup verification,
- complete project documentation,
- Phase 1 acceptance test.

At the end of Checkpoint 8:

```bash
docker compose up --build
```

should reproducibly start the complete local platform from a clean environment.

---

# Phase 2 — AWS Infrastructure with Terraform

Not yet implemented.

Planned infrastructure:

```text
VPC
├── public subnets
├── private subnets
├── routing
├── internet gateway
└── controlled egress

EKS
ECR
RDS PostgreSQL
SQS
Secrets Manager
S3
IAM
EKS Pod Identity
Route 53
```

Terraform will become the source of truth for infrastructure provisioning.

---

# Phase 3 — Kubernetes and GitOps

Not yet implemented.

Planned:

- Kubernetes Deployments,
- Services,
- startup probes,
- readiness probes,
- liveness probes,
- resource requests and limits,
- Horizontal Pod Autoscaling,
- PodDisruptionBudgets,
- topology spread constraints,
- Helm,
- Argo CD,
- environment promotion,
- immutable image digests.

Deployment architecture:

```text
GitHub
   │
   ▼
Jenkins CI
   │
   ├── test
   ├── scan
   ├── build
   └── push ECR
           │
           ▼
      update GitOps repo
           │
           ▼
         Argo CD
           │
           ▼
           EKS
```

Jenkins will handle CI.

Argo CD will own deployment and reconciliation.

---

# Phase 4 — Platform Security

Not yet implemented.

Planned:

- AWS Secrets Manager,
- External Secrets integration,
- EKS Pod Identity,
- least-privilege IAM,
- Trivy scanning,
- secret scanning,
- SBOM generation,
- container image signing,
- Kyverno policies,
- signed-image verification,
- non-root container policy,
- approved registries,
- required resource limits,
- required probes,
- default-deny NetworkPolicies.

---

# Phase 5 — Networking and Service Mesh

Not yet implemented.

Planned:

- Kubernetes Gateway API,
- Istio,
- service-to-service mTLS,
- retries,
- timeouts,
- traffic management,
- explicit east-west network policy.

---

# Phase 6 — Production Observability

Not yet implemented.

Planned:

```text
Prometheus → Metrics

Loki → Logs

Tempo → Traces

Grafana → Dashboards

Alertmanager → Alerts
```

Observability will cover:

- RED metrics for application services,
- resource saturation,
- queue backlog,
- outbox backlog,
- deployment health,
- database availability,
- dependency failures,
- latency,
- error rates,
- distributed traces.

---

# Phase 7 — Reliability Engineering

Not yet implemented.

Planned:

- SLIs,
- SLOs,
- error budgets,
- alert policies,
- recovery objectives,
- resilience testing,
- failure injection,
- autoscaling validation,
- dependency-failure exercises.

Example initial reliability targets:

```text
API availability       99.9%

5xx error rate         < 1%

p95 API latency        < 300 ms

successful deployments ≥ 99%

notification processing
                        99% within 30 seconds
```

These are starting project objectives and will be validated rather than treated as arbitrary universal values.

---

# Phase 8 — Progressive Delivery

Not yet implemented.

Planned:

- Argo Rollouts,
- canary deployments,
- metric-based rollout validation,
- automated abort,
- GitOps rollback,
- deployment-health monitoring.

Target flow:

```text
new release
    ↓
10% traffic
    ↓
validate metrics
    ↓
25%
    ↓
validate
    ↓
50%
    ↓
validate
    ↓
100%
```

If reliability metrics deteriorate:

```text
canary
   ↓
analysis fails
   ↓
rollout aborted
   ↓
traffic remains on known-good version
```

---

# Phase 9 — Operations and Disaster Recovery

Not yet implemented.

Planned:

- runbooks,
- incident simulations,
- postmortems,
- RDS backup validation,
- restore procedures,
- Terraform state protection,
- cluster reconstruction,
- GitOps disaster recovery.

Planned runbooks include:

```text
High API Error Rate

High API Latency

Pod CrashLoopBackOff

RDS Connection Exhaustion

Argo CD Sync Failure

SQS Backlog

DLQ Messages Detected

Deployment Failure

Certificate Failure
```

---

# Engineering Principles

This project follows several deliberate principles.

### Database ownership

Each service owns its own data.

```text
User          → user_db
Order         → order_db
Payment       → payment_db
Notification  → notification_db
```

Services communicate through APIs and events rather than cross-database queries.

### Fail fast on synchronous dependencies

HTTP dependencies use bounded timeouts.

### Avoid cascading readiness failures

A downstream service outage does not automatically make an otherwise healthy service unready.

### Assume duplicate messages

Event consumers are idempotent.

### Persist before acknowledging

SQS messages are deleted only after successful database processing.

### Prefer durable asynchronous delivery

Transactional outbox records protect against temporary SQS failures.

### Keep telemetry out of the critical path

Failure of the observability stack must not cause application failure.

### Avoid high-cardinality metrics

Unique IDs belong in logs and traces rather than Prometheus labels.

### Infrastructure will be reproducible

AWS resources will be provisioned through Terraform rather than manual console configuration.

### Git will become deployment truth

Argo CD will eventually reconcile Kubernetes state from Git rather than Jenkins directly applying manifests.

---

# Current Limitations

The project is intentionally incomplete.

Current limitations include:

- mock payment provider only,
- simulated email notifications,
- schema creation still uses application startup rather than a final migration strategy,
- no production authentication/authorization,
- no real AWS infrastructure yet,
- no Kubernetes deployment yet,
- no GitOps yet,
- no service mesh yet,
- no centralized log backend yet,
- no Prometheus server/Grafana dashboards yet,
- no production SLO alerting yet,
- no progressive delivery yet.

These are tracked as subsequent project phases rather than hidden as completed functionality.

---

# Why This Project Exists

The purpose of this repository is not simply to demonstrate that several tools can be installed.

The project is intended to demonstrate how the pieces interact:

```text
Application architecture
        +
distributed systems
        +
CI/CD
        +
Kubernetes
        +
AWS
        +
security
        +
observability
        +
reliability engineering
```

Each technology is introduced only when the architecture provides a reason for it.

For example:

```text
HTTP dependencies
      → timeouts and distributed tracing

SQS
      → asynchronous processing

at-least-once delivery
      → idempotent consumers

PostgreSQL + SQS
      → transactional outbox

multiple processes
      → per-process metrics

distributed failures
      → observability and SLOs

Kubernetes
      → probes, autoscaling and disruption policies

production deployment
      → GitOps and progressive delivery
```

The end goal is a system that can be **built, deployed, observed, secured, operated, failed, recovered, and explained**, rather than merely deployed once.