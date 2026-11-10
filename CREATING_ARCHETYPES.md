# 🎭 Guía para Crear tus Propios Arquetipos y Personajes

Este proyecto fue diseñado con una **arquitectura 100% modular y extensible**. Incluye arquetipos de ejemplo como **`explorer` (El Explorador Cósmico)** y **`cyberpunk` (Detective Neo-Tokio)**, y permite a cualquier creador añadir sus propios personajes, universos temáticos y estilos visuales **sin tocar una sola línea de código Python**.

---

## 🚀 Cómo Crear tu Propio Personaje en 3 Pasos

### Paso 1: Crear el Personaje en tu cuenta de Google Flow
1. Abre tu proyecto en [Google Flow](https://flow.google.com).
2. Ve a la pestaña **Personajes (*Characters*)** y pulsa en **Crear Personaje**.
3. Dale un nombre identificativo (por ejemplo: `mago 1`, `cyberpunk 1` o `vikingo 1`).
4. Genera o sube las imágenes de referencia del personaje y guarda la tarjeta.

---

### Paso 2: Crear el archivo JSON de tu Arquetipo
En la carpeta `archetypes/` del proyecto, haz una copia de [`archetypes/template.json`](archetypes/template.json) con el nombre de tu personaje:

```bash
cp archetypes/template.json archetypes/vikingo.json
```

Abre `archetypes/vikingo.json` y personaliza los campos:

```json
{
  "key": "vikingo",
  "display_name": "Ragnar el Navegante Nórdico",
  "character_name": "vikingo 1",
  "video_prefix": "vikingo",
  "character_dna": {
    "name": "Ragnar",
    "description": "Un imponente guerrero y navegante nórdico de 30 años con barba trenzada, túnica de lino gris y capa de piel con broche de plata, portando un cuerno tallado y botas de cuero.",
    "acting": "Firme, intrépido, astuto y observador. Camina con paso seguro sobre cubiertas de drakkar y costas rocosas, analizando el horizonte con mirada penetrante."
  },
  "world_rules": {
    "setting": "Fiordos nórdicos envueltos en niebla matutina, aldeas vikingas junto al mar y costas escarpadas.",
    "tone": "Expedición marítima de 30 segundos, tensión de sigilo, olas rugiendo y misterio legendario."
  },
  "visual_style": "Estilo cinematográfico fotorrealista de acción real, lente óptica de 35 mm f/1.8, iluminación nórdica fría con sutiles rayos dorados, detalles ultra nítidos.",
  "tiktok_default_caption": "¡Expedición vikinga hacia tierras desconocidas! ⚔️🌊🛡️",
  "tiktok_default_hashtags": ["#Vikingos", "#Historia", "#Aventura", "#Cine", "#Nórdico"]
}
```

#### Descripción de los campos:
| Campo | Tipo | Descripción |
| :--- | :--- | :--- |
| `key` | String | Identificador corto para la terminal (ej: `vikingo` -> se usa con `-a vikingo`). |
| `display_name` | String | Nombre visible en los logs del pipeline. |
| `character_name` | String | **Nombre exacto** que le diste al personaje en Google Flow para que el bot active su chip en cada toma. |
| `video_prefix` | String | Prefijo con el que se guardarán los videos descargados (ej: `vikingo_costa_30s.mp4`). |
| `character_dna.name` | String | Nombre narrativo del protagonista en los guiones. |
| `character_dna.description` | String | Descripción visual y vestuario que se inyecta en los prompts de video. |
| `character_dna.acting` | String | Comportamiento, biomecánica y actitud del personaje. |
| `world_rules.setting` | String | Locaciones y atmósfera típica de su universo. |
| `world_rules.tone` | String | Pacing y ritmo dramático para los guiones de TikTok. |
| `visual_style` | String | Parámetros de lente, iluminación y estética fotográfica para Google Flow. |
| `tiktok_default_caption` | String | Texto sugerido por defecto si publicas en TikTok. |
| `tiktok_default_hashtags` | Array | Lista de hashtags recomendados para la publicación. |

---

### Paso 3: Ejecutar el Pipeline con tu Arquetipo

¡Eso es todo! El sistema detectará automáticamente tu archivo `.json` y pondrá a trabajar al bot con tu nuevo personaje:

```bash
# Generar un episodio al azar de tu nuevo personaje:
python generate_and_assemble_episode.py random -a vikingo

# Generar un episodio eligiendo el modelo de IA (kimi, deepseek, haiku, claude):
python generate_and_assemble_episode.py random -a vikingo -m kimi -ft "Llegada sigilosa a una costa envuelta en niebla buscando un cofre antiguo"

# Generar solo ciertas tomas y sin publicar a TikTok:
python generate_and_assemble_episode.py random -a vikingo --scenes 1,2 --no-publish
```

---

## 🏛️ Arquetipos de Ejemplo Incluidos

El repositorio incluye dos ejemplos funcionales en la carpeta `archetypes/`:

1. **`explorer` (Alex: El Explorador Cósmico):**
   - Definido en [`archetypes/explorer.json`](archetypes/explorer.json).
   - Temática de exploración espacial, ruinas alienígenas, misterio cósmico y estética cinematográfica retro-futurista de 35mm.

2. **`cyberpunk` (Kael: Detective Neo-Tokio):**
   - Definido en [`archetypes/cyberpunk.json`](archetypes/cyberpunk.json).
   - Estética neo-noir, rascacielos cubiertos de neón y lluvia ácida, tecnología sombría e investigación detectivesca.

---

## 🔒 Arquetipos Privados (`private_archetypes/`)

Si tienes marcas registradas, personajes propios o universos narrativos confidenciales que no deseas exponer en Git:
- Guarda tus archivos de configuración o scripts en la carpeta `private_archetypes/`.
- El registro (`config_archetypes.py`) los detectará en tu entorno local automáticamente.
- La carpeta `private_archetypes/` está permanentemente ignorada en `.gitignore`, protegiendo tu propiedad intelectual de cualquier subida a repositorios públicos.
