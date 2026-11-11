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
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional, List
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger("GenericArchetypeEngine")


class GenericPromptBuilder:
    """Constructor dinámico de prompts cinematográficos basado en el archivo JSON del arquetipo."""

    SWEET_VOCABULARY_MAP = [
        (r"\bcarajos\b", "carachos"),
        (r"\bcarajo\b", "caracho"),
        (r"\bmierda\b", "córcholis"),
        (r"\bcoño\b", "caracoles"),
        (r"\bputa\b", "pucha"),
        (r"\bjoder\b", "jolines"),
    ]

    FOURTH_WALL_BREAK_PATTERNS = [
        (r"(?i)[¡!]?\s*(?:dejad?|deja|den|da|dejadnos|danos)\s+(?:un\s+)?like\b[^\.!\?]*[\.!\?]?", ""),
        (r"(?i)[¡!]?\s*dale\s+like\b[^\.!\?]*[\.!\?]?", ""),
        (r"(?i)[¡!]?\s*(?:comparte|compártelo|compartan|compartid|comparte\s+el\s+video)\b[^\.!\?]*[\.!\?]?", ""),
        (r"(?i)[¡!]?\s*(?:suscríbete|suscribiros|suscríbanse|sígueme|síguenos)\b[^\.!\?]*[\.!\?]?", ""),
        (r"(?i)[¡!]?\s*(?:etiqueta\s+a\s+(?:un|tu)\s+amigo|déjalo\s+en\s+los\s+comentarios)\b[^\.!\?]*[\.!\?]?", ""),
    ]

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.key = config.get("key", "custom")
        self.character_dna = config.get("character_dna", {})
        self.companions = config.get("companions", [])
        self.ensemble_dynamics = config.get("ensemble_dynamics", "")
        self.visual_style = config.get(
            "visual_style",
            "High-end photorealistic live-action documentary style, 35mm optical lens f/1.8."
        )
        self.negative_constraints = config.get("negative_constraints", "")

    def sanitize_scene_text(self, text: str) -> str:
        clean = text or ""
        # Filtros de seguridad universales para Google Flow
        for bad in ["aguja", "needle", "espada", "sword", "cuchillo", "knife", "pistola", "gun"]:
            clean = re.sub(rf"\b{bad}\b", "herramienta de exploración", clean, flags=re.IGNORECASE)
        for danger in ["al vacío", "sobre el vacío", "abismo", "precipicio"]:
            clean = re.sub(rf"\b{danger}\b", "a través de la superficie", clean, flags=re.IGNORECASE)
        for minor in [r"\bniño\b", r"\bniña\b", r"\bbebé\b", r"\bmenor\b"]:
            clean = re.sub(rf"{minor}", "personaje", clean, flags=re.IGNORECASE)
        # Sanitizar lenguaje malsonante y eliminar rupturas de cuarta pared
        for pattern, replacement in self.SWEET_VOCABULARY_MAP:
            clean = re.sub(pattern, replacement, clean, flags=re.IGNORECASE)
        for pattern, replacement in self.FOURTH_WALL_BREAK_PATTERNS:
            clean = re.sub(pattern, replacement, clean)
        return clean.strip()

    def build_video_prompt(self, scene: Dict[str, Any], include_dialogue: bool = True) -> str:
        desc = self.sanitize_scene_text(scene.get("description", ""))
        cam = scene.get("camera", "Cinematic tracking shot, 35mm lens, dynamic framing")
        light = scene.get("lighting", "Atmospheric cinematic lighting, gentle rim light, soft bokeh")

        # 1. Base del protagonista
        char_desc = self.character_dna.get("description", "A heroic protagonist character.")
        if self.character_dna.get("anatomy"):
            char_desc += f" Anatomy: {self.character_dna['anatomy']}"
        if self.character_dna.get("locomotion"):
            char_desc += f" Locomotion: {self.character_dna['locomotion']}"
        if self.character_dna.get("clothing"):
            char_desc += f" Traditional Costume: {self.character_dna['clothing']}"

        # 2. Base de acompañantes / escuadrón (si están presentes)
        companions_data = scene.get("companions") or self.companions
        companions_text = ""
        if companions_data and isinstance(companions_data, list):
            comp_blocks = []
            for idx, comp in enumerate(companions_data, start=2):
                c_name = comp.get("name", f"Companion {idx-1}")
                c_role = comp.get("role", "Companion")
                c_visual = comp.get("visual_desc", comp.get("personality", "Companion character"))
                comp_blocks.append(f"Character {idx} ({c_role}): {c_name}. {c_visual}")
            if comp_blocks:
                companions_text = " " + " ".join(comp_blocks)
            if self.ensemble_dynamics:
                companions_text += f" Ensemble Dynamics: {self.ensemble_dynamics}"

        # 3. Diálogos formateados
        dialogue_text = ""
        if include_dialogue and scene.get("dialogue"):
            dialogue_data = scene["dialogue"]
            if isinstance(dialogue_data, list):
                lines = []
                for item in dialogue_data:
                    spk = item.get("speaker", "")
                    line_txt = self.sanitize_scene_text(item.get("line", ""))
                    if line_txt:
                        lines.append(f'{spk}: "{line_txt}"' if spk else f'"{line_txt}"')
                if lines:
                    dialogue_text = f" Fast dynamic Spanish dialogue: {' '.join(lines)}."

        neg = f" Negative constraints: {self.negative_constraints}." if self.negative_constraints else ""

        full_prompt = (
            f"Cinematic live-action photography. {char_desc}{companions_text} Action: {desc}. "
            f"Framing: {cam}. Lighting: {light}. {self.visual_style}. Sharp crisp focus.{neg}{dialogue_text}"
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
        "kimi": "kimi-k2.7-code",
        "moonshot": "kimi-k2.7-code",
        "kimi-32k": "kimi-k2.7-code",
        "kimi-code": "kimi-k2.7-code",
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
        self.companions = config.get("companions", [])
        self.ensemble_dynamics = config.get("ensemble_dynamics", "")
        self.world_rules = config.get("world_rules", {})
        self.speech_guidelines = config.get("speech_guidelines", "")

    def _get_history_file(self) -> Path:
        base_dir = Path(__file__).resolve().parent
        return base_dir / f"history_{self.key}.json"

    def get_recent_locations(self, limit: int = 5) -> List[str]:
        hist_file = self._get_history_file()
        if not hist_file.exists():
            return []
        try:
            with open(hist_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            return [e.get("location") or e.get("city") for e in data[-limit:] if e.get("location") or e.get("city")]
        except Exception:
            return []

    def record_episode(self, location: str, title: str):
        hist_file = self._get_history_file()
        history = []
        if hist_file.exists():
            try:
                with open(hist_file, "r", encoding="utf-8") as f:
                    history = json.load(f)
            except Exception:
                history = []
        history.append({
            "location": location.strip(),
            "title": title.strip(),
            "created_at": datetime.now().isoformat()
        })
        if len(history) > 30:
            history = history[-30:]
        try:
            with open(hist_file, "w", encoding="utf-8") as f:
                json.dump(history, f, indent=2, ensure_ascii=False)
            logger.info(f"📝 Episodio registrado en historial ({self.key}): '{location}' - '{title}'")
        except Exception as e:
            logger.warning(f"No se pudo guardar historial ({self.key}): {e}")

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
        if location and str(location).strip().lower() not in ["random", "azar", "none", ""]:
            loc_directive = f"📍 ENTORNO DE LA AVENTURA: Ocurre en {str(location).strip()}."
        else:
            recent_locs = self.get_recent_locations(limit=5)
            avoid_clause = f"\n- Lugares visitados recientemente (EVITAR para no repetir): {', '.join(recent_locs)}" if recent_locs else ""
            setting_desc = self.world_rules.get("setting", "Un escenario cinematográfico acorde al universo.")
            loc_directive = f"📍 ENTORNO DE LA AVENTURA: Escoge libremente cualquier locación fascinante ({setting_desc}).{avoid_clause}"

        char_name = self.character_dna.get("name", "Protagonista")
        char_desc = self.character_dna.get("description", "Personaje principal")
        char_acting = self.character_dna.get("acting", "Valiente, ágil y carismático.")
        char_clothing = self.character_dna.get("clothing", "")
        char_locomotion = self.character_dna.get("locomotion", "")
        tone = self.world_rules.get("tone", "Misión a contrarreloj de alta adrenalina y suspenso.")

        theme_txt = f"\n🎯 TEMA SUGERIDO POR EL USUARIO (-ft): {free_theme}\n" if free_theme else ""

        companions_directive = ""
        if self.companions:
            comp_list = []
            for idx, c in enumerate(self.companions, start=1):
                c_name = c.get("name", f"Acompañante {idx}")
                c_role = c.get("role", "Compañero")
                c_desc = c.get("visual_desc", c.get("personality", ""))
                comp_list.append(f"  {idx}. {c_name} ({c_role}): {c_desc}")
            companions_directive = "\nELENCO DE ACOMPAÑANTES:\n" + "\n".join(comp_list)
            if self.ensemble_dynamics:
                companions_directive += f"\nDINÁMICA DE GRUPO Y COMPINCHERÍA: {self.ensemble_dynamics}\n- El protagonista lleva la voz y acción principal; los acompañantes intervienen con frases breves, oportunas y con chispa según su personalidad sin opacarlo."

        speech_directive = f"\nDIRECTRICES DE HABLA Y VOCABULARIO:\n{self.speech_guidelines}\n" if self.speech_guidelines else ""

        return f"""Eres un Director Creativo cinematográfico de élite especializado en narrativas virales para TikTok (hooks de alta retención, micro-storytelling y ritmo visual).
Diseña un guion cautivador de 30 segundos (exactamente 3 tomas de 10s con estricta continuidad lógica y temporal) para este universo.

{loc_directive}
{theme_txt}

FICHA DEL PROTAGONISTA:
- Nombre: {char_name}
- Descripción física y vestuario: {char_desc} {char_clothing}
- Biomecánica y actitud: {char_acting} {char_locomotion}
- Tono del universo: {tone}
{companions_directive}
{speech_directive}
ESTRUCTURA DE TIKTOK EN 30 SEGUNDOS (3 TOMAS NARRATIVAS DE 10s CON CONTINUIDAD DIRECTA):
- TOMA 1: HOOK VIRAL (< 3s): Interrupción de patrón visual o verbal inmediata con el protagonista en primer plano liderando la acción.
- TOMA 2: ESCALADA Y CONTINUIDAD DIRECTA (10-20s): Continuidad lógica directa donde terminó la toma 1. Superación de obstáculo, tensión o exploración.
- TOMA 3: REMATE MEMORABLE (20-30s): Conclusión satisfactoria, triunfo o remate simpático grupal.
- ¡PROHIBIDO TOTALMENTE ROMPER LA CUARTA PARED!: Los personajes NUNCA hablan a la cámara ni al espectador (JAMÁS decir "dale like", "comparte" o "suscríbete").

Devuelve ÚNICAMENTE un objeto JSON válido con la siguiente estructura exacta:
```json
{{
  "title": "Título llamativo para TikTok",
  "location": "Nombre específico del lugar o ciudad",
  "music_theme": "Descripción en inglés de la música de fondo sugerida",
  "tiktok_caption": "Copy cautivador para el pie de video en TikTok",
  "tiktok_hashtags": ["#Tag1", "#Tag2", "#Tag3"],
  "scenes": [
    {{
      "id": "toma_1",
      "title": "Título Toma 1",
      "description": "Descripción visual detallada del Hook viral (<3s) con el protagonista en primer plano",
      "dialogue": [
        {{"speaker": "{char_name}", "voice": "Spanish", "line": "Línea gancho del diálogo"}}
      ],
      "camera": "Dynamic push-in, low-angle ground level macro shot",
      "pacing_notes": "Pattern interrupt hook <3s"
    }},
    {{
      "id": "toma_2",
      "title": "Título Toma 2",
      "description": "Descripción visual de la escalada con continuidad lógica directa",
      "dialogue": [
        {{"speaker": "{char_name}", "voice": "Spanish", "line": "Línea de acción de la escalada"}}
      ],
      "camera": "Whip pan tracking shot, dynamic framing",
      "pacing_notes": "Escalada y retención"
    }},
    {{
      "id": "toma_3",
      "title": "Título Toma 3",
      "description": "Descripción visual del desenlace y remate memorable",
      "dialogue": [
        {{"speaker": "{char_name}", "voice": "Spanish", "line": "Remate memorable final"}}
      ],
      "camera": "Cinematic closing tracking shot",
      "pacing_notes": "Remate dentro de la ficción"
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

        temp_val = 1.0 if ("kimi" in model_name.lower() or "deepseek" in model_name.lower()) else 0.75
        timeout_sec = 120 if ("kimi" in model_name.lower() or "deepseek" in model_name.lower()) else 60
        max_tokens_val = 6000 if ("kimi" in model_name.lower() or "deepseek" in model_name.lower() or "minimax" in model_name.lower()) else 2500

        logger.info(f"✨ Generando guion con Opencode Go ({model_name}, temp={temp_val})...")
        payload = {
            "model": model_name,
            "messages": [
                {"role": "system", "content": "Eres un guionista cinematográfico de TikTok. Responde ÚNICAMENTE con JSON válido."},
                {"role": "user", "content": prompt}
            ],
            "temperature": temp_val,
            "max_tokens": max_tokens_val,
        }
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
                "x-opencode-session": "flow_video_session",
                "User-Agent": "FlowVideoAutomation/2.0",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            return self._parse_json_response(data["choices"][0]["message"]["content"])
        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8", errors="replace")
            logger.warning(f"⚠️ Opencode Go ({model_name}) devolvió HTTP {e.code}: {err_body}")
            raise RuntimeError(f"Opencode Go ({model_name}) HTTP {e.code}: {err_body}")

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
                ep_data = self._call_gemini(prompt, resolved_model)
            elif active_provider == "openai":
                ep_data = self._call_openai(prompt, resolved_model)
            elif active_provider == "anthropic":
                ep_data = self._call_anthropic(prompt, resolved_model)
            else:
                ep_data = self._call_opencode(prompt, resolved_model)
        except Exception as e:
            # Fallback automático a Gemini si Opencode/OpenAI/Anthropic fallan y Gemini está disponible
            gemini_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
            if active_provider != "gemini" and gemini_key:
                logger.warning(f"Aviso del proveedor {active_provider.upper()} ({e}). Reintentando automáticamente con Google Gemini API...")
                gemini_model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash").strip()
                ep_data = self._call_gemini(prompt, gemini_model)
            else:
                raise e

        # Registrar locación en el historial del arquetipo
        loc_val = ep_data.get("location") or ep_data.get("city") or "Aventura"
        title_val = ep_data.get("title") or f"Episodio de {self.display_name}"
        self.record_episode(loc_val, title_val)
        return ep_data

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
