"""Pipeline 100% autónomo para generar las 3 tomas del episodio en Google Flow,
ensamblarlas en la línea de tiempo de Escenas y descargar el video final de 30 segundos.
"""

import asyncio
import json
import logging
import os
import re
import shutil
import subprocess
import time
from pathlib import Path
from typing import Optional, List, Dict, Any

os.environ["no_proxy"] = "localhost,127.0.0.1"
os.environ["NO_PROXY"] = "localhost,127.0.0.1"

from playwright.async_api import async_playwright, Page, BrowserContext
from config import CDP_URL, OUTPUT_DIR, EPISODES

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("FullEpisodePipeline")

PROJECT_URL = "https://flow.google.com/project/d9315bbf-3240-478d-8b35-95ac1befd996"
SCENE_URL = "https://flow.google.com/project/d9315bbf-3240-478d-8b35-95ac1befd996/scene/3bd6b056-5a7f-488f-b2bb-7fbae9a53dfa"

def get_base_project_url(url: str) -> Optional[str]:
    """Extrae la URL base del proyecto de Google Flow (soporta cuentas /u/0/, /u/1/, etc.)."""
    if not url:
        return None
    clean = url.split("?")[0].rstrip("/")
    m = re.match(r"(https?://flow\.google\.com(?:/u/\d+)?/project/[a-zA-Z0-9_-]+)", clean)
    if m:
        return m.group(1)
    return None

async def ensure_project_page(page: Page, target_project_url: Optional[str] = None) -> bool:
    """Asegura que estamos en la página principal del proyecto de Flow correspondiente."""
    target_url = target_project_url or get_base_project_url(page.url) or PROJECT_URL
    clean_current = page.url.split("?")[0].rstrip("/")
    clean_target = target_url.split("?")[0].rstrip("/")
    if clean_current != clean_target or "/scene/" in page.url or "/character" in page.url:
        logger.info(f"🔄 Navegando a la página principal del proyecto ({target_url})...")
        await page.goto(target_url, wait_until="domcontentloaded")
        await page.wait_for_timeout(3000)
    return True

async def get_first_media_src(page: Page) -> str:
    """Obtiene el identificador src del primer video o imagen en la galería de Flow."""
    return await page.evaluate('''() => {
        const firstTile = document.querySelector('flow-video-tile');
        if (!firstTile) return '';
        const vid = firstTile.querySelector('video');
        if (vid && vid.src) return vid.src;
        const img = firstTile.querySelector('img');
        if (img && img.src) return img.src;
        return '';
    }''')

async def count_completed_tiles(page: Page) -> int:
    """Cuenta cuántos clips de video o tiles existen en el proyecto."""
    return await page.evaluate('''() => {
        const tiles = document.querySelectorAll('flow-video-tile');
        return tiles.length;
    }''')

async def ensure_generation_settings(page: Page) -> bool:
    """Configura los parámetros óptimos (Vídeo, 9:16, 720p, 10 s, x1)."""
    settings_btn = page.locator('button[aria-label*="Botón de configuración" i]').first
    if await settings_btn.count() > 0 and await settings_btn.is_visible():
        current_text = await settings_btn.inner_text()
        if "720p" in current_text and "10" in current_text and "x1" in current_text and "9_16" in current_text:
            logger.info("Opciones de generación ya calibradas (720p · 10s · 9:16 · x1).")
            return True

        await settings_btn.click()
        await page.wait_for_timeout(600)
        overlay = page.locator('.cdk-overlay-container, .flow-menu-panel').first

        for btn_txt in ["Vídeo", "Ingredientes", "9:16", "720p", "10 s", "x1"]:
            btn = overlay.locator(f'button:has-text("{btn_txt}")').first
            if await btn.count() > 0 and await btn.is_visible():
                await btn.click()
                await page.wait_for_timeout(300)

        await page.keyboard.press("Escape")
        await page.wait_for_timeout(300)
    return True

async def ensure_character_ingredient(page: Page, character_name: Optional[str] = None) -> bool:
    """Añade el ingrediente de personaje si aún no está presente en la barra."""
    char_label = character_name or "Personaje"
    chip = page.locator('.reference-ingredient-chip, .prompt-ingredient-bar').first
    if await chip.count() > 0 and await chip.is_visible():
        logger.info(f"Chip del personaje '{char_label}' ya activo.")
        return True

    add_btn = page.locator('button[aria-label*="Agregar ingredientes al cuadro de instrucción" i]').first
    if await add_btn.count() > 0 and await add_btn.is_visible():
        await add_btn.click()
        await page.wait_for_timeout(600)
        pers_item = page.locator('.cdk-overlay-container mat-list-item:has-text("Personajes")').first
        if await pers_item.count() > 0 and await pers_item.is_visible():
            await pers_item.click()
            await page.wait_for_timeout(600)

        if character_name:
            card = page.locator('.cdk-overlay-container').locator(f'text={character_name}').last
            if await card.count() > 0:
                await card.click()
                logger.info(f"✅ Personaje '{character_name}' seleccionado.")
                await page.wait_for_timeout(500)
                return True

        char_kw = character_name.split()[0].lower() if character_name else ""
        selector = f'.cdk-overlay-container img[alt*="{char_kw}" i], .cdk-overlay-container .media-tile' if char_kw else '.cdk-overlay-container .media-tile'
        first_card = page.locator(selector).first
        if await first_card.count() > 0:
            await first_card.click()
            logger.info(f"✅ Tarjeta de personaje seleccionada.")
            await page.wait_for_timeout(500)
            return True
    return False

