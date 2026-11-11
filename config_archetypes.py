"""Registro central y dinámico de arquetipos para Google Flow."""

import os
import sys
import json
from pathlib import Path
from typing import Dict, Any, Optional

BASE_DIR = Path(__file__).resolve().parent
ARCHETYPES_DIR = BASE_DIR / "archetypes"


class ArchetypeRegistry:
    """Gestiona los arquetipos para Google Flow y TikTok basados en archivos JSON."""

    @classmethod
    def get_available_archetypes(cls) -> Dict[str, str]:
        """Devuelve un diccionario de todos los arquetipos disponibles."""
        available = {}

        if ARCHETYPES_DIR.exists():
            for p in sorted(ARCHETYPES_DIR.glob("*.json")):
                if p.stem != "template":
                    clean_name = p.stem.replace(".private", "")
                    try:
                        with open(p, "r", encoding="utf-8") as f:
                            d = json.load(f)
                            available[clean_name] = d.get("display_name", clean_name.capitalize())
                    except Exception:
                        available[clean_name] = clean_name.capitalize()

        return available

    @classmethod
    def get_archetype_config(cls, name: Optional[str]) -> Dict[str, Any]:
        """Obtiene la configuración del arquetipo indicado desde archetypes/<name>.json."""
        if not name or not str(name).strip():
            name = "explorer"

        clean = str(name).strip().lower()

        from generic_engine import GenericPromptBuilder, GenericStoryGenerator

        possible_paths = [
            ARCHETYPES_DIR / f"{clean}.json",
            ARCHETYPES_DIR / f"{clean}.private.json",
            BASE_DIR / f"{clean}.json",
        ]
        for p in possible_paths:
            if p.exists():
                try:
                    with open(p, "r", encoding="utf-8") as f:
                        data = json.load(f)

                    env_url = (
                        os.getenv(f"FLOW_{clean.upper()}_PROJECT_URL")
                        or os.getenv("FLOW_PROJECT_URL", "https://flow.google.com")
                    )
                    flow_url = (data.get("flow_project_url") or env_url).strip()

                    return {
                        "key": data.get("key", clean),
                        "display_name": data.get("display_name", clean.capitalize()),
                        "flow_project_url": flow_url,
                        "character_name": data.get("character_name", f"{clean} 1"),
                        "story_generator": GenericStoryGenerator.create_class(data),
                        "prompt_builder": GenericPromptBuilder.create_class(data),
                        "video_prefix": data.get("video_prefix", clean),
                        "tiktok_default_caption": data.get("tiktok_default_caption", f"¡Aventura de {clean}! ✨"),
                        "tiktok_default_hashtags": data.get("tiktok_default_hashtags", ["#Aventura", "#Viral", "#Cine"]),
                    }
                except Exception as e:
                    raise ValueError(f"❌ Error al cargar arquetipo desde {p}: {e}")

        # Listado de ayuda si no se encuentra
        available = cls.get_available_archetypes()
        opts = "\n".join([f"  • -a {k:12} ({v})" for k, v in available.items()])
        raise ValueError(
            f"❌ ERROR: Arquetipo desconocido '{name}'.\n\n"
            f"Arquetipos disponibles en este entorno:\n{opts}\n\n"
            f"💡 Para crear tu propio personaje:\n"
            f"   1. Copia 'archetypes/template.json' como 'archetypes/{clean}.json'\n"
            f"   2. Edita su nombre, ropa, cómo actúa y locación\n"
            f"   3. Ejecuta: python generate_and_assemble_episode.py -a {clean}"
        )
