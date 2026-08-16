"""Agent and tool-calling prompts with strict JSON-output requirements.

`argument_schema` is intentionally small and portable. It captures the
requirements a benchmark can validate deterministically without pretending to
execute a tool or infer external state.
"""


def _prompt(prompt_id: str, category: str, difficulty: str, tool: str, schema: dict, system: str, prompt: str) -> dict:
    return {
        "id": prompt_id,
        "category": category,
        "difficulty": difficulty,
        "expected_tool": tool,
        "expected_args": list(schema),
        "argument_schema": schema,
        "system": system,
        "prompt": prompt,
    }


AGENT_PROMPTS = [
    _prompt(
        "agent_01_weather", "tool_calling", "easy", "get_weather",
        {
            "location": {"type": "string", "contains": "Bratislava"},
            "unit": {"type": "string", "enum": ["celsius", "C", "Celsius"]},
        },
        "You are an agent. Respond only with JSON: {\"tool\": \"name\", \"parameters\": {...}}.",
        "What is the current weather in Bratislava? Retrieve the temperature in Celsius.",
    ),
    _prompt(
        "agent_02_database", "tool_calling", "medium", "search_database",
        {
            "query": {"type": "string", "contains": "Hermes"},
            "limit": {"type": "integer", "minimum": 5},
            "filter_year": {"type": "integer", "equals": 2026},
        },
        "You are a database agent. Respond only with JSON using tool and parameters keys.",
        "Find the last five invoices issued to client Hermes in 2026.",
    ),
    _prompt(
        "agent_03_nested_order", "tool_calling", "hard", "create_order",
        {
            "customer_id": {"type": "integer", "equals": 4082},
            "priority": {"type": "boolean", "equals": True},
            "items": {
                "type": "array", "min_items": 2,
                "items": {
                    "type": "object", "required": ["sku", "qty"],
                    "properties": {
                        "sku": {"type": "string"},
                        "qty": {"type": "integer", "minimum": 1},
                    },
                },
            },
        },
        "You are an e-commerce agent. Respond only with JSON using tool and parameters keys.",
        "Create a priority order for customer 4082 containing two units of KB-990 and one unit of MS-102.",
    ),
    _prompt(
        "agent_04_routing", "tool_calling", "hard", "execute_bash_command",
        {
            "command": {"type": "string", "contains": "df -h"},
            "timeout_sec": {"type": "integer", "minimum": 1},
        },
        "Available tools: read_file, write_file, execute_bash_command, restart_server. Respond only with JSON.",
        "Determine how much free disk space remains on the server by using df -h.",
    ),
    _prompt(
        "agent_05_calendar", "tool_calling", "medium", "schedule_meeting",
        {
            "title": {"type": "string", "contains": "Project Sync"},
            "start_time": {"type": "string", "contains": "2026-09-15"},
            "attendees": {"type": "array", "min_items": 2, "items": {"type": "string"}},
        },
        "You are a calendar agent. Respond only with JSON using tool and parameters keys.",
        "Schedule a meeting titled Project Sync for 2026-09-15 at 14:00 with adam@example.com and eva@example.com.",
    ),
    _prompt(
        "agent_06_incident", "tool_calling", "hard", "create_incident",
        {
            "severity": {"type": "string", "enum": ["SEV-1", "sev-1"]},
            "title": {"type": "string", "contains": "checkout"},
            "services": {"type": "array", "min_items": 1, "items": {"type": "string"}},
        },
        "You are an incident-response agent. Respond only with JSON using tool and parameters keys.",
        "Open a SEV-1 incident titled Checkout outage for the checkout service after payment failures exceed 20 percent.",
    ),
    _prompt(
        "agent_07_file_search", "tool_calling", "medium", "search_files",
        {
            "path": {"type": "string", "contains": "src"},
            "pattern": {"type": "string", "contains": "TODO"},
            "max_results": {"type": "integer", "minimum": 10},
        },
        "You are a repository agent. Respond only with JSON using tool and parameters keys.",
        "Search the src directory for TODO comments and return up to 10 matches.",
    ),
]

# Representative fast subset: simple extraction, nested schema, and command routing.
AGENT_QUICK_IDS = ("agent_01_weather", "agent_03_nested_order", "agent_04_routing")
AGENT_QUICK = [prompt for prompt in AGENT_PROMPTS if prompt["id"] in AGENT_QUICK_IDS]
