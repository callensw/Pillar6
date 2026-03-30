# Add Pillar6 to Your Existing Agents

The fastest way to get production infrastructure for your AI agents. No
rewriting required — just wrap your existing code.

## `pillar6_wrap()` — Wrap Any Function

The simplest integration: wrap any function that takes a string and returns
a string.

```python
from pillar6 import pillar6_wrap

async def my_agent(query: str) -> str:
    # Your existing agent logic — any framework, any LLM
    response = await call_my_llm(query)
    return response

# One line to add production infrastructure
agent = pillar6_wrap(my_agent)
result = await agent("What is quantum computing?")
```

What you get automatically:

- **Tracing** — every call is traced with timing and events
- **Security** — input validation and prompt injection detection
- **Cost tracking** — duration metrics for every call
- **Audit trail** — all actions logged

### Sync functions work too

```python
def my_sync_agent(query: str) -> str:
    return call_llm_sync(query)

agent = pillar6_wrap(my_sync_agent)
result = await agent("hello")  # automatically wrapped in async
```

### Custom configuration

```python
from pillar6 import Pillar6Config, pillar6_wrap
from pillar6.config.models import SecurityConfig

config = Pillar6Config(
    security=SecurityConfig(
        max_input_length=50_000,
        blocked_patterns=[r"secret", r"password"],
    ),
)

agent = pillar6_wrap(my_agent, config=config)
```

## `@pillar6_monitor` Decorator

For a cleaner syntax when defining agents inline:

```python
from pillar6 import pillar6_monitor

@pillar6_monitor
async def my_agent(query: str) -> str:
    response = await client.messages.create(
        model="claude-sonnet-4-20250514",
        messages=[{"role": "user", "content": query}],
    )
    return response.content[0].text

result = await my_agent("Explain transformers")
```

With configuration:

```python
@pillar6_monitor(config=my_config)
async def my_agent(query: str) -> str:
    ...
```

## SDK Wrapping

The lowest-friction integration — one line to monitor every API call.

### Anthropic SDK

```python
from anthropic import AsyncAnthropic
from pillar6.wrappers.sdk import wrap_client

client = wrap_client(AsyncAnthropic())

# Use exactly like normal
response = await client.messages.create(
    model="claude-sonnet-4-20250514",
    messages=[{"role": "user", "content": "Hello"}],
)
# Token usage and costs are now tracked automatically
```

### OpenAI SDK

```python
from openai import AsyncOpenAI
from pillar6.wrappers.sdk import wrap_client

client = wrap_client(AsyncOpenAI())

response = await client.chat.completions.create(
    model="gpt-4o",
    messages=[{"role": "user", "content": "Hello"}],
)
```

## LangChain Wrapping

```python
from pillar6.wrappers.langchain import wrap_langchain

production_chain = wrap_langchain(my_chain)
result = await production_chain.ainvoke({"query": "Explain quantum computing"})

# Access traces
events = await production_chain.traces.get_trace(production_chain.last_workflow_id)
```

Install with: `pip install pillar6[langchain]`

## CrewAI Wrapping

```python
from pillar6.wrappers.crewai import wrap_crew

production_crew = wrap_crew(my_crew)
result = production_crew.kickoff()

# Each agent in the crew gets its own trace span
events = await production_crew.traces.get_trace(production_crew.last_workflow_id)
```

Install with: `pip install pillar6[crewai]`

## Accessing Pillar Data After Wrapping

Every wrapped agent exposes the pillar instances as attributes:

```python
agent = pillar6_wrap(my_func)
await agent("test query")

# Observability
events = await agent.traces.get_trace(agent.last_workflow_id)
metrics = agent.traces.get_metrics()
logs = agent.traces.get_logs()

# Cost tracking
summary = await agent.costs.get_cost_summary()

# Security
audit = agent.security.get_audit_log("default")

# Evaluation
report = await agent.evals.run_eval(...)
```

## Next Steps

- [Concepts](concepts.md) — Understand the six production pillars
- [Anthropic SDK Guide](../integrations/anthropic-sdk.md) — Full Anthropic integration guide
- [LangChain Guide](../integrations/langchain.md) — Full LangChain integration guide
