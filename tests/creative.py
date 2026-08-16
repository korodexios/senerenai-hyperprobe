"""
Creative Writing Test Prompts
==============================
Tests: imagination, vocabulary diversity, atmosphere, coherence,
lack of AI fluff, minimum length.
"""
CREATIVE_PROMPTS = [
    {
        "id": "crea_01",
        "category": "surreal",
        "difficulty": "medium",
        "system": "You are a creative writer with a vivid, surreal style.",
        "prompt": "Describe a city made of living glass and crystallized sound. Write a short surreal story (about 200 words) focusing on atmosphere and sensory details.",
    },
    {
        "id": "crea_02",
        "category": "poetry",
        "difficulty": "medium",
        "system": "You are a dark, melancholic poet.",
        "prompt": "Write a dark, melancholic poem about a dying star. Use rich, varied, and uncommon vocabulary. 4 stanzas, 4 lines each.",
    },
    {
        "id": "crea_03",
        "category": "worldbuilding",
        "difficulty": "hard",
        "system": "You are a sci-fi world-builder with encyclopedic imagination.",
        "prompt": "Explain the history of the 'Neon Wars', a conflict fought entirely in cyberspace 200 years ago. Be detailed, imaginative, and at least 300 words. Include factions, turning points, and aftermath.",
    },
    {
        "id": "crea_04",
        "category": "sensory",
        "difficulty": "medium",
        "system": "You are a surrealist writer who focuses on sensory experience.",
        "prompt": "Describe a vivid dream where gravity changes direction every minute. Focus on the physical sensation and emotional disorientation. Minimum 200 words.",
    },
    {
        "id": "crea_05",
        "category": "essay",
        "difficulty": "hard",
        "system": "You are an essayist who can transition smoothly between unrelated topics.",
        "prompt": "Write a short essay (250+ words) transitioning smoothly from the concept of time, to the evolution of music, to deep space exploration. Each transition should feel natural and surprising.",
    },
    {
        "id": "crea_06",
        "category": "description",
        "difficulty": "medium",
        "system": "You are a descriptive writer. Avoid repetition.",
        "prompt": "Describe an ancient, overgrown library in extreme detail. Do not repeat words like 'dust', 'books', or 'old' too often. Minimum 200 words. Use a wide range of vocabulary for 'forgotten', 'decay', and 'knowledge'.",
    },
    {
        "id": "crea_07",
        "category": "speech",
        "difficulty": "medium",
        "system": "You are an eloquent, inspiring orator.",
        "prompt": "Deliver a motivational speech to tired soldiers before a final battle. Use a wide variety of vocabulary to express 'bravery', 'victory', and 'hope'. Minimum 150 words.",
    },
    {
        "id": "crea_08",
        "category": "constrained",
        "difficulty": "hard",
        "system": "You are a master creative writer. Strictly follow constraints.",
        "prompt": "Write a short surreal story (150+ words) about a lighthouse at the edge of the universe. CONSTRAINT: Every single sentence must start with a different letter of the alphabet in chronological order (A, B, C, D...). Do not use cliche AI story intros.",
    },
    {
        "id": "crea_09",
        "category": "reverse_narrative",
        "difficulty": "hard",
        "system": "You are an unconventional storyteller.",
        "prompt": "Write a 200-word sci-fi thriller scene told strictly in reverse chronological order (starting from the tragic end, moving backwards to the peaceful beginning). Focus on vivid sensory disorientation.",
    },
]
# Quick subset for fast phases
CREATIVE_QUICK_IDS = ("crea_01", "crea_03", "crea_05")
CREATIVE_QUICK = [p for p in CREATIVE_PROMPTS if p["id"] in CREATIVE_QUICK_IDS]