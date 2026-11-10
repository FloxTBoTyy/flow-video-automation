# 🎬 Flow Video Automation

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Playwright](https://img.shields.io/badge/playwright-tested-green.svg)](https://playwright.dev/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Google Flow](https://img.shields.io/badge/Google-Flow-orange.svg)](https://flow.google.com)

Pipeline 100% autónomo y modular para la creación, ensamble y publicación de videos verticales (9:16) en **Google Flow** y **TikTok**, controlado mediante Playwright sobre Chrome DevTools Protocol (CDP).

Permite a cualquier creador definir sus propios personajes, historias y universos temáticos mediante sencillos archivos de configuración JSON sin tocar una sola línea de código Python.

---

## 🌟 Características Principales

- 🤖 **Automatización End-to-End**: Genera las tomas con IA en Google Flow, crea una escena limpia en formato vertical (9:16), ensambla los clips en orden narrativo cronológico y descarga el video final de 30 segundos.
- 🎭 **Arquitectura Multi-Arquetipo Modular**:
  - Arquetipos de ejemplo listos para usar (`explorer`, `cyberpunk`).
  - Creación ilimitada de arquetipos personalizados mediante archivos JSON en `archetypes/`.
  - Soporte de arquetipos privados en `private_archetypes/` (ignorado por Git, para creadores que desean mantener sus personajes y lore privados).
  - Consulta la [Guía para Crear Arquetipos](CREATING_ARCHETYPES.md).
- 🧠 **Motor Creativo con LLMs**: Generación dinámica de guiones cinematográficos de alta retención para TikTok mediante **Opencode Go** (Claude Haiku 5.5, Kimi, Deepseek) o **Google Gemini**.
- 🛡️ **Filtro Anti-Falsos Positivos**: Sanitización automática de prompts para evitar bloqueos por políticas de contenido de Google Flow.
- 🌐 **Agnóstico de Cuenta y Navegador**: Se conecta directamente a la sesión activa en tu navegador (Brave, Chrome) vía CDP, detectando automáticamente cualquier cuenta de Google (`/u/0/`, `/u/1/`, etc.) sin hardcodear credenciales.
- 🎯 **Control Granular de Tomas (`--scenes`)**: Permite generar solo tomas específicas (ej: `--scenes 1,2`) para reanudar episodios interrumpidos ahorrando créditos de IA.
- 📱 **Publicador de TikTok Integrado**: Automatiza la subida, descripción, hashtags y configuración de portada directamente en TikTok Studio.

---

## 📁 Estructura del Repositorio

```text
├── generate_and_assemble_episode.py  # Orquestador principal autónomo (Pipeline completo)
├── config_archetypes.py              # Registro dinámico de arquetipos (Públicos y Privados)
├── generic_engine.py                 # Motor dinámico para arquetipos definidos en JSON
├── archetypes/                       # Directorio de arquetipos en formato JSON
│   ├── explorer.json                 # Ejemplo: Alex, El Explorador Cósmico
│   ├── cyberpunk.json                # Ejemplo: Kael, Detective Neo-Tokio
│   └── template.json                 # Plantilla en blanco para crear nuevos personajes
├── flow_client.py                    # Controlador Playwright CDP para Google Flow
├── assemble_and_download.py          # Ensamble de clips en la línea de tiempo y descarga
├── tiktok_publisher.py               # Módulo de publicación autónoma en TikTok Studio
├── launch_browser.sh                 # Script para iniciar Brave/Chrome con puerto 9222 (CDP)
├── CREATING_ARCHETYPES.md            # Guía detallada para crear nuevos personajes
├── config.py                         # Constantes y configuración global
├── requirements.txt                  # Dependencias del proyecto en Python
└── .env.example                      # Plantilla de variables de entorno
```

---

## 🚀 Instalación y Puesta en Marcha

### 1. Clonar el repositorio
```bash
git clone https://github.com/tu-usuario/cuy-flow-automation.git
cd cuy-flow-automation
```

### 2. Crear y activar el entorno virtual
```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Instalar dependencias
```bash
pip install -r requirements.txt
playwright install chromium
```

### 4. Configurar variables de entorno
Copia la plantilla y añade tus claves de API:
```bash
cp .env.example .env
```
Edita `.env` con tus credenciales:
```env
OPENCODE_API_KEY=tu_opencode_api_key_aqui
GEMINI_API_KEY=tu_gemini_api_key_aqui
```

---

## 💻 Flujo de Trabajo

### Paso 1: Iniciar el navegador con Remote Debugging (CDP)
Para que el bot interactúe con tu sesión real de Google Flow sin captchas ni inicios de sesión bloqueados:
```bash
./launch_browser.sh
```
Inicia sesión en **Google Flow** en la ventana que se abre y entra al proyecto que quieras usar.

### Paso 2: Listar los arquetipos disponibles
```bash
python generate_and_assemble_episode.py --list
```

### Paso 3: Ejecutar el pipeline autónomo

#### Generar un episodio al azar con el arquetipo Explorer:
```bash
python generate_and_assemble_episode.py random -a explorer
```

#### Generar un episodio Cyberpunk guiado por una premisa libre (`-ft` o `--theme`):
```bash
python generate_and_assemble_episode.py random -a cyberpunk -m kimi -ft "Persecución en aerodeslizadores a través del distrito de neón bajo lluvia ácida"
```

#### Generar solo ciertas tomas (ahorro de créditos):
```bash
# Solo genera la toma 1 y 2, saltándose la 3:
python generate_and_assemble_episode.py random -a explorer --scenes 1,2
```

#### Reanudar la última historia guardada en caché:
```bash
python generate_and_assemble_episode.py -a explorer --resume --scenes 2,3
```

#### Solo generar clips sin ensamblar ni subir a TikTok:
```bash
python generate_and_assemble_episode.py random -a explorer --no-assemble --no-publish
```

---

## ⚙️ Opciones de Línea de Comandos (CLI)

| Parámetro | Alias | Descripción |
| :--- | :--- | :--- |
| `-a` | `--archetype` | Arquetipo a utilizar: `explorer`, `cyberpunk`, o tu propio archivo JSON en `archetypes/` (por defecto: `explorer`). |
| `--list` | | Muestra todos los arquetipos disponibles en el sistema. |
| `-m` | `--model` | Modelo de LLM: `kimi`, `haiku`, `claude`, `deepseek`, etc. |
| `-ft` | `--theme`, `--free-theme` | Premisa o tema libre para guiar la historia generada por la IA. |
| `-s` | `--scenes`, `--tomas` | Tomas a generar separadas por comas (ej: `1,2` o `2`). |
| `-f` | `--file`, `--episode-file` | Carga un archivo JSON con la historia sin llamar al LLM. |
| `--resume` | `--reuse-last` | Reutiliza la última historia guardada en caché. |
| `--no-assemble` | `--skip-assemble` | Genera los clips pero no crea la escena ni ensambla. |
| `--no-publish` | `--skip-tiktok` | Descarga el video final pero no lo sube a TikTok. |
| `--dry-run-publish` | | Prepara la publicación en TikTok sin dar clic final en Publicar. |

---

## 🔒 Privacidad y Arquetipos Privados

Si estás creando contenido para una marca, canal o propiedad intelectual privada que **no quieres compartir públicamente**:
1. El directorio `private_archetypes/` está configurado en `.gitignore` para que **nunca se suba a Git**.
2. Puedes colocar tus scripts y arquetipos privados dentro de `private_archetypes/` y el registro los detectará automáticamente en tu máquina local.
3. El archivo `.env` con tus claves privadas de API también está permanentemente ignorado por Git.

---

## 🧠 Modelos de IA Soportados y Roadmap

### 🟢 Soportados Actualmente (Integrados):

1. **Vía Opencode Go API** (`OPENCODE_API_KEY` en `.env`):
   - `-m kimi`: Moonshot Kimi (`kimi-k2.7-code`, `kimi-k3.1-pro`) — Respuestas ultra dinámicas y gran ingenio narrativo.
   - `-m deepseek`: DeepSeek (`deepseek-v4-pro`) — Excelente coherencia estructural y lógica dramática.
   - `-m haiku` o `-m claude`: Anthropic Claude (`claude-haiku-5-5`) — Guiones de alta retención para TikTok.
   - `-m minimax`: MiniMax (`minimax-m3.1-flash`) — Generación rápida y concisa.
   - `-m qwen`: Alibaba Qwen (`qwen-3.7-plus`).

2. **Vía Google Gemini Oficial** (`GEMINI_API_KEY` en `.env`):
   - Integración nativa con `google-genai` SDK (`gemini-2.5-flash`, `gemini-2.0-flash`).
   - Funciona como generador principal o como respaldo automático si Opencode no responde.

### 🔜 Próximas Versiones (Roadmap):

- [ ] **OpenAI SDK Directo**: Integración nativa con endpoints de OpenAI (`gpt-4o`, `gpt-4o-mini`).
- [ ] **Anthropic SDK Oficial**: Conexión directa mediante clave de Anthropic (`claude-3-5-sonnet`).
- [ ] **Modelos Locales**: Soporte para ejecutar LLMs locales en tu máquina sin costo de API mediante **Ollama** o **vLLM** (`Llama 3`, `Mistral`, `DeepSeek-R1`).
- [ ] **Generación de Voz (TTS)**: Inyección automática de pistas de audio sincronizadas con ElevenLabs.

---

## 🤝 Contribuciones

Las contribuciones son bienvenidas. Si deseas colaborar:
1. Haz un Fork del proyecto.
2. Crea una rama para tu feature (`git checkout -b feature/nueva-mejora`).
3. Haz commit de tus cambios (`git commit -m 'feat: añadir nueva función'`).
4. Haz Push a la rama (`git push origin feature/nueva-mejora`).
5. Abre un Pull Request.

---

## 📄 Licencia

Este proyecto está bajo la Licencia [MIT](LICENSE).
