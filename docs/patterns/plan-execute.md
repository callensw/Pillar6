# Plan-Execute Pattern

The Plan-Execute pattern separates planning from execution. The agent first
creates a complete plan, then executes each step. If a step fails, it can
generate a revised plan.

## When to Use

- Tasks with a clear structure that can be broken into steps
- Multi-step workflows where order matters
- Scenarios where you want visibility into the plan before execution
- Tasks that benefit from replanning on failure

## How It Works

```
1. PLAN    -- LLM generates a numbered step-by-step plan
2. EXECUTE -- Execute each step (tool call or LLM reasoning)
3. REPLAN  -- If a step fails, generate a revised plan
4. REPEAT  -- Continue until all steps complete or max_replans exceeded
```

The LLM is prompted to produce a plan in this format:

```
1. Search for information about the topic [tool:search] [args:{"query": "topic"}]
2. Analyse the results [expect:key findings]
3. Write a summary
```

## Full Example

```python
import asyncio
from pillar6.agents.patterns import PlanExecuteAgent, PlanExecuteConfig
from pillar6.config.models import Pillar6Config, SecurityConfig
from pillar6.core.eval import MockLLMAdapter

async def search(query: str) -> str:
    return f"Found 3 results for: {query}"

llm = MockLLMAdapter(
    responses={
        "plan": '1. Search for info [tool:search] [args:{"query": "AI"}]\n2. Summarize',
    },
    default_response="AI is artificial intelligence used in many fields.",
)

agent = PlanExecuteAgent(
    plan_config=PlanExecuteConfig(max_replans=2, allow_replan=True),
    config=Pillar6Config(security=SecurityConfig(default_deny=False)),
    llm=llm,
)

agent.tool_registry.register(
    "search",
    search,
    {"properties": {"query": {"type": "string"}}, "required": ["query"]},
)

result = asyncio.run(agent.run("Tell me about AI"))
print(result)
```

## Configuration

```python
from pillar6.agents.patterns import PlanExecuteConfig

config = PlanExecuteConfig(
    max_replans=2,       # Maximum number of replanning attempts
    allow_replan=True,   # Whether to replan on step failure
)
```

## Plan Format

Steps can include optional metadata:

| Annotation | Format | Purpose |
|-----------|--------|---------|
| Tool | `[tool:tool_name]` | Tool to execute for this step |
| Arguments | `[args:{"key": "value"}]` | JSON arguments for the tool |
| Expected | `[expect:description]` | Expected output (for documentation) |

## Tips

- **Keep plans short** (3-7 steps). Longer plans are more likely to need replanning.
- **Set `allow_replan=True`** for resilience against transient failures.
- **Limit `max_replans`** to prevent infinite replan loops (2-3 is typical).
- **Use tool steps** for actions with clear inputs/outputs, and LLM steps for reasoning.
