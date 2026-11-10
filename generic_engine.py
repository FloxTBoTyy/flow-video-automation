"""Motor genérico de historias y prompts para arquetipos personalizados definidos por el usuario.
Permite a cualquier usuario crear sus propios personajes y universos en Google Flow
mediante un archivo JSON sin tocar una sola línea de código Python.
"""

import os
import re
import json
import logging
import urllib.request
import urllib.error
from typing import Dict, Any, Optional

logger = logging.getLogger("GenericArchetypeEngine")

class GenericPromptBuilder:
    """Constructor dinámico de prompts cinematográficos basado en el archivo JSON del arquetipo."""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.key = config.get("key", "custom")
        self.character_dna = config.get("character_dna", {})
        self.visual_style = config.get("visual_style", "High-end photorealistic live-action documentary style, 35mm optical lens f/1.8.")

    def sanitize_scene_text(self, text: str) -> str:
        clean = text or ""
        # Filtros de seguridad universales para Google Flow
        for bad in ["aguja", "needle", "espada", "sword", "cuchillo", "knife", "pistola", "gun"]:
            clean = re.sub(rf"\b{bad}\b", "herramienta de exploración", clean, flags=re.IGNORECASE)
        for danger in ["al vacío", "sobre el vacío", "abismo", "precipicio"]:
            clean = re.sub(rf"\b{danger}\b", "a través de la superficie", clean, flags=re.IGNORECASE)
        for minor in [r"\bniño\b", r"\bniña\b", r"\bbebé\b", r"\bmenor\b"]:
            clean = re.sub(rf"{minor}", "personaje", clean, flags=re.IGNORECASE)
        return clean

    def build_video_prompt(self, scene: Dict[str, Any], include_dialogue: bool = True) -> str:
        desc = self.sanitize_scene_text(scene.get("description", ""))
        cam = scene.get("camera", "Cinematic tracking shot, 35mm lens, dynamic framing")
        light = scene.get("lighting", "Atmospheric cinematic lighting, gentle rim light, soft bokeh")

        char_desc = self.character_dna.get("description", "A heroic explorer character.")
        
        dialogue_text = ""
        if include_dialogue and scene.get("dialogue"):
            dialogue_data = scene["dialogue"]
            if isinstance(dialogue_data, list):
                lines = []
                for item in dialogue_data:
                    line_txt = self.sanitize_scene_text(item.get("line", ""))
                    if line_txt:
                        lines.append(f'"{line_txt}"')
                if lines:
                    dialogue_text = f" Fast dynamic Spanish whispered dialogue: {' '.join(lines)}."

        full_prompt = (
            f"Cinematic live-action photography. {char_desc} {desc}. "
            f"Framing: {cam}. Lighting: {light}. {self.visual_style}. Sharp crisp focus.{dialogue_text}"
        )
        return full_prompt.strip()

    def build_scene_by_id(self, scene_id: str, scenes: Optional[list] = None) -> Optional[str]:
        if not scenes:
            return None
        for sc in scenes:
            if sc.get("id") == scene_id or str(scene_id).lower() in str(sc.get("id", "")).lower():
                return self.build_video_prompt(sc)
        return None

    @classmethod
    def create_class(cls, config: Dict[str, Any]):
        """Crea una clase adaptadora compatible con la interfaz estática esperada por el pipeline."""
        instance = cls(config)
        
        class DynamicPromptBuilderAdapter:
            @staticmethod
            def build_scene_by_id(scene_id: str, scenes: Optional[list] = None) -> Optional[str]:
                return instance.build_scene_by_id(scene_id, scenes=scenes)
            
            @staticmethod
            def build_video_prompt(scene: Dict[str, Any], include_dialogue: bool = True) -> str:
                return instance.build_video_prompt(scene, include_dialogue=include_dialogue)
                
        return DynamicPromptBuilderAdapter


