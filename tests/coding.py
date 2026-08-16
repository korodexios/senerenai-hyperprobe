"""
Coding Test Prompts — Hard Level
=================================
Categories:
  1. Algorithm Implementation (novel problem, correct solution required)
  2. System Code (real-world patterns: async, threading, I/O)
  3. Bug Fixing (given broken code, produce a fix)
  4. Code from Spec (translate requirements to code)
  5. Refactoring (transform existing code while preserving behavior)

Each prompt tests:
  - Syntactic correctness (must parse/compile)
  - Semantic correctness (must solve the actual problem)
  - Code quality (clean, idiomatic, no unnecessary complexity)
  - Hallucination resistance (no made-up APIs or libraries)
  - Instruction following (does exactly what asked)
"""

CODING_PROMPTS = [
    # ── 1. Algorithm Implementation ──
    {
        "id": "code_algo_01",
        "category": "algorithm",
        "difficulty": "hard",
        "language": "python",
        "system": "You are an expert Python developer. Write clean, correct, minimal code.",
        "prompt": """Write a Python function that implements an LRU cache with O(1) get and put operations.

Requirements:
- `class LRUCache(capacity: int)`
- `get(key: int) -> int` returns -1 if not found
- `put(key: int, value: int)` evicts least recently used when at capacity
- Must be O(1) for both operations
- Do NOT use `functools.lru_cache` or `collections.OrderedDict`
- Implement using a doubly linked list + hash map

Include a `__repr__` that shows the cache contents in MRU→LRU order.
Include 5 test cases that verify correctness including eviction behavior.""",
        "eval_notes": "Must have DLL + dict, O(1) complexity, working eviction, valid test cases.",
    },

    {
        "id": "code_algo_02",
        "category": "algorithm",
        "difficulty": "hard",
        "language": "python",
        "system": "You are an expert Python developer.",
        "prompt": """Implement Dijkstra's shortest path algorithm for a weighted directed graph.

Requirements:
- Input: adjacency list as `dict[str, list[tuple[str, float]]]` (node → [(neighbor, weight)])
- Function signature: `def dijkstra(graph, start, end) -> tuple[float, list[str]]`
- Returns (total_cost, path_as_list_of_nodes) or (float('inf'), []) if no path
- Must use a min-heap (heapq)
- Handle: disconnected nodes, self-loops, negative weight detection (raise ValueError)

Include 4 test cases: simple path, no path, single node, negative weight error.""",
        "eval_notes": "Must use heapq, reconstruct path, handle edge cases, raise on negative weights.",
    },

    {
        "id": "code_algo_03",
        "category": "algorithm",
        "difficulty": "medium",
        "language": "python",
        "system": "You are a Python developer. Write efficient code.",
        "prompt": """Write a function that merges K sorted lists into one sorted list.

Signature: `def merge_k_sorted(lists: list[list[int]]) -> list[int]`

Requirements:
- Must use a min-heap approach (not just flatten+sort)
- Handle empty lists in the input
- Handle completely empty input
- Time complexity must be O(N log K) where N = total elements, K = number of lists

Include 5 test cases including edge cases.""",
        "eval_notes": "Must use heap with list index tracking, handle empties, correct complexity.",
    },

    # ── 2. System Code ──
    {
        "id": "code_sys_01",
        "category": "system",
        "difficulty": "medium",
        "language": "python",
        "system": "You are a Python developer specializing in async I/O.",
        "prompt": """Write an async Python HTTP retry wrapper using aiohttp.

Requirements:
- `async def fetch_with_retry(url, max_retries=3, backoff_factor=0.5, timeout=10)`
- Retries on: 429, 500, 502, 503, 504 status codes
- Exponential backoff: wait = backoff_factor * (2 ** attempt)
- Respects Retry-After header if present on 429
- Raises after max_retries exhausted
- Returns the response JSON on success

Use only `aiohttp` and `asyncio`. Include type hints throughout.""",
        "eval_notes": "Must handle Retry-After, exponential backoff math, proper async/await, type hints.",
    },

    {
        "id": "code_sys_02",
        "category": "system",
        "difficulty": "hard",
        "language": "python",
        "system": "You are a Python systems programmer.",
        "prompt": """Implement a simple task queue with worker pool using only Python standard library.

Requirements:
- `class TaskQueue(num_workers: int)`
- `submit(fn, *args, **kwargs) -> Future` - submit a callable
- `shutdown(wait=True)` - graceful shutdown
- Workers pull from a thread-safe queue
- Future objects support `.result(timeout=None)` and `.done()`
- Handle worker crashes gracefully
- NOT using concurrent.futures (implement from scratch with threading + queue)

Include a demo showing 10 tasks submitted to 3 workers.""",
        "eval_notes": "Must use threading.Thread + queue.Queue, custom Future class, error isolation.",
    },

    # ── 3. Bug Fixing ──
    {
        "id": "code_fix_01",
        "category": "bugfix",
        "difficulty": "medium",
        "language": "python",
        "system": "You are a senior Python developer. Find and fix all bugs.",
        "prompt": """Fix all bugs in this code. Explain each bug briefly.

```python
import threading

class BankAccount:
    def __init__(self, balance=0):
        self.balance = balance
        self.lock = threading.Lock()

    def deposit(self, amount):
        self.lock.acquire()
        new_balance = self.balance + amount
        self.balance = new_balance
        self.lock.release()
        return new_balance

    def withdraw(self, amount):
        self.lock.acquire()
        if self.balance >= amount:
            new_balance = self.balance - amount
            self.balance = new_balance
            self.lock.release()
            return new_balance
        return -1  # insufficient funds

    def transfer(self, other, amount):
        self.lock.acquire()
        other.lock.acquire()
        withdrawn = self.withdraw(amount)
        if withdrawn != -1:
            other.deposit(amount)
        other.lock.release()
        self.lock.release()

a = BankAccount(1000)
b = BankAccount(500)
a.transfer(b, 200)
print(f"A: {a.balance}, B: {b.balance}")
```

Provide the corrected version with all bugs fixed.""",
        "eval_notes": "Bugs: withdraw doesn't release lock on failure, transfer causes deadlock (nested locks + withdraw re-acquires).",
    },

    {
        "id": "code_fix_02",
        "category": "bugfix",
        "difficulty": "hard",
        "language": "python",
        "system": "You are a senior Python developer. Find and fix ALL concurrency bugs.",
        "prompt": """This async code has multiple concurrency bugs. Find and fix ALL of them.

```python
import asyncio

class AsyncCache:
    def __init__(self):
        self.cache = {}
        self.pending = {}

    async def get_or_compute(self, key, compute_fn):
        if key in self.cache:
            return self.cache[key]

        if key in self.pending:
            return await self.pending[key]

        self.pending[key] = compute_fn(key)
        try:
            result = await self.pending[key]
            self.cache[key] = result
            return result
        finally:
            del self.pending[key]

async def main():
    cache = AsyncCache()
    async def slow_compute(key):
        await asyncio.sleep(1)
        return f"value_{key}"
    results = await cache.get_many(["a", "b", "a", "c", "b"], slow_compute)
    print(results)

asyncio.run(main())
```""",
        "eval_notes": "Bugs: race condition on pending, get_many is sequential not concurrent, pending stores coroutine not Task.",
    },

    # ── 4. Code from Spec ──
    {
        "id": "code_spec_01",
        "category": "from_spec",
        "difficulty": "medium",
        "language": "python",
        "system": "You are a Python developer. Implement from spec.",
        "prompt": """Implement a simple expression evaluator from this spec:

GRAMMAR:
  expr     → term (('+' | '-') term)*
  term     → factor (('*' | '/') factor)*
  factor   → NUMBER | '(' expr ')' | '-' factor
  NUMBER   → [0-9]+ ('.' [0-9]+)?

REQUIREMENTS:
- `def evaluate(expression: str) -> float`
- Recursive descent parser (no eval/exec/ast)
- Handle: operator precedence, parentheses, unary minus, decimals
- Raise `ValueError` with descriptive message on invalid input
- Examples: "3 + 4 * 2" → 11.0, "-(3 + 4) * 2" → -14.0

Include 8 test cases covering all grammar rules and error cases.""",
        "eval_notes": "Must implement recursive descent, handle precedence correctly, no eval() cheating.",
    },

    {
        "id": "code_spec_02",
        "category": "from_spec",
        "difficulty": "hard",
        "language": "python",
        "system": "You are an expert Python developer. Write clean, tested code.",
        "prompt": """Implement a simple event emitter/pub-sub system with these exact features:

```python
class EventEmitter:
    on(event: str, handler: Callable) -> Callable  # returns unsubscribe function
    once(event: str, handler: Callable) -> Callable  # auto-removes after first call
    emit(event: str, *args, **kwargs) -> int  # returns number of handlers called
    off(event: str, handler: Callable) -> bool  # returns True if handler was found
```

Requirements:
- Thread-safe for on/off/emit (use threading.Lock)
- `once` handlers fire exactly once then auto-remove
- `emit` during `emit` (re-entrant) must work correctly

Include comprehensive tests for all features including re-entrancy.""",
        "eval_notes": "Must handle re-entrancy (iterate copy), thread safety.",
    },

    # ── 5. Refactoring ──
    {
        "id": "code_refactor_01",
        "category": "refactoring",
        "difficulty": "medium",
        "language": "python",
        "system": "You are a Python refactoring expert.",
        "prompt": """Refactor this code to eliminate duplication and deep nesting. Use strategy pattern or similar. Preserve exact behavior.

```python
def process_order(order):
    if order['type'] == 'digital':
        if order['status'] == 'pending':
            price = order['base_price']
            if order.get('coupon'):
                if order['coupon']['type'] == 'percent':
                    price = price * (1 - order['coupon']['value'] / 100)
                elif order['coupon']['type'] == 'fixed':
                    price = price - order['coupon']['value']
                    if price < 0: price = 0
            tax = price * 0.10
            total = price + tax
            order['total'] = total
            order['status'] = 'processed'
            order['delivery'] = 'email'
            return order
        elif order['status'] == 'processed':
            return order
    elif order['type'] == 'physical':
        if order['status'] == 'pending':
            price = order['base_price']
            if order.get('coupon'):
                if order['coupon']['type'] == 'percent':
                    price = price * (1 - order['coupon']['value'] / 100)
                elif order['coupon']['type'] == 'fixed':
                    price = price - order['coupon']['value']
                    if price < 0: price = 0
            weight = order.get('weight', 0)
            shipping = 5.99 if weight < 1 else 9.99 if weight < 5 else 14.99 if weight < 20 else 24.99
            tax = price * 0.10
            total = price + tax + shipping
            order['total'] = total
            order['status'] = 'processed'
            order['delivery'] = 'shipping'
            return order
    raise ValueError(f"Unknown order type: {order['type']}")
```

Include a brief explanation of changes.""",
        "eval_notes": "Should extract: apply_coupon, calc_shipping, separate digital vs physical strategies.",
    },
]

# Quick representative subset for fast phases (3 hardest-most-discriminating)
CODING_QUICK_IDS = ("code_algo_01", "code_fix_01", "code_spec_01")
CODING_QUICK = [p for p in CODING_PROMPTS if p["id"] in CODING_QUICK_IDS]
