# M11 Idea: Durable Webhook Dispatch Pipeline

Date: 2026-05-16
Methodology: spec-first

## Problem

M10 made webhook triggers usable from the UI, but webhook ingestion still stops at a `pending` execution record. That is useful for auditability, yet not enough for a serious automation product: incoming webhook events must move into an executable pipeline that can be claimed, run, retried, observed, and later scaled into a worker.

## Product Bet

Build the first durable dispatch layer between webhook ingestion and workflow execution.

The first M11 slice should not attempt a full distributed queue. It should create the internal contract that a worker can rely on:

- find pending webhook-triggered executions;
- dispatch them through the existing executor;
- leave non-webhook pending executions alone;
- preserve tenant isolation through execution/workflow IDs already stored on the execution;
- keep raw webhook headers redacted;
- produce deterministic test coverage before a background loop is introduced.

## User Journey

As an operator, I want webhook-triggered workflow runs to move from `pending` to an executed terminal state, so that external systems can trigger real automation instead of only creating stored events.

As a platform maintainer, I want the dispatch mechanism to be a testable service first, so that a future worker loop can run the same logic safely.

## First Slice

M11 Slice 1 creates a backend dispatcher service and tests:

- webhook ingestion still returns `202` with `pending`;
- dispatcher scans pending webhook executions;
- dispatcher runs those executions through the existing executor;
- dispatcher skips non-webhook pending executions;
- dispatcher respects a batch limit.

## Out Of Scope

- no distributed queue yet;
- no Redis/SQS/Celery dependency;
- no recurring background loop in this slice;
- no webhook signing;
- no retry backoff policy yet;
- no UI controls for the dispatcher yet.
