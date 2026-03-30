# CrewAI Integration

Add Pillar6 production infrastructure to your CrewAI crews.

## Installation

```bash
pip install pillar6[crewai]
```

## 5-Minute Setup

```python
from crewai import Agent, Task, Crew
from pillar6.wrappers.crewai import wrap_crew

# Your existing CrewAI code
researcher = Agent(role="Researcher", goal="Find information", ...)
writer = Agent(role="Writer", goal="Write reports", ...)
crew = Crew(agents=[researcher, writer], tasks=[...])

# Add Pillar6 — one line
production_crew = wrap_crew(crew)

# Use like normal
result = production_crew.kickoff()
```

## Full Example

```python
from pillar6 import Pillar6Config
from pillar6.wrappers.crewai import wrap_crew

config = Pillar6Config()
production_crew = wrap_crew(crew, config=config)
result = production_crew.kickoff()

# View what happened — each crew agent gets its own trace span
events = await production_crew.traces.get_trace(production_crew.last_workflow_id)
for event in events:
    print(f"[{event.event_type}] {event.message}")
```

## What You Get

- **Per-agent tracing** — each agent in the crew gets its own trace events
- **Timing metrics** — duration tracking for the full crew execution
- **Audit trail** — all kickoffs are logged

## Advanced Configuration

```python
from pillar6 import Pillar6Config
from pillar6.config.models import ObservabilityConfig

config = Pillar6Config(
    observability=ObservabilityConfig(
        enable_tracing=True,
        enable_metrics=True,
    ),
)

production_crew = wrap_crew(crew, config=config)
```
