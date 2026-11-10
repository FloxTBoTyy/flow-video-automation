"""Motor genérico de historias y prompts para arquetipos personalizados definidos por el usuario.
Permite a cualquier usuario crear sus propios personajes y universos en Google Flow
mediante un archivo JSON sin tocar una sola línea de código Python.

Soporta múltiples proveedores de IA:
- Google Gemini (Oficial vía SDK o REST)
- Opencode Go (Kimi, DeepSeek, Haiku, Qwen, MiniMax)
- OpenAI Oficial (gpt-4o, gpt-4o-mini, o3-mini)
- Anthropic Claude Oficial (claude-3-5-sonnet, claude-3-5-haiku)
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
        self.visual_style = config.get(
            "visual_style",
            "High-end photorealistic live-action documentary style, 35mm optical lens f/1.8."
        )

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
    """Generador dinámico universal de historias compatible con múltiples proveedores de IA."""

    MODEL_ALIASES = {
        # Google Gemini (Baseline y Frontier)
        "gemini": "gemini-2.5-flash",
        "gemini-flash": "gemini-2.5-flash",
        "gemini-pro": "gemini-1.5-pro",
        "gemini-2.5": "gemini-2.5-flash",
        "gemini-2.0": "gemini-2.0-flash",
        "gemini-1.5": "gemini-1.5-flash",
        "argon": "gemini-argon",
        "gemini-argon": "gemini-argon",

        # OpenAI (Baseline y Frontier: Astra, Sol, Luna)
        "gpt-4o": "gpt-4o",
        "gpt-4o-mini": "gpt-4o-mini",
        "4o-mini": "gpt-4o-mini",
        "4o": "gpt-4o",
        "o3-mini": "o3-mini",
        "o1-mini": "o1-mini",
        "astra": "gpt-5-astra",
        "sol": "gpt-5-sol",
        "luna": "gpt-6-luna",
        "gpt-5": "gpt-5-sol",
        "gpt-6": "gpt-6-luna",

        # Anthropic Claude (Baseline y Frontier: Fable)
        "haiku": "claude-3-5-haiku-20241022",
        "claude": "claude-3-5-haiku-20241022",
        "claude-haiku": "claude-3-5-haiku-20241022",
        "sonnet": "claude-3-5-sonnet-20241022",
        "claude-sonnet": "claude-3-5-sonnet-20241022",
        "claude-3.5-sonnet": "claude-3-5-sonnet-20241022",
        "claude-3.5-haiku": "claude-3-5-haiku-20241022",
        "fable": "claude-fable",
        "claude-fable": "claude-fable",
        "claude-haiku-5-5": "claude-haiku-5-5",

        # DeepSeek
        "deepseek": "deepseek-chat",
        "deepseek-chat": "deepseek-chat",
        "deepseek-v3": "deepseek-chat",
        "deepseek-r1": "deepseek-reasoner",
        "r1": "deepseek-reasoner",
        "deepseek-v4-pro": "deepseek-v4-pro",

        # Moonshot Kimi (v1 y K2/K3 series)
        "kimi": "moonshot-v1-8k",
        "moonshot": "moonshot-v1-8k",
        "kimi-32k": "moonshot-v1-32k",
        "kimi-k3": "kimi-k3.1-pro",
        "kimi-k3.1": "kimi-k3.1-pro",
        "kimi-k2.7": "kimi-k2.7-code",
        "kimi-k2.7-code": "kimi-k2.7-code",

        # Alibaba Qwen (v2.5, v3.7, v4)
        "qwen": "qwen-2.5-72b-instruct",
        "qwen-2.5": "qwen-2.5-72b-instruct",
        "qwen-3.7": "qwen-3.7-plus",
        "qwen-4": "qwen-4-plus",
        "qwen4": "qwen-4-plus",
    }

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.key = config.get("key", "custom")
        self.display_name = config.get("display_name", self.key)
        self.character_dna = config.get("character_dna", {})
        self.world_rules = config.get("world_rules", {})

    @classmethod
    def resolve_model_name(cls, m: Optional[str] = None, provider: str = "opencode") -> str:
        """Resuelve el nombre exacto del modelo según el alias y el proveedor."""
        if m and m.strip():
            clean = m.strip().lower()
            return cls.MODEL_ALIASES.get(clean, m.strip())

        # Si no se pasó modelo, tomar el predeterminado del proveedor
        if provider == "gemini":
            return os.getenv("GEMINI_MODEL", "gemini-2.5-flash").strip()
        elif provider == "openai":
            return os.getenv("OPENAI_MODEL", "gpt-4o-mini").strip()
        elif provider == "anthropic":
            return os.getenv("ANTHROPIC_MODEL", "claude-3-5-haiku-20241022").strip()
        else:
            return os.getenv("OPENCODE_MODEL", "deepseek-chat").strip()

    @classmethod
    def resolve_provider(cls, provider_arg: Optional[str] = None, model_arg: Optional[str] = None) -> str:
        """Determina de forma inteligente qué proveedor usar (CLI > Modelo > .env > Auto-detección de Keys)."""
        # 1. Argumento explícito en CLI (-p / --provider)
        if provider_arg and provider_arg.strip():
            p = provider_arg.strip().lower()
            if p in ["gemini", "google"]:
                return "gemini"
            if p in ["openai", "gpt"]:
                return "openai"
            if p in ["anthropic", "claude"]:
                return "anthropic"
            if p in ["opencode", "zen"]:
                return "opencode"
            return p

        # 2. Detección por el nombre del modelo (-m)
        if model_arg and model_arg.strip():
            m = model_arg.strip().lower()
            if any(k in m for k in ["gemini", "argon"]):
                return "gemini"
            if any(k in m for k in ["gpt-", "o1", "o3", "4o", "astra", "sol", "luna"]):
                return "openai"
            if any(k in m for k in ["claude", "sonnet", "haiku", "fable"]):
                return "anthropic"
            if any(k in m for k in ["kimi", "deepseek", "moonshot", "qwen", "minimax"]):
                return "opencode"

        # 3. Variable de entorno AI_PROVIDER
        env_prov = os.getenv("AI_PROVIDER", "").strip().lower()
        if env_prov in ["gemini", "openai", "anthropic", "opencode"]:
            return env_prov

        # 4. Auto-detección por claves presentes en .env
        if os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY"):
            # Si solo está configurado Gemini, usar Gemini por defecto
            if not os.getenv("OPENCODE_API_KEY"):
                return "gemini"
        if os.getenv("OPENAI_API_KEY") and not os.getenv("OPENCODE_API_KEY") and not os.getenv("GEMINI_API_KEY"):
            return "openai"
        if os.getenv("ANTHROPIC_API_KEY") and not os.getenv("OPENCODE_API_KEY"):
            return "anthropic"
        if os.getenv("OPENCODE_API_KEY"):
            return "opencode"

        return "gemini" if (os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")) else "opencode"

    def build_prompt(self, location: Optional[str] = None, free_theme: Optional[str] = None) -> str:
        loc = f"📍 ENTORNO: {location}" if location else f"📍 ENTORNO: {self.world_rules.get('setting', 'Un escenario cinematográfico acorde al universo.')}"

        char_name = self.character_dna.get("name", "Protagonista")
        char_desc = self.character_dna.get("description", "Personaje principal")
        char_acting = self.character_dna.get("acting", "Valiente, ágil y carismático.")
        tone = self.world_rules.get("tone", "Misión a contrarreloj de alta adrenalina y suspenso.")

        theme_txt = f"\n🎯 TEMA SUGERIDO POR EL USUARIO: {free_theme}\n" if free_theme else ""

        return f"""Eres un Director Creativo cinematográfico de élite especializado en contenido hiperviral de TikTok.
