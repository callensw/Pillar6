# Observability

The Observability pillar provides distributed tracing, structured logging,
metric emission, and trace export for debugging and replay.

## Key Concepts

### Trace Hierarchy

Each agent run creates a trace (identified by `workflow_id`) containing
ordered events. Events can reference parent events for nested tracing.

### Structured Logging

Logs are structured entries with level, message, agent ID, workflow ID,
and trace ID for easy correlation.

## Configuration

```python
from pillar6.config.models import ObservabilityConfig

config = ObservabilityConfig(
    enable_tracing=True,
    enable_metrics=True,
    log_level="INFO",
    trace_sample_rate=1.0,
)
```

## Usage

### Tracing

```python
from pillar6.core.observability import DefaultObservabilityLayer
from pillar6.types import TraceEvent

obs = DefaultObservabilityLayer()

# Start a trace
trace_ctx = obs.start_trace("workflow-123")

# Add events
obs.add_event(trace_ctx, TraceEvent(
    event_type="step_start",
    message="Starting tool call",
))

obs.add_event(trace_ctx, TraceEvent(
    event_type="step_end",
    message="Tool call completed",
    data={"duration_ms": 150.5},
))

# End the trace
obs.end_trace(trace_ctx)

# Retrieve events
events = await obs.get_trace("workflow-123")
for event in events:
    print(f"{event.event_type}: {event.message}")
```

### Structured Logging

```python
obs.log("INFO", "Agent started processing", trace_ctx=trace_ctx, agent_id="agent-1")
obs.log("WARNING", "Slow response detected", agent_id="agent-1", latency_ms=5000)
obs.log("ERROR", "Tool execution failed", agent_id="agent-1", tool="search")

# Retrieve logs with filtering
logs = obs.get_logs(level="ERROR", agent_id="agent-1", limit=10)
for log in logs:
    print(f"[{log.level}] {log.message} - {log.data}")
```

### Metrics

```python
# Emit metrics
await obs.emit_metric("agent.run.tokens", 1500.0, {"agent_id": "agent-1"})
await obs.emit_metric("tool.latency_ms", 250.0, {"tool": "search"})

# Retrieve metrics
all_metrics = obs.get_metrics()
token_metrics = obs.get_metrics(name="agent.run.tokens")
recent = obs.get_metrics(since=1700000000.0)
```

### Trace Export

Export a complete trace for debugging or replay:

```python
export = await obs.export_trace("workflow-123")
# Returns a JSON-serializable dict with:
# {
#     "workflow_id": "workflow-123",
#     "trace_id": "...",
#     "events": [...],
#     "metrics": [...],
#     "logs": [...],
#     "total_duration_ms": 1234.5,
# }

import json
print(json.dumps(export, indent=2))
```
