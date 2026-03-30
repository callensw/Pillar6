# Build Agents from Scratch

Build a working agent with tools using Pillar6's built-in patterns.

!!! tip
    If you already have agents built with another framework, see
    [Add Pillar6 to Existing Agents](wrapping.md) instead — it's faster.

## 1. Create a Tool

Define an async function that your agent can call:

```python
async def get_weather(city: str) -> str:
    """Look up the weather for a city (mock implementation)."""
    forecasts = {
        "london": "Cloudy, 15C",
        "tokyo": "Sunny, 25C",
        "new york": "Rainy, 18C",
    }
    return forecasts.get(city.lower(), f"No data for {city}")
```

## 2. Configure and Create the Agent

```python
from pillar6 import BaseAgent, Pillar6Config
from pillar6.config.models import SecurityConfig
from pillar6.core.eval import MockLLMAdapter

config = Pillar6Config(
    security=SecurityConfig(default_deny=False),
)

# Use a mock LLM for this example
llm = MockLLMAdapter(
    responses={"weather": "The weather in London is Cloudy, 15C."},
    default_response="I can help you check the weather!",
)

agent = BaseAgent(config=config, llm=llm)
```

## 3. Register the Tool

```python
agent.tool_registry.register(
    "get_weather",
    get_weather,
    {
        "properties": {
            "city": {"type": "string", "description": "City name"},
        },
        "required": ["city"],
    },
)
```

## 4. Run the Agent

```python
import asyncio

async def main():
    result = await agent.run("What is the weather in London?")
    print(result)

asyncio.run(main())
```

## 5. View the Trace

After the agent runs, you can inspect what happened:

```python
async def main_with_trace():
    result = await agent.run("What is the weather in London?")
    print("Result:", result)

    # Get metrics
    metrics = agent.observability.get_metrics()
    for m in metrics:
        print(f"  {m['name']}: {m['value']}")

asyncio.run(main_with_trace())
```

## Using Agent Patterns

For more complex tasks, use one of the built-in patterns:

```python
from pillar6.agents.patterns import ReActAgent, ReActConfig

agent = ReActAgent(
    react_config=ReActConfig(max_steps=5),
    config=config,
    llm=llm,
)
result = await agent.run("What is the weather in London?")
```

See the [Patterns](../patterns/react.md) section for full guides on each pattern.

## Next Steps

- [Concepts](concepts.md) — Understand the six production pillars
- [Context Management](../pillars/context-management.md) — Deep dive into context handling
- [Tool Orchestration](../pillars/tool-orchestration.md) — Advanced tool features
