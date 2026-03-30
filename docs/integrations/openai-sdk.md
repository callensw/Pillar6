# OpenAI SDK Integration

Add Pillar6 production monitoring to your raw OpenAI SDK calls.

## Installation

```bash
pip install pillar6 openai
```

## 5-Minute Setup

```python
from openai import AsyncOpenAI
from pillar6.wrappers.sdk import wrap_client

# Your existing client
client = wrap_client(AsyncOpenAI())

# Use exactly like normal — every call is now monitored
response = await client.chat.completions.create(
    model="gpt-4o",
    messages=[{"role": "user", "content": "Explain quantum computing"}],
)
print(response.choices[0].message.content)
```

## Full Example

```python
from openai import AsyncOpenAI
from pillar6 import Pillar6Config
from pillar6.config.models import SecurityConfig
from pillar6.wrappers.sdk import wrap_client

config = Pillar6Config(
    security=SecurityConfig(
        enable_input_validation=True,
    ),
)

client = wrap_client(AsyncOpenAI(), config=config)

response = await client.chat.completions.create(
    model="gpt-4o",
    messages=[{"role": "user", "content": "Hello!"}],
)

# View cost summary
summary = await client.costs.get_cost_summary()
print(f"Total cost: ${summary.total_cost_usd:.4f}")
```

## What You Get

- **Automatic token tracking** — prompt and completion tokens extracted from every response
- **Cost calculation** — real-time cost tracking per model
- **Input validation** — message content checked for prompt injection
- **Distributed tracing** — every API call traced with timing

## Advanced Configuration

```python
from pillar6 import Pillar6Config
from pillar6.config.models import RouterConfig

config = Pillar6Config(
    router=RouterConfig(max_cost_usd=10.0),
)

client = wrap_client(AsyncOpenAI(), config=config)
```
