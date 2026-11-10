"""Cliente de automatización para Google Flow vía Chrome DevTools Protocol (CDP)."""

import asyncio
import logging
import os
import re
from pathlib import Path
from typing import Optional, List, Dict, Any

# Asegurar que la conexión CDP local no pase por proxies de entorno
os.environ["no_proxy"] = "localhost,127.0.0.1"
os.environ["NO_PROXY"] = "localhost,127.0.0.1"

from playwright.async_api import async_playwright, Browser, BrowserContext, Page

from config import CDP_URL, FLOW_URL, FLOW_PROJECT_URL, OUTPUT_DIR

def get_base_project_url(url: str) -> Optional[str]:
    """Extrae la URL base del proyecto de Google Flow (soporta cuentas /u/0/, /u/1/, etc.)."""
    if not url:
        return None
    clean = url.split("?")[0].rstrip("/")
    m = re.match(r"(https?://flow\.google\.com(?:/u/\d+)?/project/[a-zA-Z0-9_-]+)", clean)
    if m:
        return m.group(1)
    return None

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("FlowClient")

class FlowClient:
    """Controlador de Google Flow conectándose a una sesión real de Chrome/Brave."""

    def __init__(self, cdp_url: str = CDP_URL):
        self.cdp_url = cdp_url
        self.playwright = None
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None

    async def connect(self) -> bool:
        """Conecta con el navegador existente a través del puerto CDP."""
        logger.info(f"Conectando a {self.cdp_url} vía CDP...")
        try:
            self.playwright = await async_playwright().start()
            self.browser = await self.playwright.chromium.connect_over_cdp(self.cdp_url)
            
            if not self.browser.contexts:
                logger.error("No se encontró ningún contexto en el navegador conectado.")
                return False

            self.context = self.browser.contexts[0]
            logger.info("✅ Conexión establecida con el navegador.")
            return True
        except Exception as e:
            logger.error(f"Error conectando al navegador: {e}")
            logger.info("Asegúrate de que Brave o Chrome esté iniciado con ./launch_browser.sh")
            return False

    async def get_or_open_flow_page(self) -> Page:
        """Busca una pestaña activa con Google Flow o abre una nueva."""
        if not self.context:
            raise RuntimeError("Browser context no inicializado. Llama a connect() primero.")

        # Buscar pestaña activa de flow (priorizando la que tenga un proyecto abierto)
        target_page = None
        for p in self.context.pages:
            url = p.url
            if ("flow.google.com" in url or "labs.google" in url) and "/project/" in url and "/character" not in url:
                target_page = p
                break

        if not target_page:
            for p in self.context.pages:
                url = p.url
                if "flow.google.com" in url or "labs.google" in url:
                    if "/character" not in url:
                        target_page = p
                        break
                    elif not target_page:
                        target_page = p

        if target_page:
            self.page = target_page
            await self.page.bring_to_front()
            detected_project = get_base_project_url(target_page.url)
            proj_url = detected_project or FLOW_PROJECT_URL
            clean_url = target_page.url.split("?")[0].rstrip("/")
            clean_target = proj_url.split("?")[0].rstrip("/")
            if clean_url != clean_target or "/scene/" in target_page.url or "/character" in target_page.url:
                logger.info(f"🔄 Restableciendo pestaña de Flow a la página principal del proyecto ({proj_url})...")
                await target_page.goto(proj_url, wait_until="domcontentloaded")
                await target_page.wait_for_timeout(3000)
            else:
                logger.info(f"Pestaña de Flow lista en la página principal: {target_page.url}")
            return self.page

        # Si no existe, usar la página actual o crear una nueva
        logger.info(f"Abriendo Google Flow ({FLOW_URL})...")
        if self.context.pages and self.context.pages[0].url in ("about:blank", "chrome://newtab/"):
            self.page = self.context.pages[0]
            await self.page.goto(FLOW_URL, wait_until="networkidle")
        else:
            self.page = await self.context.new_page()
            await self.page.goto(FLOW_URL, wait_until="networkidle")

        return self.page

    async def check_session_status(self) -> Dict[str, Any]:
        """Comprueba si el usuario tiene sesión activa en Flow y los créditos disponibles."""
        if not self.page:
            await self.get_or_open_flow_page()

        await self.page.wait_for_timeout(2000)
        current_url = self.page.url
        title = await self.page.title()

        # Comprobar indicadores de login
        is_logged_in = "accounts.google.com" not in current_url
        
        # Buscar texto de créditos o elementos relevantes en el DOM
        body_text = await self.page.evaluate("() => document.body ? document.body.innerText : ''")
        has_credits = "créditos" in body_text.lower() or "credits" in body_text.lower()

        return {
            "url": current_url,
            "title": title,
            "is_logged_in": is_logged_in,
            "body_snippet": body_text[:300].strip().replace("\n", " "),
            "has_credits_text": has_credits
        }

    async def get_dom_structure(self) -> Dict[str, Any]:
        """Inspecciona los elementos clave de la interfaz de Flow (inputs, botones, áreas de texto)."""
        if not self.page:
            await self.get_or_open_flow_page()

        script = """
        () => {
            const inputs = Array.from(document.querySelectorAll('input, textarea, [contenteditable="true"], [role="textbox"]')).map(el => ({
                tag: el.tagName.toLowerCase(),
                role: el.getAttribute('role'),
                contenteditable: el.getAttribute('contenteditable'),
                aria_label: el.getAttribute('aria-label'),
                placeholder: el.getAttribute('placeholder'),
                id: el.id,
                className: el.className
            }));

            const buttons = Array.from(document.querySelectorAll('button, [role="button"]')).map(el => ({
                text: el.innerText.trim().slice(0, 50),
                aria_label: el.getAttribute('aria-label'),
                role: el.getAttribute('role'),
                disabled: el.disabled
            })).filter(b => b.text || b.aria_label);

            const videos = Array.from(document.querySelectorAll('video')).map(v => ({
                src: v.src,
                currentSrc: v.currentSrc,
                duration: v.duration
            }));

            return { inputs, buttons: buttons.slice(0, 20), videos_count: videos.length };
        }
        """
        return await self.page.evaluate(script)

    async def configure_generation_settings(self, aspect_ratio="9:16", model="Omni 1.1 Flash", resolution="720p", duration="10 s", outputs="x1") -> bool:
        """Configura el popup de opciones de generación según la interfaz real de Flow."""
        if not self.page:
            await self.get_or_open_flow_page()

        logger.info("Comprobando botón de configuración en Flow...")
        
        # El botón de configuración muestra el texto del estado actual (ej: 'Video · 720p · 10 s\ncrop_9_16\nx1')
        settings_trigger = self.page.locator('button[aria-label*="Botón de configuración" i]').first
        if await settings_trigger.count() > 0 and await settings_trigger.is_visible():
            current_text = await settings_trigger.inner_text()
            # Si ya tiene la configuración correcta, no es necesario reabrir el menú
            if "720p" in current_text and "10" in current_text and "x1" in current_text:
                logger.info(f"Opciones ya configuradas correctamente en Flow: {repr(current_text.strip())}")
                return True

            # Si requiere cambio, abrir el panel
            await settings_trigger.click()
            await self.page.wait_for_timeout(500)

        # Seleccionar las opciones deseadas dentro del overlay
        overlay = self.page.locator('.cdk-overlay-container, .flow-menu-panel').first

        video_tab = overlay.locator('button:has-text("Vídeo"), button:has-text("Video")').first
        if await video_tab.count() > 0 and await video_tab.is_visible():
            await video_tab.click()

        ingredientes_btn = overlay.locator('button:has-text("Ingredientes")').first
        if await ingredientes_btn.count() > 0 and await ingredientes_btn.is_visible():
            await ingredientes_btn.click()

        aspect_btn = overlay.locator(f'button:has-text("{aspect_ratio}")').first
        if await aspect_btn.count() > 0 and await aspect_btn.is_visible():
            await aspect_btn.click()

        res_btn = overlay.locator(f'button:has-text("{resolution}")').first
        if await res_btn.count() > 0 and await res_btn.is_visible():
            await res_btn.click()

        dur_btn = overlay.locator(f'button:has-text("{duration}")').first
        if await dur_btn.count() > 0 and await dur_btn.is_visible():
            await dur_btn.click()

        out_btn = overlay.locator(f'button:has-text("{outputs}")').first
        if await out_btn.count() > 0 and await out_btn.is_visible():
            await out_btn.click()

        # Cerrar el panel de configuración con Escape para no tapar otros elementos
        await self.page.keyboard.press("Escape")
        await self.page.wait_for_timeout(300)
        return True

    async def select_character_ingredient(self, character_name: str = "character 1") -> bool:
        """Pulsa el botón '+' (Agregar ingredientes) y selecciona el personaje existente en el proyecto."""
        if not self.page:
            await self.get_or_open_flow_page()

        logger.info(f"Añadiendo personaje '{character_name}' como ingrediente...")

        # Verificar si ya existe el chip del ingrediente en la barra
        ingredient_chip = self.page.locator('.reference-ingredient-chip, .prompt-ingredient-bar').first
        if await ingredient_chip.count() > 0 and await ingredient_chip.is_visible():
            logger.info("El ingrediente del personaje ya está presente en el cuadro de instrucción.")
            return True

        # 1. Buscar y pulsar el botón '+' con aria-label 'Agregar ingredientes al cuadro de instrucción'
        add_btn = self.page.locator('button[aria-label*="Agregar ingredientes al cuadro de instrucción" i]').first
        if await add_btn.count() > 0 and await add_btn.is_visible():
            await add_btn.click()
            await self.page.wait_for_timeout(600)
            logger.info("Botón '+' (Agregar ingredientes) presionado.")

        # 2. En el menú emergente (.cdk-overlay-container), hacer clic en 'Personajes'
        pers_item = self.page.locator('.cdk-overlay-container mat-list-item:has-text("Personajes")').first
        if await pers_item.count() > 0 and await pers_item.is_visible():
            await pers_item.click()
            await self.page.wait_for_timeout(600)
            logger.info("Categoría 'Personajes' seleccionada en el menú.")

        # 3. Localizar y seleccionar la tarjeta del personaje
        char_card = self.page.locator('.cdk-overlay-container').locator(f'text={character_name}').last
        if await char_card.count() > 0:
            await char_card.click()
            logger.info(f"✅ Personaje '{character_name}' seleccionado con éxito.")
            await self.page.wait_for_timeout(500)
            return True
        else:
            logger.warning(f"No se encontró directamente '{character_name}', seleccionando primera tarjeta de personaje...")
            first_card = self.page.locator('.cdk-overlay-container .media-tile, .cdk-overlay-container img').first
            if await first_card.count() > 0:
                await first_card.click()
                logger.info("✅ Tarjeta de personaje seleccionada.")
                await self.page.wait_for_timeout(500)
                return True
            return False

    async def inject_prompt(self, prompt_text: str) -> bool:
        """Introduce el prompt en el área de texto ProseMirror de Flow de forma nativa."""
        if not self.page:
            await self.get_or_open_flow_page()

        logger.info("Localizando área de entrada del prompt en Flow...")

        # En Flow es un div con clase 'ProseMirror' y aria-label '¿Qué quieres crear?'
        target_el = self.page.locator('div.ProseMirror, div[aria-label="¿Qué quieres crear?"]').first
        if await target_el.count() == 0 or not await target_el.is_visible():
            logger.error("No se pudo localizar el campo de entrada de prompt en Flow.")
            return False

        # Enfocar, limpiar texto anterior e insertar el nuevo prompt
        await target_el.click()
        await self.page.wait_for_timeout(200)

        # Seleccionar todo el contenido existente y reemplazarlo
        await self.page.keyboard.press("Control+A")
        await self.page.keyboard.press("Backspace")
        await self.page.wait_for_timeout(200)

        # Inyectar texto vía portapapeles o inserción directa
        await self.page.evaluate("""
            ({text}) => {
                const el = document.querySelector('div.ProseMirror, div[aria-label="¿Qué quieres crear?"]');
                if (el) {
                    el.focus();
                    document.execCommand('insertText', false, text);
                    el.dispatchEvent(new Event('input', { bubbles: true }));
                }
            }
        """, {"text": prompt_text})
        await self.page.wait_for_timeout(400)

        logger.info("Prompt inyectado exitosamente en el editor de Flow.")
        return True

    async def submit_prompt(self) -> bool:
        """Pulsa el botón de generación 'Iniciar generación'."""
        if not self.page:
            return False

        gen_btn = self.page.locator('button[aria-label*="Iniciar generación" i]').first
        if await gen_btn.count() > 0 and await gen_btn.is_visible():
            logger.info("Pulsando botón 'Iniciar generación'...")
            await gen_btn.click()
            await self.page.wait_for_timeout(1000)
            return True

        # Alternativa: Enter
        logger.info("Pulsando Enter en el editor de Flow...")
        await self.page.keyboard.press("Enter")
        return True

    async def wait_for_video_generation(self, timeout_sec: int = 180) -> bool:
        """Espera a que el video termine de renderizarse en Flow."""
        if not self.page:
            return False

        logger.info("Esperando a que termine el renderizado del clip en Flow...")
        start_time = asyncio.get_event_loop().time()
        while asyncio.get_event_loop().time() - start_time < timeout_sec:
            # Comprobar si hay indicadores de carga ('Generando', spinners, o si el botón de generar vuelve a estar listo)
            is_generating = await self.page.evaluate('''() => {
                const text = document.body ? document.body.innerText.toLowerCase() : '';
                return text.includes('generando') || text.includes('renderiz') || document.querySelector('.generating-indicator') !== null;
            }''')
            if not is_generating:
                logger.info("✅ Renderizado completado.")
                return True
            await asyncio.sleep(5)

        logger.warning("Tiempo de espera agotado esperando el renderizado.")
        return False

    async def open_or_create_scene(self) -> bool:
        """Abre la vista de Escenas y entra al editor de la escena del proyecto."""
        if not self.page:
            await self.get_or_open_flow_page()

        logger.info("Accediendo a la sección de 'Escenas'...")
        # Si ya estamos en /scene/
        if "/scene/" in self.page.url:
            return True

        # Click en Escenas en la barra lateral
        escenas_nav = self.page.locator('button:has-text("Escenas")').first
        if await escenas_nav.count() > 0 and await escenas_nav.is_visible():
            await escenas_nav.click()
            await self.page.wait_for_timeout(1000)

        # Entrar al primer FLOW-SCENE-TILE existente
        scene_tile = self.page.locator('flow-scene-tile').first
        if await scene_tile.count() > 0:
            logger.info("Abriendo escena existente...")
            await scene_tile.click()
            await self.page.wait_for_timeout(1500)
            return True
        return False

    async def append_clip_to_scene(self, clip_index: int = 0) -> bool:
        """En el editor de escena, hace clic en '+' (Agregar clip) y selecciona el clip generado."""
        if not self.page:
            return False

        logger.info("Añadiendo clip a la línea de tiempo de la escena...")
        add_clip_btn = self.page.locator('button[aria-label="Agregar clip"]').first
        if await add_clip_btn.count() == 0:
            logger.error("No se encontró el botón 'Agregar clip' en la línea de tiempo.")
            return False

        await add_clip_btn.click()
        await self.page.wait_for_timeout(600)

        # En el menú desplegable, pulsar 'Agregar clip'
        menu_add = self.page.locator('.cdk-overlay-container button:has-text("Agregar clip")').first
        if await menu_add.count() > 0:
            await menu_add.click()
            await self.page.wait_for_timeout(1000)

        # En el modal de selección de contenido multimedia, seleccionar el clip
        dialog = self.page.locator('flow-media-picker-dialog, mat-dialog-container').first
        if await dialog.count() > 0:
            # Seleccionar la pestaña de Videos si está disponible
            videos_tab = dialog.locator('mat-list-item:has-text("Videos")').first
            if await videos_tab.count() > 0:
                await videos_tab.click()
                await self.page.wait_for_timeout(500)

            # Seleccionar el clip correspondiente
            tiles = dialog.locator('flow-video-tile, .media-tile, flow-grid-tile')
            if await tiles.count() > clip_index:
                await tiles.nth(clip_index).click()
                logger.info(f"✅ Clip index {clip_index} añadido a la escena.")
                await self.page.wait_for_timeout(1000)
                return True
        return False

    async def download_scene_video(self, download_dir: Path = OUTPUT_DIR) -> Optional[str]:
        """Hace clic en el botón 'Descargar contenido multimedia' dentro del editor de escenas y descarga en 720p."""
        if not self.page:
            return None

        logger.info("Localizando botón 'Descargar contenido multimedia' en el editor de escenas...")
        # Exactamente como en tu captura de pantalla: botón con icono download y aria-label 'Descargar contenido multimedia'
        download_btn = self.page.locator('button[aria-label*="Descargar contenido multimedia" i]').first
        if await download_btn.count() == 0:
            logger.error("No se encontró el botón de descarga en la escena.")
            return None

        # Configurar comportamiento de descarga nativo por CDP para evitar que se quede esperando la ventana del sistema
        try:
            cdp_session = await self.context.new_cdp_session(self.page)
            await cdp_session.send('Browser.setDownloadBehavior', {
                'behavior': 'allow',
                'downloadPath': str(download_dir),
                'events': True
            })
        except Exception as e:
            logger.warning(f"No se pudo forzar setDownloadBehavior: {e}")

        await download_btn.click()
        await self.page.wait_for_timeout(800)

        # Seleccionar la opción de resolución: '720p Tamaño original' (o '1080p')
        format_opt = self.page.locator('.cdk-overlay-container button:has-text("720p"), .cdk-overlay-container [role="menuitem"]:has-text("720p"), .cdk-overlay-container flow-menu-item:has-text("720p")').first
        if await format_opt.count() == 0:
            format_opt = self.page.locator('.cdk-overlay-container button').filter(has_not_text="Descartar").first

        try:
            async with self.page.expect_download(timeout=120000) as download_info:
                if await format_opt.count() > 0:
                    await format_opt.click()
                else:
                    await download_btn.click()
            download = await download_info.value
            target_path = download_dir / download.suggested_filename
            await download.save_as(str(target_path))
            logger.info(f"🎉 ¡VIDEO FINAL DE 30 SEGUNDOS DESCARGADO EN: {target_path}!")
            return str(target_path)
        except Exception as e:
            logger.warning(f"Descarga delegada directamente a Brave o completada: {e}")
            return None

    async def close(self):
        """Cierra la conexión con Playwright sin cerrar el navegador del usuario."""
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()
        logger.info("Conexión CDP cerrada.")