async def inject_and_generate_take(page: Page, prompt_text: str, take_title: str) -> bool:
    """Inyecta el prompt en Flow y pulsa 'Iniciar generación', esperando a que termine."""
    logger.info(f"\n{'='*60}\n🚀 GENERANDO: {take_title.upper()}\n{'='*60}")
    
    # 1. Contar clips completados actuales y guardar el src del primer video
    initial_count = await count_completed_tiles(page)
    initial_src = await get_first_media_src(page)
    initial_short = initial_src.split("?")[0][-25:] if initial_src else "ninguno"
    logger.info(f"Clips actualmente en el proyecto: {initial_count} (primer src: ...{initial_short})")

    # 2. Inyectar prompt
    target_el = page.locator('div.ProseMirror, div[aria-label="¿Qué quieres crear?"]').first
    if await target_el.count() == 0 or not await target_el.is_visible():
        logger.error("No se encontró el campo de entrada de prompt.")
        return False

    await target_el.click()
    await page.wait_for_timeout(200)
    await page.keyboard.press("Control+A")
    await page.keyboard.press("Backspace")
    await page.wait_for_timeout(200)

    await page.evaluate("""
        ({text}) => {
            const el = document.querySelector('div.ProseMirror, div[aria-label="¿Qué quieres crear?"]');
            if (el) {
                el.focus();
                document.execCommand('insertText', false, text);
                el.dispatchEvent(new Event('input', { bubbles: true }));
            }
        }
    """, {"text": prompt_text})
    await page.wait_for_timeout(500)

    # 3. Presionar botón de generación
    gen_btn = page.locator('button[aria-label*="Iniciar generación" i]').first
    if await gen_btn.count() > 0 and await gen_btn.is_visible():
        logger.info("Pulsando botón 'Iniciar generación' (consume 15 créditos)...")
        await gen_btn.click()
    else:
        logger.info("Pulsando Enter para generar...")
        await page.keyboard.press("Enter")

    # 4. Esperar a que Flow registre el trabajo e inicie la generación
    await page.wait_for_timeout(6000)

    # 5. Monitorear hasta que el clip termine de generarse (máximo 240s)
    logger.info(f"Monitoreando renderizado en la nube de Flow para '{take_title}'...")
    start_time = time.time()
    generation_started = False
    
    while time.time() - start_time < 240:
        await asyncio.sleep(4)
        elapsed = time.time() - start_time
        current_count = await count_completed_tiles(page)
        current_src = await get_first_media_src(page)
        
        is_generating = await page.evaluate('''() => {
            const text = document.body ? document.body.innerText.toLowerCase() : '';
            const genText = text.includes('generando') || text.includes('procesando') || text.includes('generating');
            const spinners = document.querySelector('mat-progress-spinner, flow-progress-bar, [role="progressbar"]') !== null;
            return genText || spinners;
        }''')
        
        if is_generating:
            generation_started = True

        # Criterio definitivo de completitud:
        # 1. El primer clip de la galería cambió por un nuevo src válido de video de Flow
        has_new_video = bool(current_src and current_src != initial_src and "flow.google.com/asb/" in current_src)
        # 2. O la cantidad total de tiles aumentó
        has_more_tiles = bool(current_count > initial_count)

        # Flow tarda un mínimo de 30 segundos para generar 10s de video en la nube.
        if elapsed >= 30:
            if has_new_video or (has_more_tiles and not is_generating) or (generation_started and not is_generating):
                logger.info(f"🎉 ¡{take_title} GENERADO EXITOSAMENTE! (Clips: {current_count}, tiempo: {int(elapsed)}s)")
                await page.wait_for_timeout(3000)
                return True
        
        if int(elapsed) % 15 == 0 or int(elapsed) % 15 < 4:
            logger.info(f"Generando en Flow... ({int(elapsed)}s transcurridos, en_proceso={is_generating}, new_video={has_new_video}, tiles={current_count}/{initial_count})")

    logger.warning("Tiempo de espera agotado para el renderizado del clip.")
    return False

# ==========================================
# SECCIÓN DE ENSAMBLE Y DESCARGA EN ESCENAS
# ==========================================

async def ensure_scene_editor(page: Page, scene_url: Optional[str] = None) -> bool:
    """Navega al editor de escenas del proyecto actual."""
    if "/scene/" not in page.url:
        # 1. Intentar hacer clic en el botón nativo de Escenas en la barra de Flow
        escenas_btn = page.locator('button:has-text("Escenas")')
        if await escenas_btn.count() > 0 and await escenas_btn.first.is_visible():
            logger.info("Navegando a Escenas mediante el botón 'Escenas' de Flow...")
            await escenas_btn.first.click()
            await page.wait_for_timeout(3000)
        elif scene_url:
            logger.info(f"Navegando al editor de escenas ({scene_url})...")
            await page.goto(scene_url, wait_until="domcontentloaded")
            await page.wait_for_timeout(3000)
        else:
            logger.info(f"Navegando al editor de escenas por defecto ({SCENE_URL})...")
            await page.goto(SCENE_URL, wait_until="domcontentloaded")
            await page.wait_for_timeout(3000)
    else:
        logger.info(f"Ya en el editor de escena: {page.url}")

    entendido = page.locator('button:has-text("Entendido")')
    if await entendido.count() > 0 and await entendido.first.is_visible():
        await entendido.first.click()
        await page.wait_for_timeout(500)
    return True

