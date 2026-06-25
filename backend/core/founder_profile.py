"""Perfil do fundador.

Usado pelo agente de Founder Compatibility (e outros) para filtrar
oportunidades inviaveis antes de gastar analise. `get_profile_as_text()`
formata o perfil para ser injetado nos prompts dos agentes.
"""

FOUNDER_PROFILE: dict = {
    "name": "Henrique",
    "location": "Dublin, Ireland",
    "languages": ["Portuguese", "English", "Italian", "Spanish", "Arabic"],
    "skills": {
        "technical": [
            "Python", "FastAPI", "Next.js", "REST APIs",
            "Automation", "AI/LLMs", "Claude Code", "NFC",
            "3D Printing", "WordPress",
        ],
        "business": [
            "Marketing", "B2B Sales", "SaaS", "E-commerce",
            "Product Management", "Community Building",
        ],
    },
    "markets": ["Ireland", "Europe", "Brazil", "Portuguese-speaking markets"],
    "active_projects": ["SmartTap", "TALOA", "InMyHouses"],
    "budget_range": "bootstrap",
    "tools_available": [
        "Claude Code", "OpenAI", "Vercel", "Railway",
        "Supabase", "Stripe", "Canva", "GitHub",
    ],
    "target_business_type": ["SaaS", "Marketplace", "B2B", "Automation"],
    "avoid": ["physical_retail", "requires_large_team", "high_regulatory_overhead"],
}


def get_profile_as_text() -> str:
    """Retorna o perfil formatado em texto para inserir em prompts de LLM."""
    p = FOUNDER_PROFILE
    return f"""FOUNDER PROFILE
Name: {p["name"]}
Location: {p["location"]}
Languages: {", ".join(p["languages"])}

Technical skills: {", ".join(p["skills"]["technical"])}
Business skills: {", ".join(p["skills"]["business"])}

Target markets: {", ".join(p["markets"])}
Active projects: {", ".join(p["active_projects"])}
Budget: {p["budget_range"]}
Tools available: {", ".join(p["tools_available"])}
Preferred business types: {", ".join(p["target_business_type"])}
Avoid: {", ".join(p["avoid"])}"""
