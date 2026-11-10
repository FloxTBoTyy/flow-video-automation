"""Registro central y dinámico de arquetipos para Google Flow."""

import os
import sys
import json
from pathlib import Path
from typing import Dict, Any, Optional

BASE_DIR = Path(__file__).resolve().parent
PRIVATE_DIR = BASE_DIR / "private_archetypes"
ARCHETYPES_DIR = BASE_DIR / "archetypes"

# Añadir carpeta privada al path si existe en la máquina local del usuario
if PRIVATE_DIR.exists() and str(PRIVATE_DIR) not in sys.path:
    sys.path.insert(0, str(PRIVATE_DIR))


class ArchetypeRegistry:
    """Gestiona los arquetipos públicos y privados para Google Flow y TikTok."""

    @classmethod
    def get_available_archetypes(cls) -> Dict[str, str]:
        """Devuelve un diccionario de todos los arquetipos disponibles."""
        available = {}

        # 1. Arquetipos públicos en archetypes/
        if ARCHETYPES_DIR.exists():
            for p in ARCHETYPES_DIR.glob("*.json"):
                if p.stem != "template":
                    try:
                        with open(p, "r", encoding="utf-8") as f:
                            d = json.load(f)
                            available[p.stem] = d.get("display_name", p.stem.capitalize())
                    except Exception:
                        available[p.stem] = p.stem.capitalize()

        # 2. Arquetipos privados locales (si existen en private_archetypes/ de la máquina del usuario)
        if PRIVATE_DIR.exists():
            try:
                import private_registry
                if hasattr(private_registry, "get_private_available_archetypes"):
                    available.update(private_registry.get_private_available_archetypes())
            except Exception:
                pass

        return available

    @classmethod
    def get_archetype_config(cls, name: Optional[str]) -> Dict[str, Any]:
        """Obtiene la configuración del arquetipo indicado. Soporta arquetipos públicos y privados."""
        if not name or not str(name).strip():
            name = "explorer"

        clean = str(name).strip().lower()

        # 1. Arquetipos privados locales (módulo privado local)
        if PRIVATE_DIR.exists():
            try:
                import private_registry
                if hasattr(private_registry, "get_private_archetype_config"):
                    priv_cfg = private_registry.get_private_archetype_config(clean)
                    if priv_cfg:
                        return priv_cfg
            except Exception as e:
                logger_msg = f"Aviso al cargar módulo privado para '{clean}': {e}"
                # Continuar hacia los arquetipos públicos JSON

        # 2. Arquetipos públicos y personalizados (archetypes/*.json)
        from generic_engine import GenericPromptBuilder, GenericStoryGenerator

        possible_paths = [
            ARCHETYPES_DIR / f"{clean}.json",
            PRIVATE_DIR / f"{clean}.json",
            BASE_DIR / f"{clean}.json",
        ]
        for p in possible_paths:
            if p.exists():
                try:
                    with open(p, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    return {
                        "key": data.get("key", clean),
                        "display_name": data.get("display_name", clean.capitalize()),
                        "flow_project_url": data.get("flow_project_url", ""),
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
            "💡 Para crear tu propio personaje:\n"
            "   1. Copia 'archetypes/template.json' como 'archetypes/<nombre>.json'\n"
            "   2. Edita su nombre, ropa, cómo actúa y locación\n"
            "   3. Ejecuta: python generate_and_assemble_episode.py -a <nombre>"
        )
