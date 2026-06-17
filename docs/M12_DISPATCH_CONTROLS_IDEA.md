# M12 Idea: Operator-Grade Dispatch Controls

Date: 2026-05-17
Status: draft

## Problem

M11 made webhook dispatch durable and observable, but operators still cannot act on the queue.

When a webhook execution is dead-lettered, the product can show the state, but the user has no first-class recovery path. That means a production workflow can stall on a transient connector problem until someone edits database state or replays the webhook externally.

## Product Goal

Turn webhook dispatch from a background mechanism into an operator-grade workflow surface:

- recover dead-lettered executions;
- pause/resume dispatch per workflow;
- prevent noisy triggers from flooding execution slots;
- filter and inspect queue state without exposing webhook payloads or headers.

## M12 Slice Plan

Slice 1:

- manual retry for dead-lettered webhook executions via authenticated API;
- create a new pending execution with preserved lineage metadata;
- keep the source execution failed and auditable.

Slice 2:

- connector workspace action button for dead-letter retry;
- refresh queue after retry.

Slice 3:

- pause/resume dispatch per workflow.

Slice 4:

- per-trigger rate limit and queue filters.

## Non-Goals

- No external queue broker.
- No destructive mutation of failed execution history.
- No unauthenticated retry endpoint.
- No raw webhook payload/header rendering in queue UI.
