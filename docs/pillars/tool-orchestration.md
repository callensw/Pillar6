# Tool Orchestration

The Tool Orchestration pillar handles tool registration, argument validation,
execution with retries, circuit breakers, result caching, and parallel execution.

## Key Concepts

### Circuit Breaker Pattern

Each tool has its own circuit breaker that protects against cascading failures:

```
CLOSED --[failures >= threshold]--> OPEN --[timeout elapses]--> HALF_OPEN --[success]--> CLOSED
                                                                           --[failure]--> OPEN
```

- **CLOSED**: Normal operation, failures are counted
- **OPEN**: All calls are rejected immediately
- **HALF_OPEN**: One test call is allowed through

### Retry with Exponential Backoff

Failed tool calls are retried with exponential backoff and jitter:

```
delay = base_delay * (2 ^ attempt) + random_jitter
```

## Configuration

```python
from pillar6.config.models import ToolConfig

config = ToolConfig(
    max_retries=3,
    retry_base_delay_ms=500.0,
    timeout_ms=30_000.0,
    max_concurrency=5,
    circuit_breaker_threshold=5,
    circuit_breaker_reset_ms=60_000.0,
    cache_ttl_seconds=300.0,  # 0 = disabled
)
```

## Usage

### Register a Tool

```python
from pillar6.core.tools import DefaultToolRegistry, DefaultToolExecutor

registry = DefaultToolRegistry()

async def search(query: str) -> str:
    return f"Results for: {query}"

registry.register(
    "search",
    search,
    {
        "properties": {
            "query": {"type": "string", "description": "Search query"},
        },
        "required": ["query"],
    },
)
```

### Execute a Tool

```python
from pillar6.types import ExecutionContext

executor = DefaultToolExecutor(registry)
context = ExecutionContext(agent_id="agent-1", workflow_id="wf-1")

result = await executor.execute("search", {"query": "pillar6"}, context)
print(result.output)    # "Results for: pillar6"
print(result.success)   # True
print(result.duration_ms)  # e.g. 1.5
```

### Parallel Execution

```python
from pillar6.types import ToolCall

calls = [
    ToolCall(tool_name="search", arguments={"query": "topic A"}),
    ToolCall(tool_name="search", arguments={"query": "topic B"}),
]

results = await executor.execute_parallel(calls, max_concurrency=3)
# results[0] corresponds to calls[0], etc.
```

### Result Caching

Enable caching by setting `cache_ttl_seconds` in the tool config:

```python
config = ToolConfig(cache_ttl_seconds=60.0)

registry.register("search", search, schema, config=config)
# Second call with same args returns cached result
```

### Health Check

```python
health = await registry.health_check()
for name, status in health.items():
    print(f"{name}: healthy={status.healthy}, "
          f"circuit={status.circuit_breaker_state}, "
          f"calls={status.total_calls}")
```