async def create_new_scene(page: Page, target_project_url: Optional[str] = None) -> bool:
    """Crea una nueva escena limpia directamente desde el menú '+' y la configura en 9:16 vertical."""
    logger.info("🎬 Creando nueva escena limpia en Google Flow...")
    
    # 1. Si ya estamos dentro de un /scene/, salir a la vista principal del proyecto
    if "/scene/" in page.url:
        proj_url = target_project_url or get_base_project_url(page.url) or page.url.split("/scene/")[0]
        logger.info(f"Saliendo a la vista principal del proyecto ({proj_url})...")
        await page.goto(proj_url, wait_until="domcontentloaded")
        await page.wait_for_timeout(2000)

    # 2. Hacer clic en el botón '+' de la barra superior (Agregar menú de contenido multimedia)
    add_btn = page.locator('button[aria-label*="Agregar menú de contenido multimedia" i]').first
    if await add_btn.count() > 0 and await add_btn.is_visible():
        await add_btn.click()
        await page.wait_for_timeout(600)
        item = page.locator('.cdk-overlay-container [role="menuitem"]:has-text("Nueva escena"), .cdk-overlay-container button:has-text("Nueva escena")').first
        if await item.count() > 0:
            await item.click()
            logger.info("✅ 'Nueva escena' seleccionada desde el menú '+'.")
            await page.wait_for_timeout(3000)
    else:
        # Fallback: intentar mediante la pestaña 'Escenas' y clic derecho en el fondo
        logger.info("Intentando crear escena desde la vista de Escenas...")
        escenas_nav = page.locator('mat-nav-list a:has-text("Escenas"), a[aria-label*="Escenas" i]').first
        if await escenas_nav.count() > 0 and await escenas_nav.is_visible():
            await escenas_nav.click()
            await page.wait_for_timeout(2000)
            viewport = page.viewport_size or {'width': 1280, 'height': 800}
            await page.mouse.click(viewport['width'] * 0.85, viewport['height'] * 0.4, button='right')
            await page.wait_for_timeout(800)
            item = page.locator('.cdk-overlay-container [role="menuitem"]:has-text("Nueva escena"), .cdk-overlay-container button:has-text("Nueva escena")').first
            if await item.count() > 0:
                await item.click()
                logger.info("✅ 'Nueva escena' creada vía clic derecho.")
                await page.wait_for_timeout(3000)

    # 3. Cerrar tooltip de bienvenida si aparece
    entendido = page.locator('button:has-text("Entendido")')
    if await entendido.count() > 0 and await entendido.first.is_visible():
        await entendido.first.click()
        await page.wait_for_timeout(400)

    # 4. Asegurar que la relación de aspecto sea 9:16 vertical (para TikTok)
    ratio_btn = page.locator('button:has-text("16:9"), button:has-text("9:16"), [aria-label*="relación de aspecto" i]').first
    if await ratio_btn.count() > 0:
        txt = (await ratio_btn.text_content() or "").strip()
        if "16:9" in txt or "landscape" in txt.lower():
            logger.info("📐 Cambiando relación de aspecto de 16:9 a 9:16 vertical para TikTok...")
            await ratio_btn.click()
            await page.wait_for_timeout(800)
            logger.info(f"✅ Relación de aspecto establecida a: {(await ratio_btn.text_content() or '').strip()}")
        else:
            logger.info(f"✅ Relación de aspecto ya es 9:16 vertical: {txt}")

    # 5. Comprobar que el timeline esté limpio (0 clips)
    clips_cnt = await page.locator('.clip').count()
    if clips_cnt > 0:
        logger.warning(f"Se detectaron {clips_cnt} clips en la escena. Limpiando...")
        await clear_timeline(page)
    else:
        logger.info("✨ Línea de tiempo 100% limpia y nueva (0 clips).")

    return True

async def clear_timeline(page: Page):
    """Elimina todos los clips previos para armar una línea de tiempo limpia."""
    logger.info("Limpiando clips existentes en la línea de tiempo...")
    clips = page.locator('.clip')
    count = await clips.count()
    if count == 0:
        logger.info("Timeline ya está limpio (0 clips).")
        return

    logger.info(f"Eliminando {count} clips antiguos...")
    for _ in range(count + 3):
        clips = page.locator('.clip')
        current_count = await clips.count()
        if current_count == 0:
            break
        first_clip = clips.first
        try:
            await first_clip.click(force=True, timeout=2000)
        except Exception:
            await first_clip.evaluate("el => el.click()")

        await page.wait_for_timeout(200)
        await page.keyboard.press("Backspace")
        await page.wait_for_timeout(400)
        if await clips.count() == current_count:
            try:
                await first_clip.click(force=True, timeout=2000)
            except Exception:
                await first_clip.evaluate("el => el.click()")
            await page.keyboard.press("Delete")
            await page.wait_for_timeout(400)

    logger.info(f"Timeline limpio. Clips restantes: {await page.locator('.clip').count()}")

