# Anthropic SDK Integration

Add Pillar6 production monitoring to your raw Anthropic SDK calls.

## Installation

```bash
pip install pillar6 anthropic
```

## 5-Minute Setup

```python
from anthropic import AsyncAnthropic
from pillar6.wrappers.sdk import wrap_client

# Your existing client
client = wrap_client(AsyncAnthropic())

# Use exactly like normal — every call is now monitored
response = await client.messages.create(
    model="claude-sonnet-4-20250514",
    max_tokens=1024,
    messages=[{"role": "user", "content": "Explain quantum computing"}],
)
print(response.content[0].text)
```

## Full Example

```python
from anthropic import AsyncAnthropic
from pillar6 import Pillar6Config
from pillar6.config.models import SecurityConfig
from pillar6.wrappers.sdk import wrap_client

config = Pillar6Config(
    security=SecurityConfig(
        enable_input_validation=True,
        blocked_patterns=[r"ignore\s+instructions"],
    ),
)

client = wrap_client(AsyncAnthropic(), config=config)

response = await client.messages.create(
    model="claude-sonnet-4-20250514",
    max_tokens=1024,
    messages=[{"role": "user", "content": "Hello!"}],
)

# View traces
events = await client.traces.get_trace(client.traces._traces[-1][0] if client.traces._traces else "")

# View cost summary
summary = await client.costs.get_cost_summary()
print(f"Total cost: ${summary.total_cost_usd:.4f}")
print(f"Total tokens: {summary.total_tokens}")
```

## What You Get

- **Automatic token tracking** — input and output tokens extracted from every response
- **Cost calculation** — real-time cost tracking per model
- **Input validation** — message content checked for prompt injection
- **Distributed tracing** — every API call traced with timing
- **Security checks** — all message content validated before sending

## Advanced Configuration

```python
from pillar6 import Pillar6Config
from pillar6.config.models import RouterConfig, SecurityConfig

config = Pillar6Config(
    router=RouterConfig(max_cost_usd=5.0),
    security=SecurityConfig(max_input_length=100_000),
)

client = wrap_client(AsyncAnthropic(), config=config)
```
