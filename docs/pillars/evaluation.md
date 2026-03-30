# Testing & Evaluation

The Evaluation pillar provides mock adapters, chaos testing, scoring heuristics,
dataset-driven evaluation, and run comparison.

## Key Concepts

### Scoring

Outputs are scored using a cascade:

1. **Exact match** (case-insensitive, stripped): score = 1.0
2. **Contains match** (expected is a substring): score = 0.8
3. **Word similarity** (Jaccard-like overlap): score = 0.0 - 1.0

### MockLLMAdapter

Returns predetermined responses based on pattern matching against the input.
Essential for deterministic testing.

### ChaosToolWrapper

Wraps a tool handler and randomly injects failures or delays. Use it to
test your agent's resilience to tool failures.

## Configuration

```python
from pillar6.config.models import EvalConfig

config = EvalConfig(
    pass_threshold=0.7,       # Minimum score to pass
    max_parallel_evals=3,
)
```

## Usage

### MockLLMAdapter

```python
from pillar6.core.eval import MockLLMAdapter

llm = MockLLMAdapter(
    responses={
        "weather": "It's sunny and 25C.",
        "translate": "Bonjour le monde!",
    },
    default_response="I don't know.",
)

# Input containing "weather" -> "It's sunny and 25C."
# Input containing "translate" -> "Bonjour le monde!"
# Anything else -> "I don't know."
```

### Running Evaluations

```python
from pillar6.core.eval import DefaultEvalSuite
from pillar6.types import EvalDataset

suite = DefaultEvalSuite()

dataset = EvalDataset.from_list([
    {"input": "What is 2+2?", "expected_output": "4"},
    {"input": "Capital of France?", "expected_output": "Paris"},
])

report = await suite.run_eval(agent, dataset)
print(f"Pass rate: {report.pass_rate:.0%}")
print(f"Average score: {report.avg_score:.2f}")
print(f"Passed: {report.passed}/{report.total_cases}")
```

### Loading Datasets from JSON

```python
# From a JSON file
dataset = EvalDataset.from_json("tests/fixtures/eval_data.json")

# JSON format (list of objects):
# [
#   {"input": "question 1", "expected_output": "answer 1"},
#   {"input": "question 2", "expected_output": "answer 2"}
# ]
```

### Comparing Runs

```python
report_a = await suite.run_eval(agent_v1, dataset)
report_b = await suite.run_eval(agent_v2, dataset)

comparison = await suite.compare(report_a, report_b)
print(f"Score diff: {comparison.score_diff:+.2f}")
print(f"Improved: {comparison.improved}")
print(f"Cases improved: {comparison.improved_cases}")
print(f"Cases regressed: {comparison.regressed_cases}")
```

### ChaosToolWrapper

Test your agent's resilience to tool failures:

```python
from pillar6.core.eval import ChaosToolWrapper

async def reliable_search(query: str) -> str:
    return f"Results for: {query}"

# Wrap with 30% failure rate and 20% chance of 500ms delay
chaos_search = ChaosToolWrapper(
    handler=reliable_search,
    failure_rate=0.3,
    delay_ms=500.0,
    delay_rate=0.2,
)

# Register the chaos-wrapped version
registry.register("search", chaos_search, schema)
```

### Custom Judging

Subclass `DefaultEvalSuite` to use an LLM-as-judge:

```python
from pillar6.core.eval import DefaultEvalSuite
from pillar6.types import EvalResult

class LLMJudge(DefaultEvalSuite):
    async def judge(self, output, expected, rubric=None):
        # Call your LLM to judge the output
        # Return an EvalResult with score and reasoning
        ...
```