async def open_media_picker(page: Page) -> bool:
    """Abre el diálogo de medios seleccionando el clip previo para mostrar el botón '+'."""
    dialog = page.locator('mat-dialog-container, flow-media-picker-dialog, [role="dialog"]').first
    if await dialog.count() > 0 and await dialog.is_visible():
        return True

    clips = page.locator('.clip')
    clips_count = await clips.count()

    if clips_count == 0:
        empty_add = page.locator('button[aria-label="Agregar clip"]').first
        if await empty_add.count() > 0:
            await empty_add.click()
            await page.wait_for_timeout(1000)
    else:
        last_clip = clips.nth(clips_count - 1)
        try:
            await last_clip.click(force=True, timeout=2000)
        except Exception:
            await last_clip.evaluate("el => el.click()")
        await page.wait_for_timeout(400)

        clicked_add_btn = await page.evaluate('''() => {
            const addBtn = document.querySelector('button.add-clip-button, flow-scene-timeline button[aria-label*="Agregar" i]');
            if (addBtn) { addBtn.click(); return true; }
            return false;
        }''')

        if not clicked_add_btn:
            box = await last_clip.bounding_box()
            if box:
                end_x = box["x"] + box["width"]
                center_y = box["y"] + box["height"] / 2
                await page.mouse.click(end_x + 8, center_y)
                await page.wait_for_timeout(500)

        await page.wait_for_timeout(400)
        await page.evaluate('''() => {
            const all = Array.from(document.querySelectorAll('.cdk-overlay-container *'));
            const item = all.reverse().find(el => {
                const txt = (el.innerText || '').trim();
                return txt.includes('Agregar clip') && el.children.length <= 1;
            });
            if (item) item.click();
        }''')
        await page.wait_for_timeout(1200)

    for _ in range(12):
        if await dialog.count() > 0 and await dialog.is_visible():
            return True
        await page.wait_for_timeout(500)

    return False

async def add_clip_by_index(page: Page, index: int, label: str) -> bool:
    """Selecciona el clip en la posición `index` del modal de medios y confirma."""
    dialog = page.locator('mat-dialog-container, flow-media-picker-dialog, [role="dialog"]').first
    if await dialog.count() == 0 or not await dialog.is_visible():
        if not await open_media_picker(page):
            logger.error(f"No se pudo abrir el selector de medios para {label}.")
            return False

    asset_buttons = dialog.locator('button.asset-item')
    count = await asset_buttons.count()
    logger.info(f"Añadiendo {label} (Índice #{index} de {count} clips disponibles)...")

    if index >= count:
        logger.error(f"Índice {index} fuera de rango ({count} clips).")
        return False

    target_btn = asset_buttons.nth(index)
    await target_btn.click()
    await page.wait_for_timeout(800)

    confirm = page.locator('button:has-text("Agregar contenido multimedia")').first
    try:
        await confirm.wait_for(state="visible", timeout=4000)
        await confirm.click()
        logger.info(f"✅ {label} añadido exitosamente.")
        await page.wait_for_timeout(2500)
        return True
    except Exception:
        confirmed_js = await page.evaluate('''() => {
            const btn = Array.from(document.querySelectorAll('button')).find(b => (b.innerText || '').includes('Agregar contenido multimedia'));
            if (btn) { btn.click(); return true; }
            return false;
        }''')
        if confirmed_js:
            logger.info(f"✅ {label} añadido vía JS.")
            await page.wait_for_timeout(2500)
            return True

    return False

async def verify_video_file(file_path: Path) -> dict:
    """Verifica el archivo de video final con ffprobe."""
    cmd = [
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration,size,bit_rate:stream=codec_name,codec_type,width,height,r_frame_rate",
        "-of", "json", str(file_path)
    ]
    try:
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
        data = json.loads(res.stdout)
        duration = float(data.get("format", {}).get("duration", 0))
        size_mb = float(data.get("format", {}).get("size", 0)) / (1024 * 1024)
        streams = data.get("streams", [])
        v_stream = next((s for s in streams if s.get("codec_type") == "video"), {})
        a_stream = next((s for s in streams if s.get("codec_type") == "audio"), {})
        return {
            "path": str(file_path),
            "size_mb": round(size_mb, 2),
            "duration": round(duration, 2),
            "resolution": f"{v_stream.get('width')}x{v_stream.get('height')}",
            "video_codec": v_stream.get("codec_name"),
            "audio_codec": a_stream.get("codec_name"),
            "valid": duration > 28.0 and v_stream.get("width") is not None
        }
    except Exception as e:
        logger.warning(f"Error ffprobe: {e}")
        return {"valid": False, "error": str(e)}

