---
title: Aspire Dashboard
ring: adopt
quadrant: staples
tags: [observability, opentelemetry]
---

The [Aspire Dashboard](https://aspire.dev/dashboard/) is a lightweight web UI that displays OpenTelemetry logs, traces, and metrics received over OTLP.

SAF runs the dashboard [standalone](https://aspire.dev/dashboard/#run-the-dashboard-standalone) as a local observability viewer for the solution stack. SAF Desktop Orchestrator starts it automatically with `saf run`, so developers can follow logs and traces across the app backend server, frontend server, product instances, and other services from a single place.
