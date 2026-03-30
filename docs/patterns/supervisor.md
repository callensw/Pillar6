# Supervisor Pattern

The Supervisor pattern uses a coordinator agent that analyses a task,
delegates sub-tasks to specialist agents, and synthesises their results.

## When to Use

- Tasks requiring multiple areas of expertise
- Workflows where subtasks can be solved independently
- Scenarios benefiting from divide-and-conquer
- Building multi-agent systems

## How It Works

```
1. ANALYSE    -- Supervisor LLM identifies which specialists are needed
2. DELEGATE   -- Send sub-tasks to specialist agents
3. EXECUTE    -- Specialists run independently (sequential or parallel)
4. SYNTHESISE -- Supervisor combines results into a final response
```

## Full Example

```python
import asyncio
from pillar6.agents.patterns import ReActAgent, SupervisorAgent, SupervisorConfig
from pillar6.config.models import Pillar6Config, SecurityConfig
from pillar6.core.eval import MockLLMAdapter

config = Pillar6Config(security=SecurityConfig(default_deny=False))

# Create specialist agents
researcher_llm = MockLLMAdapter(default_response="Research findings: AI is advancing rapidly.")
researcher = ReActAgent(config=config, llm=researcher_llm)

writer_llm = MockLLMAdapter(default_response="Article: AI continues to transform industries.")
writer = ReActAgent(config=config, llm=writer_llm)

# Create supervisor
supervisor_llm = MockLLMAdapter(
    responses={
        "write": '[{"specialist": "researcher", "sub_task": "Research AI trends"}, '
                 '{"specialist": "writer", "sub_task": "Write article"}]',
    },
    default_response="Combined: The research shows AI is advancing, as detailed in the article.",
)

supervisor = SupervisorAgent(
    supervisor_config=SupervisorConfig(execution_mode="sequential"),
    config=config,
    llm=supervisor_llm,
)

# Register specialists
supervisor.register_specialist("researcher", researcher, "Finds and analyses information")
supervisor.register_specialist("writer", writer, "Writes articles and summaries")

result = asyncio.run(supervisor.run("Write an article about AI trends"))
print(result)
```

## Configuration

```python
from pillar6.agents.patterns import SupervisorConfig

config = SupervisorConfig(
    execution_mode="sequential",    # "sequential" or "parallel"
    max_specialists_per_task=5,     # Max specialists to delegate to
)
```

## Execution Modes

| Mode | Description | Best for |
|------|-------------|----------|
| `sequential` | Specialists run one at a time | When results depend on each other |
| `parallel` | Specialists run concurrently | Independent subtasks, faster execution |

## Error Handling

- If a specialist fails, the error is captured and passed to the synthesis step
- The supervisor can still produce a response using partial results
- Unknown specialist names result in an error message (not a crash)

## Tips

- **Write clear specialist descriptions** so the supervisor LLM can route accurately.
- **Use `parallel` mode** when subtasks are independent for faster execution.
- **Limit `max_specialists_per_task`** to control cost and complexity.
- **Specialists can be any BaseAgent subclass** including other patterns (ReAct, PlanExecute, or even nested Supervisors).