async def export_and_download_final(page: Page, context: BrowserContext, output_filename: str) -> Optional[str]:
    """Inicia la exportación a 720p y descarga directamente al disco vía CDP."""
    logger.info("🎬 Iniciando exportación de la escena de 30 segundos...")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    target_path = OUTPUT_DIR / output_filename

    # Configurar CDP setDownloadBehavior
    try:
        cdp_session = await context.new_cdp_session(page)
        await cdp_session.send('Browser.setDownloadBehavior', {
            'behavior': 'allow',
            'downloadPath': str(OUTPUT_DIR.resolve()),
            'events': True
        })
        logger.info(f"✅ CDP setDownloadBehavior activado hacia: {OUTPUT_DIR}")
    except Exception as e:
        logger.warning(f"Aviso CDP: {e}")

    start_export_time = time.time()

    # Pulsar botón de descarga en cabecera
    dl_btn = page.locator('button[aria-label="Descargar escena"], button[aria-label*="Descargar contenido multimedia" i], button[aria-label*="Descargar" i]').first
    if await dl_btn.count() > 0:
        await dl_btn.click()
        await page.wait_for_timeout(1200)

        # Seleccionar 720p en el menú emergente
        await page.evaluate('''() => {
            const all = Array.from(document.querySelectorAll('.cdk-overlay-container *'));
            const opt = all.reverse().find(el => {
                const txt = (el.innerText || '').toLowerCase();
                return txt.includes('720p') && el.children.length <= 1;
            });
            if (opt) opt.click();
        }''')
        await page.wait_for_timeout(1500)

    # Monitorear exportación en Google Flow
    logger.info("Monitoreando exportación de Flow (renderizado en la nube)...")
    start_time = time.time()
    download_done = False

    while time.time() - start_time < 360:
        # 1. Comprobar botón 'Descargar escena' en notificación emergente
        toast_btn = page.locator('.cdk-overlay-container button:has-text("Descargar"), mat-snack-bar-container button:has-text("Descargar")').filter(has_not_text="Descartar").first
        if await toast_btn.count() > 0 and await toast_btn.is_visible():
            btn_txt = (await toast_btn.inner_text()).strip()
            logger.info(f"🎉 ¡Notificación de exportación completada! Pulsando '{btn_txt}'...")
            try:
                async with page.expect_download(timeout=6000) as dl_info:
                    await toast_btn.click()
                dl = await dl_info.value
                await dl.save_as(str(target_path))
                download_done = True
                break
            except Exception:
                logger.info("Descarga en proceso vía CDP directamente al disco...")

        # 2. Comprobar si el archivo nuevo ya fue guardado en disco
        for sdir in [OUTPUT_DIR, Path.home() / "Descargas", Path.home() / "Downloads"]:
            if not sdir.exists():
                continue

            crdownload_files = list(sdir.glob("*.crdownload"))
            if crdownload_files:
                logger.info(f"Descargando datos: {crdownload_files[0].name} ({crdownload_files[0].stat().st_size / (1024*1024):.2f} MB)...")
                await asyncio.sleep(2)
                continue

            for f in sorted(sdir.glob("*.mp4"), key=os.path.getmtime, reverse=True):
                if f.stat().st_mtime >= start_export_time - 3.0 and f.stat().st_size > 500000:
                    s1 = f.stat().st_size
                    await asyncio.sleep(1.5)
                    s2 = f.stat().st_size
                    if s1 == s2 and s1 > 5000000:
                        logger.info(f"Archivo completado detectado: {f.name} ({s2 / (1024*1024):.2f} MB)")
                        if f != target_path:
                            shutil.copy2(f, target_path)
                        download_done = True
                        break

            if download_done:
                break

        if download_done:
            break

        await asyncio.sleep(3)
        elapsed = int(time.time() - start_time)
        if elapsed % 15 == 0:
            logger.info(f"Esperando finalización de exportación... ({elapsed}s)")

    if target_path.exists() and target_path.stat().st_size > 5000000:
        meta = await verify_video_file(target_path)
        logger.info(f"🎉 ¡VIDEO FINAL VERIFICADO CON ÉXITO!")
        logger.info(f"   Ruta: {target_path}")
        logger.info(f"   Duración: {meta.get('duration')}s | Resolución: {meta.get('resolution')} | Tamaño: {meta.get('size_mb')} MB | Codec: {meta.get('video_codec')}/{meta.get('audio_codec')}")
        return str(target_path)

    return None

