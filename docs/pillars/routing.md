# Efficiency & Routing

The Routing pillar selects the optimal model for each request based on
constraints, manages fallback chains, tracks costs, and provides semantic caching.

## Key Concepts

### Model Profiles

Each model has a profile describing its capabilities and costs:

```python
from pillar6.types import ModelProfile, ModelTier

profile = ModelProfile(
    name="claude-sonnet-4-20250514",
    tier=ModelTier.BALANCED,
    cost_per_1k_input=0.003,
    cost_per_1k_output=0.015,
    avg_latency_ms=1000.0,
    max_tokens=4096,
    provider="anthropic",
)
```

### Constraint-Based Routing

The router filters available models by constraints and selects the most
cost-efficient option:

1. Filter by `preferred_tier`
2. Filter by `max_latency_ms`
3. Filter by `max_cost_per_token`
4. Sort by cost efficiency (lowest cost per token)

### Fallback Chains

When a model fails, the router provides the next model in the fallback chain:

```
claude-sonnet -> gpt-4o -> claude-haiku
gpt-4o -> claude-sonnet -> gpt-4o-mini
```

## Configuration

```python
from pillar6.config.models import RouterConfig

config = RouterConfig(
    default_model="claude-sonnet-4-20250514",
    enable_caching=True,
    cache_ttl_seconds=300,
    max_cost_usd=10.0,
)
```

## Usage

### Basic Routing

```python
from pillar6.core.router import DefaultRouter
from pillar6.types import LLMRequest, RouteConstraints

router = DefaultRouter(config)

request = LLMRequest(
    messages=[...],
    metadata={"constraints": RouteConstraints(
        preferred_tier="balanced",
        max_latency_ms=2000.0,
    ).model_dump()},
)

model = await router.route(request)
print(model)  # "claude-sonnet-4-20250514"
```

### Fallback Chains

```python
# Get the next fallback for a model
next_model = await router.get_fallback("claude-sonnet-4-20250514")
print(next_model)  # "gpt-4o"

# Skip models that have already been tried
next_model = await router.get_fallback(
    "claude-sonnet-4-20250514",
    tried=["gpt-4o"],
)
print(next_model)  # "claude-haiku-4-5-20251001"
```

### Cost Tracking

```python
from pillar6.types import TokenUsage

usage = TokenUsage(prompt_tokens=100, completion_tokens=50, total_tokens=150)
await router.track_cost("agent-1", "claude-sonnet-4-20250514", usage)

summary = await router.get_cost_summary()
print(f"Total cost: ${summary.total_cost_usd:.4f}")
print(f"Total tokens: {summary.total_tokens}")
print(f"By model: {summary.by_model}")
```

### Semantic Caching

When enabled, identical requests return cached responses:

```python
config = RouterConfig(enable_caching=True, cache_ttl_seconds=300)
router = DefaultRouter(config)

# First call: cache miss
cached = await router.check_cache("model", "system prompt", "user message")
# cached is None

# Store result
await router.store_cache("model", "system prompt", "user message", "response")

# Second call: cache hit
cached = await router.check_cache("model", "system prompt", "user message")
# cached == "response"
```

### Custom Model Profiles

Register your own models:

```python
router.register_model(ModelProfile(
    name="my-custom-model",
    tier=ModelTier.FAST,
    cost_per_1k_input=0.001,
    cost_per_1k_output=0.002,
    avg_latency_ms=200.0,
))
```