class GenericStoryGenerator:
    """Generador dinámico de historias que adapta la plantilla del arquetipo JSON."""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.key = config.get("key", "custom")
        self.display_name = config.get("display_name", self.key)
        self.character_dna = config.get("character_dna", {})
        self.world_rules = config.get("world_rules", {})

    @staticmethod
    def get_opencode_key() -> Optional[str]:
        return os.getenv("OPENCODE_API_KEY")

    def build_prompt(self, location: Optional[str] = None, free_theme: Optional[str] = None) -> str:
        loc = f"📍 ENTORNO: {location}" if location else f"📍 ENTORNO: {self.world_rules.get('setting', 'Un escenario cinematográfico acorde al universo.')}"
        
        char_name = self.character_dna.get("name", "Protagonista")
        char_desc = self.character_dna.get("description", "Personaje principal")
        char_acting = self.character_dna.get("acting", "Valiente, ágil y carismático.")
        tone = self.world_rules.get("tone", "Misión a contrarreloj de alta adrenalina y suspenso.")

        theme_txt = f"\n🎯 TEMA SUGERIDO POR EL USUARIO: {free_theme}\n" if free_theme else ""

        return f"""Eres un Director Creativo cinematográfico de élite especializado en contenido hiperviral de TikTok.
Tu público objetivo es 100% HISPANOHABLANTE. Todos los diálogos, títulos y textos DEBEN SER ESTRICTAMENTE EN ESPAÑOL.

UNIVERSO Y PERSONAJE:
- Universo: {self.display_name}
- Protagonista: {char_name}. {char_desc}
- Cómo actúa: {char_acting}
- Tono y ritmo: {tone}
{loc}
{theme_txt}
ESTRUCTURA DE TIKTOK EN 3 TOMAS (30 SEGUNDOS TOTAL, CONTINUIDAD DIRECTA):
1. TOMA 1: HOOK TREPIDANTE (< 3s) - Alta energía visual, acción inmediata "in media res" y frase gancho en español (< 3s).
2. TOMA 2: MANIOBRA Y SUSPENSO (10-20s) - Superación de obstáculo con ingenio y trabajo en equipo.
3. TOMA 3: RESOLUCIÓN Y ESCAPE (20-30s) - Clímax triunfal y remate memorable.

REGLAS DE SEGURIDAD (ANTI-FILTROS):
- NUNCA uses términos violentos explícitos, armas reales, ni hagas mención a menores o camas.

Devuelve ÚNICAMENTE un bloque de código JSON con este formato exacto:
```json
{{
  "location": "Locación de la historia",
  "title": "Título llamativo en español",
  "tiktok_caption": "Texto para el copy de TikTok con gancho",
  "tiktok_hashtags": ["#Tag1", "#Tag2", "#Tag3"],
  "scenes": [
    {{
      "id": "toma_1",
      "title": "Toma 1: El Hook",
      "description": "Acción inicial dinámica en español",
      "dialogue": [
        {{"speaker": "{char_name}", "voice": "Spanish (urgent)", "line": "¡Rápido, tenemos poco tiempo!"}}
      ],
      "camera": "Dynamic push-in, low-angle tracking shot",
      "lighting": "Cinematic lighting, gentle rim light"
    }},
    {{
      "id": "toma_2",
      "title": "Toma 2: La Maniobra",
      "description": "Acción tensa de superación de obstáculo",
      "dialogue": [
        {{"speaker": "{char_name}", "voice": "Spanish (determined)", "line": "¡Ahora! ¡Tres, dos, uno... ya!"}}
      ],
      "camera": "Whip pan tracking shot, sharp focus",
      "lighting": "Atmospheric contrast lighting"
    }},
    {{
      "id": "toma_3",
      "title": "Toma 3: La Victoria",
      "description": "Resolución exitosa y escape triunfal",
      "dialogue": [
        {{"speaker": "{char_name}", "voice": "Spanish (triumphant)", "line": "¡Lo logramos! ¡Misión cumplida!"}}
      ],
      "camera": "Cinematic closing tracking shot",
      "lighting": "Warm triumphant lighting"
    }}
  ]
}}
```"""

    MODEL_ALIASES = {
        "haiku": "claude-haiku-5-5",
        "claude": "claude-haiku-5-5",
        "claude-haiku": "claude-haiku-5-5",
        "deepseek": "deepseek-v4-pro",
        "deepseek-pro": "deepseek-v4-pro",
        "kimi": "kimi-k2.7-code",
        "kimi-code": "kimi-k2.7-code",
        "kimi-pro": "kimi-k3.1-pro",
        "minimax": "minimax-m3.1-flash",
        "qwen": "qwen-3.7-plus",
        "gpt": "gpt-6-luna",
    }

    @classmethod
    def resolve_model_name(cls, m: Optional[str] = None) -> str:
        if m and m.strip():
            clean = m.strip().lower()
            return cls.MODEL_ALIASES.get(clean, m.strip())
        return os.getenv("OPENCODE_MODEL", "claude-haiku-5-5").strip()

    @staticmethod
    def get_api_key() -> Optional[str]:
        return os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")

    def generate_episode_with_gemini(self, location: Optional[str] = None, free_theme: Optional[str] = None) -> Dict[str, Any]:
        """Respaldo oficial con Google Gemini API si Opencode no está disponible."""
        gemini_key = self.get_api_key()
        if not gemini_key:
            raise RuntimeError("GEMINI_API_KEY no configurada.")
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=gemini_key)
        prompt = self.build_prompt(location=location, free_theme=free_theme)
        model_to_use = os.getenv("GEMINI_MODEL", "gemini-2.5-flash").strip()

        logger.info(f"✨ Generando guion para [{self.display_name}] usando Google Gemini API ({model_to_use})...")
        response = client.models.generate_content(
            model=model_to_use,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.8,
            )
        )
        raw_text = response.text.strip()
        cleaned = re.sub(r"^```json\s*", "", raw_text, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s*```$", "", cleaned)
        return json.loads(cleaned)

    def generate_episode(self, location: Optional[str] = None, model: Optional[str] = None, free_theme: Optional[str] = None) -> Dict[str, Any]:
        api_key = self.get_opencode_key()
        if not api_key:
            if self.get_api_key():
                logger.warning("OPENCODE_API_KEY no detectada. Usando Gemini API de respaldo...")
                return self.generate_episode_with_gemini(location=location, free_theme=free_theme)
            raise RuntimeError("Se requiere OPENCODE_API_KEY o GEMINI_API_KEY en .env para generar guiones.")

        resolved_model = self.resolve_model_name(model)
        prompt = self.build_prompt(location=location, free_theme=free_theme)

        logger.info(f"✨ Generando guion para [{self.display_name}] usando {resolved_model}...")

        base_url = os.getenv("OPENCODE_BASE_URL", "https://opencode.ai/zen/go/v1")
        url = f"{base_url.rstrip('/')}/chat/completions"

        payload = {
            "model": resolved_model,
            "messages": [
                {"role": "system", "content": "Eres un guionista cinematográfico de TikTok. Responde ÚNICAMENTE con JSON válido."},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.75,
            "max_tokens": 1800,
        }

        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
                "User-Agent": "FlowVideoAutomation/2.0",
            },
            method="POST",
        )

        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        raw_content = data["choices"][0]["message"]["content"]
        match = re.search(r"```json\s*(.*?)\s*```", raw_content, re.DOTALL)
        json_str = match.group(1) if match else raw_content.strip()

        parsed = json.loads(json_str)
        return parsed

    @classmethod
    def create_class(cls, config: Dict[str, Any]):
        """Crea una clase adaptadora compatible con la interfaz estática esperada por el pipeline."""
        instance = cls(config)

        class DynamicStoryGeneratorAdapter:
            @staticmethod
            def resolve_model_name(m: Optional[str] = None) -> str:
                return instance.resolve_model_name(m)

            @staticmethod
            def generate_episode(location: Optional[str] = None, model: Optional[str] = None, free_theme: Optional[str] = None) -> Dict[str, Any]:
                return instance.generate_episode(location=location, model=model, free_theme=free_theme)

            @staticmethod
            def generate_episode_with_gemini(location: Optional[str] = None, free_theme: Optional[str] = None) -> Dict[str, Any]:
                return instance.generate_episode_with_gemini(location=location, free_theme=free_theme)

            @staticmethod
            def get_api_key() -> Optional[str]:
                return instance.get_api_key()

        return DynamicStoryGeneratorAdapter