# ==========================================
# ORQUESTADOR PRINCIPAL DEL EPISODIO
async def run_full_pipeline(
    episode_input: Any = "random",
    publish_tiktok: bool = False,
    tiktok_dry_run: bool = False,
    model: Optional[str] = None,
    archetype: Optional[str] = None,
    free_theme: Optional[str] = None,
    scenes_filter: Optional[List[int]] = None,
    episode_file: Optional[str] = None,
    resume_last: bool = False,
    no_assemble: bool = False,
):
    from config_archetypes import ArchetypeRegistry
    archetype_cfg = ArchetypeRegistry.get_archetype_config(archetype)
    archetype_key = archetype_cfg["key"]
    target_project_url = archetype_cfg["flow_project_url"]
    char_ingredient = archetype_cfg["character_name"]
    prompt_builder_cls = archetype_cfg["prompt_builder"]

    p = await async_playwright().start()
    browser = await p.chromium.connect_over_cdp(CDP_URL)
    context = browser.contexts[0]

    if isinstance(episode_input, dict):
        ep_data = episode_input
    elif episode_file:
        ep_path = Path(episode_file)
        if not ep_path.exists():
            alt_path = Path("private_archetypes") / Path(episode_file).name
            if alt_path.exists():
                ep_path = alt_path
            else:
                logger.error(f"❌ El archivo de episodio '{episode_file}' no existe.")
                await browser.close()
                await p.stop()
                return
        with open(ep_path, "r", encoding="utf-8") as f:
            ep_data = json.load(f)
        logger.info(f"📄 Episodio cargado desde archivo JSON: {ep_path}")
    elif resume_last:
        ep_path = Path(f"last_episode_{archetype_key}.json")
        if not ep_path.exists():
            alt_path = Path("private_archetypes") / f"last_episode_{archetype_key}.json"
            if alt_path.exists():
                ep_path = alt_path
            else:
                logger.error(f"❌ No se encontró archivo previo para reanudar ({ep_path}).")
                await browser.close()
                await p.stop()
                return
        with open(ep_path, "r", encoding="utf-8") as f:
            ep_data = json.load(f)
        logger.info(f"🔄 Reanudando última historia guardada: '{ep_data.get('title')}'")
    else:
        pref = None if episode_input in ["random", "azar", None] else str(episode_input)
        
        story_gen = archetype_cfg.get("story_generator")
        if not story_gen:
            logger.error(f"❌ No se encontró generador de historias para {archetype_cfg['display_name']}.")
            await browser.close()
            await p.stop()
            return

        resolved_model = story_gen.resolve_model_name(model) if hasattr(story_gen, "resolve_model_name") else model
        logger.info(f"✨ Generando historia para [{archetype_cfg['display_name']}] usando {resolved_model or 'modelo configurado'}...")
        try:
            ep_data = story_gen.generate_episode(pref, model=resolved_model, free_theme=free_theme)
        except Exception as e:
            # Fallback con Gemini API si está soportado por el generador y Opencode falla
            if hasattr(story_gen, "generate_episode_with_gemini") and getattr(story_gen, "get_api_key", lambda: False)():
                logger.warning(f"Reintentando historia con API oficial de Gemini: {e}")
                ep_data = story_gen.generate_episode_with_gemini(pref, free_theme=free_theme)
            else:
                logger.error(f"❌ Error al generar historia para {archetype_cfg['display_name']}: {e}")
                logger.error("🛑 Proceso DETENIDO para NO gastar tus créditos de Flow en una historia no deseada.")
                await browser.close()
                await p.stop()
                return

    # Guardar copia de seguridad de la historia actual para permitir reanudación
    cache_path = Path(f"last_episode_{archetype_key}.json")
    try:
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump(ep_data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.warning(f"No se pudo guardar copia de seguridad del episodio: {e}")

    scenes = ep_data["scenes"]
    clean_slug = (ep_data.get("city") or ep_data.get("location") or "escena").lower().replace(" ", "_").replace("á", "a").replace("ñ", "n")
    output_filename = f"{archetype_cfg['video_prefix']}_{clean_slug}_30s.mp4"

    logger.info(f"\n{'='*70}\n🌟 INICIANDO PIPELINE AUTÓNOMO [{archetype_cfg['display_name'].upper()}]: {ep_data['title'].upper()}\n{'='*70}")

    page = None
    # 1. Priorizar una pestaña de Flow que ya tenga un proyecto abierto
    for pg in context.pages:
        if "flow.google.com" in pg.url and "/project/" in pg.url and "character" not in pg.url:
            page = pg
            break

    # 2. Si no, buscar cualquier pestaña de Flow activa
    if not page:
        for pg in context.pages:
            if "flow.google.com" in pg.url and "character" not in pg.url:
                page = pg
                break

    if not page:
        logger.error("No se encontró ninguna pestaña de Google Flow abierta en el navegador.")
        await browser.close()
        await p.stop()
        return

    await page.bring_to_front()

    # 🌐 Autodetección agnóstica de la cuenta y proyecto activo en el navegador
    detected_project = get_base_project_url(page.url)
    if detected_project:
        logger.info(f"🌐 Proyecto detectado automáticamente en tu navegador: {detected_project}")
        target_project_url = detected_project
    elif target_project_url and "flow.google.com/project/" in target_project_url:
        logger.info(f"ℹ️ Usando proyecto configurado en .env como fallback: {target_project_url}")
    else:
        logger.warning(f"⚠️ No se detectó un proyecto específico en la URL actual ({page.url}). Usando pestaña actual.")
        target_project_url = page.url

    # FASE 1: GENERACIÓN DE CLIPS EN FLOW
    await ensure_project_page(page, target_project_url=target_project_url)
    await ensure_generation_settings(page)

    generated_count = 0
    for i, sc in enumerate(scenes):
        scene_num = i + 1
        if scenes_filter and scene_num not in scenes_filter:
            logger.info(f"⏭️ [SALTANDO TOMA {scene_num}/{len(scenes)}] '{sc['title']}' según filtro --scenes {scenes_filter}")
            continue

        take_id = sc["id"]
        take_title = sc["title"]
        prompt = prompt_builder_cls.build_scene_by_id(take_id, scenes=scenes)

        logger.info(f"\n▶️ [PASO {scene_num}/{len(scenes)}] Preparando generación para: {take_title}")
        await ensure_character_ingredient(page, character_name=char_ingredient)
        success = await inject_and_generate_take(page, prompt, take_title)
        if not success:
            logger.error(f"Fallo en la generación de {take_title}. Deteniendo pipeline.")
            await browser.close()
            await p.stop()
            return

        generated_count += 1
        # Pausa breve entre tomas
        await page.wait_for_timeout(3000)

    logger.info(f"\n🎉 ¡Generación de tomas en Google Flow completada ({generated_count} tomas generadas)!")

    if no_assemble:
        logger.info("\n🛑 [ENSAMBLE OMITIDO] Se ha indicado --no-assemble. Las tomas quedan en la galería de Flow sin ensamblar.")
        return

    # FASE 2: ENSAMBLE EN LA LÍNEA DE TIEMPO DE ESCENAS (NUEVA ESCENA 9:16)
    logger.info("\n🎬 [FASE DE ENSAMBLE] Creando nueva escena limpia en formato 9:16 vertical...")
    await create_new_scene(page, target_project_url=target_project_url)
    await page.wait_for_timeout(1000)

    # 2. Agregar los clips generados en orden cronológico narrativo:
    if scenes_filter == [1, 2]:
        # Caso especial: Toma 3 ya existía en la galería antes de generar Toma 1 y Toma 2
        logger.info(f"Añadiendo Toma 1 ({scenes[0]['title']}) desde índice 1...")
        await add_clip_by_index(page, index=1, label=f"Toma 1: {scenes[0]['title']}")
        await page.wait_for_timeout(2000)

        logger.info(f"Añadiendo Toma 2 ({scenes[1]['title']}) desde índice 0...")
        await add_clip_by_index(page, index=0, label=f"Toma 2: {scenes[1]['title']}")
        await page.wait_for_timeout(2000)

        logger.info(f"Añadiendo Toma 3 ({scenes[2]['title']}) desde índice 2 (generada previamente)...")
        await add_clip_by_index(page, index=2, label=f"Toma 3: {scenes[2]['title']}")
        await page.wait_for_timeout(2500)
    else:
        # Caso estándar (3 tomas generadas en este run en orden 1, 2, 3)
        # Índice 2: Toma 1 (la más antigua de las 3 nuevas)
        # Índice 1: Toma 2
        # Índice 0: Toma 3 (la más reciente de las 3 nuevas)
        logger.info(f"Añadiendo Toma 1 ({scenes[0]['title']}) desde índice 2...")
        await add_clip_by_index(page, index=2, label=f"Toma 1: {scenes[0]['title']}")
        await page.wait_for_timeout(2000)

        logger.info(f"Añadiendo Toma 2 ({scenes[1]['title']}) desde índice 1...")
        await add_clip_by_index(page, index=1, label=f"Toma 2: {scenes[1]['title']}")
        await page.wait_for_timeout(2000)

        logger.info(f"Añadiendo Toma 3 ({scenes[2]['title']}) desde índice 0...")
        await add_clip_by_index(page, index=0, label=f"Toma 3: {scenes[2]['title']}")
        await page.wait_for_timeout(2500)

    total_clips = await page.locator('.clip').count()
    logger.info(f"✅ Clips finales en la línea de tiempo: {total_clips}/3 (30.00 segundos).")

    # Asegurar que la escena/clip está seleccionada para activar el botón de descarga
    clips = page.locator('.clip')
    if await clips.count() > 0:
        try:
            await clips.last.click(force=True, timeout=2000)
        except Exception:
            await clips.last.evaluate("el => el.click()")
        await page.wait_for_timeout(1000)

    # FASE 3: EXPORTACIÓN Y DESCARGA FINAL
    final_video_path = await export_and_download_final(page, context, output_filename)

    if final_video_path:
        print("\n" + "=" * 70)
        print("🎉 ¡NUEVO VIDEO DE 30 SEGUNDOS GENERADO, ENSAMBLADO Y DESCARGADO!")
        print(f"🎬 Episodio: {ep_data['title']}")
        print(f"📁 Archivo final: {final_video_path}")
        if ep_data.get("tiktok_caption"):
            print(f"📱 Copy TikTok: {ep_data['tiktok_caption']}")
        if ep_data.get("tiktok_hashtags"):
            tags = " ".join(ep_data["tiktok_hashtags"]) if isinstance(ep_data["tiktok_hashtags"], list) else str(ep_data["tiktok_hashtags"])
            print(f"🏷️ Hashtags recomendados: {tags}")
        print("=" * 70 + "\n")

        # FASE 4: PUBLICACIÓN EN TIKTOK STUDIO (OPCIONAL O AUTOMÁTICA)
        if publish_tiktok:
            logger.info("\n📱 [FASE DE PUBLICACIÓN TIKTOK] Subiendo video a TikTok Studio...")
            from tiktok_publisher import TikTokPublisher
            publisher = TikTokPublisher()
            caption = ep_data.get("tiktok_caption") or archetype_cfg["tiktok_default_caption"]
            hashtags = ep_data.get("tiktok_hashtags") or archetype_cfg["tiktok_default_hashtags"]
            await publisher.publish_video_pipeline(
                video_path=final_video_path,
                caption=caption,
                hashtags=hashtags,
                dry_run=tiktok_dry_run,
            )
    else:
        logger.error("No se pudo completar la descarga final.")

    # Restablecer la pestaña de Flow a la vista principal del proyecto al finalizar
    try:
        if page:
            logger.info(f"🔄 Restableciendo la pestaña de Flow a la vista principal del proyecto ({target_project_url})...")
            await ensure_project_page(page, target_project_url=target_project_url)
    except Exception as e:
        logger.warning(f"No se pudo restablecer la pestaña de Flow: {e}")

    await browser.close()
    await p.stop()

def parse_scenes_arg(scenes_str: Optional[str]) -> Optional[List[int]]:
    if not scenes_str:
        return None
    result = []
    for part in str(scenes_str).replace("-", ",").split(","):
        part = part.strip()
        if part.isdigit():
            val = int(part)
            if val not in result:
                result.append(val)
    return sorted(result) if result else None

if __name__ == "__main__":
    import argparse
    import sys
    from config_archetypes import ArchetypeRegistry

    parser = argparse.ArgumentParser(description="Pipeline autónomo de generación y publicación multi-arquetipo")
    parser.add_argument("city", nargs="?", default="random", help="Ciudad o locación (o 'random')")
    parser.add_argument("model_arg", nargs="?", default=None, help="Modelo de Opencode opcional al final (ej: kimi, haiku)")
    parser.add_argument("-a", "--archetype", "--avatar", "--arquetipo", type=str, default=None, help="Arquetipo a utilizar (ej: 'explorer', 'cyberpunk', etc.)")
    parser.add_argument("--list", "-l", action="store_true", help="Listar arquetipos disponibles")
    parser.add_argument("--no-publish", "--skip-tiktok", action="store_true", help="Solo generar y ensamblar el video local sin subirlo a TikTok")
    parser.add_argument("--dry-run-publish", action="store_true", help="Preparar la publicación en TikTok (subir, copy, IA) sin dar clic final en Publicar")
    parser.add_argument("--publish", action="store_true", default=True, help="Publicar automáticamente el video en TikTok (por defecto: activado)")
    parser.add_argument("--model", "-m", type=str, default=None, help="Modelo de Opencode Go a usar (ej: haiku, deepseek, kimi, minimax)")
    parser.add_argument("-ft", "--free-theme", "--theme", type=str, default=None, help="Tema libre o premisa opcional sugerida para el episodio")
    parser.add_argument("--scenes", "-s", "--tomas", type=str, default=None, help="Tomas o escenas específicas a generar separadas por comas (ej: '1,2' o '2' o '1'). Por defecto: todas (1,2,3).")
    parser.add_argument("--file", "--episode-file", "-f", type=str, default=None, help="Ruta a un archivo JSON con la historia completa (ej: 'sugar_cube_episode.json'). Evita llamar a la IA.")
    parser.add_argument("--resume", "--reuse-last", action="store_true", help="Reutiliza la última historia guardada en caché (last_episode_<arquetipo>.json).")
    parser.add_argument("--no-assemble", "--skip-assemble", action="store_true", help="Solo generar los clips en Flow sin ensamblarlos en la línea de tiempo ni exportar.")

    args = parser.parse_args()

    if args.list:
        available = ArchetypeRegistry.get_available_archetypes()
        print("\n" + "=" * 65)
        print("🎭 ARQUETIPOS DISPONIBLES:")
        print("=" * 65)
        for k, v in available.items():
            print(f"  • -a {k:12} ({v})")
        print("=" * 65 + "\n")
        sys.exit(0)

    try:
        archetype_cfg = ArchetypeRegistry.get_archetype_config(args.archetype)
    except ValueError as e:
        print("\n" + "=" * 70)
        print(str(e))
        print("=" * 70 + "\n")
        sys.exit(1)

    # Detección inteligente de modelo si se pone al final (ej: 'random kimi' o solo 'kimi')
    known_models = ["kimi", "haiku", "claude", "deepseek", "minimax", "kimi-code"]
    selected_model = args.model or args.model_arg
    city_arg = args.city

    if city_arg and city_arg.lower() in known_models and not selected_model:
        selected_model = city_arg
        city_arg = "random"

    preferred = None if (not city_arg or city_arg.lower() in ["random", "--random", "-r", "azar", "aleatorio"]) else city_arg

    # Por defecto, la publicación en TikTok está ACTIVADA automáticamente
    publish_flag = not args.no_publish
    dry_run_flag = args.dry_run_publish
    scenes_filter_list = parse_scenes_arg(args.scenes)

    print(f"\n🚀 Iniciando pipeline autónomo...")
    print(f"🎭 Arquetipo seleccionado: {archetype_cfg['display_name']} ({archetype_cfg['key']})")
    print(f"📍 Destino/Entorno: {preferred or 'Al azar con IA'}")
    if args.free_theme:
        print(f"🎯 Tema libre sugerido (-ft): '{args.free_theme}'")
    if selected_model:
        print(f"🧠 Modelo de IA seleccionado: {selected_model}")
    if scenes_filter_list:
        print(f"🎬 Filtro de tomas activo (--scenes): Solo se generarán {scenes_filter_list} (omitiendo el resto)")
    if args.resume:
        print("🔄 Reanudando última historia guardada en caché (--resume)")
    elif args.file:
        print(f"📄 Usando archivo de historia especificado: {args.file}")
    if args.no_assemble:
        print("🎬 Ensamble: DESACTIVADO (--no-assemble)")
    if publish_flag and not args.no_assemble:
        print(f"📱 Publicación TikTok: {'DRY-RUN (sin clic final)' if dry_run_flag else 'PUBLICACIÓN AUTOMÁTICA ACTIVA 🚀'}")
    else:
        print("📱 Publicación TikTok: DESACTIVADA (--no-publish / --no-assemble)")

    asyncio.run(run_full_pipeline(
        episode_input=preferred,
        publish_tiktok=publish_flag,
        tiktok_dry_run=dry_run_flag,
        model=selected_model,
        archetype=archetype_cfg["key"],
        free_theme=args.free_theme,
        scenes_filter=scenes_filter_list,
        episode_file=args.file,
        resume_last=args.resume,
        no_assemble=args.no_assemble,
    ))