Tu misión es diseñar un guion cautivador y tenso de 30 segundos (3 tomas de 10s cada una) para el protagonista de este universo.

{loc}
{theme_txt}

FICHA DEL PROTAGONISTA:
- Nombre: {char_name}
- Descripción física y vestuario: {char_desc}
- Biomecánica y actitud: {char_acting}
- Tono del universo: {tone}

ESTRUCTURA OBLIGATORIA (3 TOMAS NARRATIVAS DE 10s):
- Toma 1: Planteamiento y gancho inicial (primeros 3 segundos vitales de retención).
- Toma 2: Punto de giro, obstáculo o momento de máximo riesgo a contrarreloj.
- Toma 3: Clímax, resolución exitosa o escape triunfal.

REGLAS ESTRICTAS DE CONTENIDO:
1. Todas las descripciones visuales deben ser hiperrealistas y cinematográficas.
2. Los diálogos deben ser en ESPAÑOL, directos, naturales, con urgencia y compinchería.
3. Responde ÚNICAMENTE con un objeto JSON válido con la siguiente estructura exacta (sin texto previo ni posterior):

```json
{{
  "title": "Título corto y épico del episodio",
  "location": "Nombre específico del lugar",
  "scenes": [
    {{
      "id": "toma_1",
      "title": "Toma 1: El Desafío",
      "description": "Acción cinematográfica visual y clara del protagonista",
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

    def _parse_json_response(self, raw_content: str) -> Dict[str, Any]:
        """Limpia bloques de código markdown y convierte a dict."""
        match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", raw_content)
        json_str = match.group(1).strip() if match else raw_content.strip()
        return json.loads(json_str)

    # ========================================================
    # 1. LLAMADA A GOOGLE GEMINI OFICIAL (SDK google-genai)
    # ========================================================
    def _call_gemini(self, prompt: str, model_name: str) -> Dict[str, Any]:
        gemini_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        if not gemini_key:
            raise RuntimeError("GEMINI_API_KEY no configurada en .env.")
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=gemini_key)
        logger.info(f"✨ Generando guion con Google Gemini Oficial ({model_name})...")
        response = client.models.generate_content(
            model=model_name,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.8,
            )
        )
        return self._parse_json_response(response.text)

    # ========================================================
    # 2. LLAMADA A OPENCODE GO (Endpoint OpenAI-compatible)
    # ========================================================
    def _call_opencode(self, prompt: str, model_name: str) -> Dict[str, Any]:
        api_key = os.getenv("OPENCODE_API_KEY")
        if not api_key:
            raise RuntimeError("OPENCODE_API_KEY no configurada en .env.")

        base_url = os.getenv("OPENCODE_BASE_URL", "https://opencode.ai/zen/go/v1")
        url = f"{base_url.rstrip('/')}/chat/completions"

        logger.info(f"✨ Generando guion con Opencode Go ({model_name})...")
        payload = {
            "model": model_name,
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
        return self._parse_json_response(data["choices"][0]["message"]["content"])

    # ========================================================
    # 3. LLAMADA A OPENAI OFICIAL (Endpoint OpenAI v1)
    # ========================================================
    def _call_openai(self, prompt: str, model_name: str) -> Dict[str, Any]:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY no configurada en .env.")

        url = "https://api.openai.com/v1/chat/completions"
        logger.info(f"✨ Generando guion con OpenAI Oficial ({model_name})...")
        payload = {
            "model": model_name,
            "messages": [
                {"role": "system", "content": "Eres un guionista cinematográfico de TikTok. Responde ÚNICAMENTE con JSON válido."},
                {"role": "user", "content": prompt}
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.75,
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
        return self._parse_json_response(data["choices"][0]["message"]["content"])

    # ========================================================
    # 4. LLAMADA A ANTHROPIC CLAUDE OFICIAL (Endpoint Messages v1)
    # ========================================================
    def _call_anthropic(self, prompt: str, model_name: str) -> Dict[str, Any]:
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise RuntimeError("ANTHROPIC_API_KEY no configurada en .env.")

        url = "https://api.anthropic.com/v1/messages"
        logger.info(f"✨ Generando guion con Anthropic Claude Oficial ({model_name})...")
        payload = {
            "model": model_name,
            "max_tokens": 1800,
            "system": "Eres un guionista cinematográfico de TikTok. Responde ÚNICAMENTE con JSON válido sin bloques markdown ni texto adicional.",
            "messages": [
                {"role": "user", "content": prompt}
            ],
        }
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "User-Agent": "FlowVideoAutomation/2.0",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        return self._parse_json_response(data["content"][0]["text"])

    # ========================================================
    # DISPATCHER PRINCIPAL CON FALLBACK INTELIGENTE
    # ========================================================
    def generate_episode(
        self,
        location: Optional[str] = None,
        model: Optional[str] = None,
        free_theme: Optional[str] = None,
        provider: Optional[str] = None
    ) -> Dict[str, Any]:
        """Genera el episodio despachando la petición al proveedor elegido."""
        active_provider = self.resolve_provider(provider_arg=provider, model_arg=model)
        resolved_model = self.resolve_model_name(model, provider=active_provider)
        prompt = self.build_prompt(location=location, free_theme=free_theme)

        logger.info(f"🎯 Proveedor activo: {active_provider.upper()} | Modelo: {resolved_model}")

        try:
            if active_provider == "gemini":
                return self._call_gemini(prompt, resolved_model)
            elif active_provider == "openai":
                return self._call_openai(prompt, resolved_model)
            elif active_provider == "anthropic":
                return self._call_anthropic(prompt, resolved_model)
            else:
                return self._call_opencode(prompt, resolved_model)
        except Exception as e:
            # Fallback automático a Gemini si Opencode/OpenAI/Anthropic fallan y Gemini está disponible
            gemini_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
            if active_provider != "gemini" and gemini_key:
                logger.warning(f"Aviso del proveedor {active_provider.upper()} ({e}). Reintentando automáticamente con Google Gemini API...")
                gemini_model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash").strip()
                return self._call_gemini(prompt, gemini_model)
            raise e

    @classmethod
    def create_class(cls, config: Dict[str, Any]):
        """Crea una clase adaptadora compatible con la interfaz estática esperada por el pipeline."""
        instance = cls(config)

        class DynamicStoryGeneratorAdapter:
            @staticmethod
            def resolve_model_name(m: Optional[str] = None, provider: str = "opencode") -> str:
                return instance.resolve_model_name(m, provider=provider)

            @staticmethod
            def resolve_provider(provider_arg: Optional[str] = None, model_arg: Optional[str] = None) -> str:
                return instance.resolve_provider(provider_arg=provider_arg, model_arg=model_arg)

            @staticmethod
            def generate_episode(
                location: Optional[str] = None,
                model: Optional[str] = None,
                free_theme: Optional[str] = None,
                provider: Optional[str] = None
            ) -> Dict[str, Any]:
                return instance.generate_episode(
                    location=location,
                    model=model,
                    free_theme=free_theme,
                    provider=provider
                )

        return DynamicStoryGeneratorAdapter
