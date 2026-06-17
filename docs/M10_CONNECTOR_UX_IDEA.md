# M10 Idea: Connector UX and Builder Integration

## Problem

M9 created the connector runtime, but the product still does not feel like a usable integration platform because connector setup requires API calls or handcrafted workflow JSON.

If GraphPilot is meant to become a better n8n-style workflow system, users need a fast, inspectable, low-friction way to add connector nodes, attach credentials, expose webhook triggers, and debug connector failures from the UI.

## Product Bet

The next step is not adding more connectors. The next step is making one connector feel excellent.

M10 should turn the existing `http.request` runtime into a complete workflow-building experience:

- add an HTTP Request connector node from the builder;
- configure method, URL, headers, query, and body without touching raw workflow JSON;
- select an existing credential or create one from the workflow setup path;
- create/copy webhook trigger URLs for workflows;
- inspect connector logs in execution details;
- use Workflow Doctor to recover from missing connector credentials.

## Why This Matters

n8n is powerful but can become difficult to debug when credentials, trigger payloads, runtime failures, and node configuration are spread across different surfaces.

GraphPilot can be better by making connector failure recovery part of the workflow:

1. build the node;
2. run the workflow;
3. see the exact connector failure;
4. get a Doctor diagnosis;
5. create/select the missing credential;
6. replay.

That loop is the product wedge.

## M10 Outcome

By the end of M10, a user should be able to complete this without leaving the app UI:

1. create a workflow;
2. add an HTTP Request connector node;
3. create or choose a credential;
4. configure a private URL and see it safely blocked;
5. create a webhook trigger;
6. invoke the webhook externally;
7. inspect the pending execution and connector logs;
8. get a Doctor diagnosis for a missing credential.

## Non-Goals

- More connector runtimes.
- OAuth.
- Connector marketplace.
- Durable trigger queue.
- Retry execution engine.
- Typed field mapping.
- AI-generated workflow builder.

Those become stronger after the core UX loop is real.
