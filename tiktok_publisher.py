"""Módulo de automatización para subir y publicar videos directamente en TikTok Studio
a través de Chrome DevTools Protocol (CDP) y Playwright.
"""

import argparse
import asyncio
import logging
import os
import sys
from pathlib import Path
from typing import Optional, List, Dict, Any

# Asegurar que las conexiones locales CDP no se vean afectadas por variables de proxy
os.environ["no_proxy"] = "localhost,127.0.0.1"
os.environ["NO_PROXY"] = "localhost,127.0.0.1"

from playwright.async_api import async_playwright, Browser, BrowserContext, Page

from config import CDP_URL

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("TikTokPublisher")

TIKTOK_UPLOAD_URL = "https://www.tiktok.com/tiktokstudio/upload?from=creator_center&tab=video"


class TikTokPublisher:
    """Controlador autónomo para TikTok Studio conectado a la sesión activa del usuario."""

    def __init__(self, cdp_url: str = CDP_URL):
        self.cdp_url = cdp_url
        self.playwright = None
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None

    async def connect(self) -> bool:
        """Conecta con el navegador en ejecución vía CDP."""
        logger.info(f"Conectando a {self.cdp_url} vía CDP...")
        try:
            self.playwright = await async_playwright().start()
            self.browser = await self.playwright.chromium.connect_over_cdp(self.cdp_url)

            if not self.browser.contexts:
                logger.error("No se encontró ningún contexto en el navegador.")
                return False

            self.context = self.browser.contexts[0]
            logger.info("✅ Conexión establecida con el navegador.")
            return True
        except Exception as e:
            logger.error(f"Error conectando al navegador vía CDP: {e}")
            logger.info("Asegúrate de que Brave esté abierto con ./launch_browser.sh")
            return False

    async def get_or_open_upload_page(self, force_reset: bool = True) -> Optional[Page]:
        """Busca una pestaña activa con TikTok Studio y asegura que inicie en la pantalla inicial de subida."""
        if not self.context:
            raise RuntimeError("Navegador no inicializado. Llama a connect() primero.")

        # Buscar pestaña existente de TikTok
        target_page = None
        for p in self.context.pages:
            url = p.url
            if "tiktokstudio" in url or "tiktok.com" in url:
                target_page = p
                break

        if target_page:
            self.page = target_page
            await self.page.bring_to_front()

            # Si se solicita reinicio o si la pestaña quedó en /content (publicaciones) o fuera de la pantalla de subida inicial
            clean_url = self.page.url.split("#")[0]
            if force_reset or "/content" in clean_url or "upload" not in clean_url or "creator_center" not in clean_url:
                logger.info(f"🔄 Restableciendo pestaña de TikTok a la pantalla inicial de subida ({TIKTOK_UPLOAD_URL})...")
                await self.page.goto(TIKTOK_UPLOAD_URL, wait_until="domcontentloaded")
                await self.page.wait_for_timeout(3000)
            else:
                logger.info(f"Pestaña de TikTok Studio lista en pantalla de subida: {self.page.url}")

            return self.page

        # Si no existe, abrir en pestaña en blanco o nueva pestaña
        logger.info(f"Abriendo TikTok Studio Upload ({TIKTOK_UPLOAD_URL})...")
        if self.context.pages and self.context.pages[0].url in ("about:blank", "chrome://newtab/"):
            self.page = self.context.pages[0]
            await self.page.goto(TIKTOK_UPLOAD_URL, wait_until="domcontentloaded")
        else:
            self.page = await self.context.new_page()
            await self.page.goto(TIKTOK_UPLOAD_URL, wait_until="domcontentloaded")

        await self.page.bring_to_front()
        await self.page.wait_for_timeout(3000)
        return self.page

    async def upload_video(self, video_path: Path | str, timeout_seconds: int = 120) -> bool:
        """Sube un video usando el input[type=file] para evitar el diálogo GTK del sistema operativo."""
        if not self.page:
            await self.get_or_open_upload_page()

        path_obj = Path(video_path).resolve()
        if not path_obj.exists():
            logger.error(f"El archivo de video no existe: {path_obj}")
            return False

        logger.info(f"Preparando subida de: {path_obj.name} ({path_obj.stat().st_size / (1024*1024):.2f} MB)")

        # Comprobar si ya estamos en la pantalla de detalles (hay un video cargado previamente)
        replace_btn = self.page.locator('button:has-text("Sustituir"), button:has-text("Reemplazar")').first
        desc_el = self.page.locator('div[contenteditable="true"]').first

        if await replace_btn.count() > 0 and await replace_btn.is_visible() and await desc_el.count() > 0:
            body_text = await self.page.evaluate("() => document.body ? document.body.innerText : ''")
            if path_obj.name in body_text or "_30s" in body_text:
                logger.info(f"✅ Video activo detectado en TikTok Studio. Reutilizando carga activa...")
                return True
            else:
                logger.info("Video distinto detectado. Usando 'Sustituir'...")
                async with self.page.expect_file_chooser() as fc_info:
                    await replace_btn.click()
                file_chooser = await fc_info.value
                await file_chooser.set_files(str(path_obj))
        else:
            # Localizar el input de archivo en la pantalla inicial de subida
            file_input = self.page.locator('input[type="file"]').first
            if await file_input.count() == 0:
                logger.error("No se encontró el elemento input[type='file'] en TikTok Studio.")
                return False

            logger.info("Adjuntando archivo directamente vía CDP (sin abrir el explorador de archivos)...")
            await file_input.set_input_files(str(path_obj))

        # Esperar a que la subida se procese y aparezca el indicador de "Cargado" o el formulario de detalles
        logger.info("Esperando a que TikTok procese la subida del video...")
        start_time = asyncio.get_event_loop().time()

        while asyncio.get_event_loop().time() - start_time < timeout_seconds:
            # Comprobar si el texto 'Cargado' está presente
            cargado_el = self.page.locator('text=Cargado').first
            has_cargado = await cargado_el.count() > 0

            # Comprobar si el editor de descripción ya está visible
            desc_el = self.page.locator('div[contenteditable="true"]').first
            has_desc = await desc_el.count() > 0 and await desc_el.is_visible()

            if has_cargado or has_desc:
                logger.info("✅ ¡Video subido y procesado con éxito por TikTok Studio!")
                await self.page.wait_for_timeout(2000)
                return True

            await self.page.wait_for_timeout(2000)

        logger.error(f"Tiempo de espera agotado ({timeout_seconds}s) para la subida del video.")
        return False

    async def set_description(self, caption: str, hashtags: Optional[List[str]] = None) -> bool:
        """Introduce el texto de descripción y hashtags en el editor Draft.js de TikTok."""
        if not self.page:
            return False

        logger.info("Configurando descripción y hashtags...")

        # Formatear el texto completo
        formatted_tags = []
        if hashtags:
            for tag in hashtags:
                clean_tag = tag.strip()
                if clean_tag:
                    if not clean_tag.startswith("#"):
                        clean_tag = f"#{clean_tag}"
                    formatted_tags.append(clean_tag)

        tags_str = " ".join(formatted_tags)
        full_text = f"{caption}\n\n{tags_str}".strip() if tags_str else caption

        logger.info(f"Texto a insertar ({len(full_text)} caracteres):\n{full_text}")

        # Localizar el editor de texto enriquecido (Draft.js)
        desc_el = self.page.locator('div[contenteditable="true"]').first
        if await desc_el.count() == 0:
            logger.error("No se encontró el editor de descripción (contenteditable).")
            return False

        await desc_el.click()
        await self.page.wait_for_timeout(400)

        # Seleccionar todo el contenido existente y borrarlo
        await self.page.keyboard.press("Control+A")
        await self.page.wait_for_timeout(200)
        await self.page.keyboard.press("Backspace")
        await self.page.wait_for_timeout(200)

        # Insertar el nuevo texto
        await self.page.keyboard.insert_text(full_text)
        await self.page.wait_for_timeout(1000)

        # Cerrar el menú flotante de autocompletado de hashtags
        await self.page.keyboard.press("Escape")
        await self.page.wait_for_timeout(300)

        # Verificar contador de caracteres
        counter_el = self.page.locator('text=/4000').first
        if await counter_el.count() > 0:
            counter_text = await counter_el.inner_text()
            logger.info(f"✅ Descripción actualizada. Contador de caracteres: {counter_text}")

        return True

    async def enable_ai_content_label(self) -> bool:
        """Despliega los ajustes avanzados y activa el interruptor de 'Contenido generado por IA'."""
        if not self.page:
            return False

        logger.info("Verificando sección de 'Contenido generado por IA'...")

        # 1. Comprobar si 'Mostrar más' está presente y necesita desplegarse
        mostrar_mas = self.page.locator('text="Mostrar más"').first
        if await mostrar_mas.count() > 0 and await mostrar_mas.is_visible():
            logger.info("Haciendo clic en 'Mostrar más ⌄' para desplegar ajustes avanzados...")
            await mostrar_mas.click()
            await self.page.wait_for_timeout(1000)

        # 2. Localizar el contenedor de Contenido generado por IA
        aigc_container = self.page.locator('[data-e2e="aigc_container"]').first
        if await aigc_container.count() == 0:
            # Búsqueda alternativa por texto
            aigc_label = self.page.locator('text="Contenido generado por IA"').first
            if await aigc_label.count() > 0:
                logger.info("Localizado contenedor AIGC por texto...")
                aigc_container = aigc_label.locator("xpath=ancestor::div[contains(@class, 'container')][1]")

        if await aigc_container.count() == 0:
            logger.warning("No se pudo localizar el contenedor de 'Contenido generado por IA'.")
            return False

        # 3. Comprobar el estado actual del switch
        switch_content = aigc_container.locator('.Switch__content, [data-layout="switch-root"]').first
        switch_input = aigc_container.locator('input[role="switch"]').first

        is_checked = False
        if await switch_input.count() > 0:
            is_checked = await switch_input.is_checked()
        elif await switch_content.count() > 0:
            aria_checked = await switch_content.get_attribute("aria-checked")
            is_checked = aria_checked == "true"

        if is_checked:
            logger.info("✅ El interruptor de 'Contenido generado por IA' ya está ACTIVADO.")
            return True

        logger.info("Activando interruptor de 'Contenido generado por IA'...")
        # Hacer clic en el elemento Switch__content (el contenedor visual que recibe el puntero)
        if await switch_content.count() > 0:
            await switch_content.click()
        elif await switch_input.count() > 0:
            await switch_input.click(force=True)

        await self.page.wait_for_timeout(1500)

        # Verificar nuevo estado
        if await switch_input.count() > 0:
            new_state = await switch_input.is_checked()
            if new_state:
                logger.info("✅ 'Contenido generado por IA' ACTIVADO con éxito.")
                return True

        logger.info("✅ Estado del interruptor actualizado.")
        return True

    async def publish(self, dry_run: bool = False) -> bool:
        """Hace clic en el botón 'Publicar' para subir el video a TikTok."""
        if not self.page:
            return False

        pub_btn = self.page.locator('button:has-text("Publicar")').first
        # 1. Asegurar verificación de etiqueta de IA activada
        await self.enable_ai_content_label()

        # 2. Hacer scroll down hacia el botón 'Publicar' para asegurar visibilidad en pantalla
        logger.info("Haciendo scroll down hacia el botón 'Publicar'...")
        await pub_btn.scroll_into_view_if_needed()
        await self.page.wait_for_timeout(1000)

        # Verificar si está habilitado
        aria_disabled = await pub_btn.get_attribute("aria-disabled")
        disabled_attr = await pub_btn.get_attribute("disabled")
        if aria_disabled == "true" or disabled_attr is not None:
            logger.warning("El botón 'Publicar' está temporalmente deshabilitado. Esperando 3 segundos...")
            await self.page.wait_for_timeout(3000)

        if dry_run:
            logger.info("🔍 MODO DRY-RUN: El video, la descripción, el scroll y la etiqueta de IA están completamente listos.")
            logger.info("   Botón 'Publicar' visible en pantalla. NO se hizo clic para permitir tu confirmación.")
            return True

        logger.info("🚀 Haciendo clic en el botón principal 'Publicar'...")
        await pub_btn.click()
        await self.page.wait_for_timeout(2000)

        # 3. Detectar y confirmar el diálogo modal emergente ("Publicar ahora" / "Publicar")
        logger.info("Comprobando si aparece ventana modal de confirmación ('Publicar ahora')...")
        for _ in range(5):
            confirm_modal_btn = self.page.locator(
                'div[role="dialog"] button:has-text("Publicar ahora"), '
                'div[role="dialog"] button:has-text("Publicar"), '
                '.TUXModal button:has-text("Publicar ahora"), '
                '.TUXModal button:has-text("Publicar"), '
                '.modal button:has-text("Publicar ahora"), '
                'button:has-text("Publicar ahora"), '
                'button:has-text("Publicar de todos modos"), '
                'button:has-text("Post now")'
            ).first

            if await confirm_modal_btn.count() > 0 and await confirm_modal_btn.is_visible():
                logger.info("👉 ¡Ventana emergente detectada! Haciendo clic en 'Publicar ahora'...")
                await confirm_modal_btn.click()
                await self.page.wait_for_timeout(2000)
                break
            await self.page.wait_for_timeout(1000)

        # 4. Esperar hasta 60 segundos a que TikTok procese la subida y confirme la publicación
        logger.info("Esperando confirmación de publicación de TikTok (redirección a /content)...")
        published = False
        start_wait = asyncio.get_event_loop().time()

        while asyncio.get_event_loop().time() - start_wait < 60:
            current_url = self.page.url
            if "/content" in current_url:
                logger.info(f"🎉 ¡VIDEO PUBLICADO CON ÉXITO EN TIKTOK! (Redirección confirmada a {current_url})")
                published = True
                break

            # Si el modal "Publicar ahora" aparece con retraso durante la espera, confirmarlo
            confirm_modal_btn = self.page.locator(
                'div[role="dialog"] button:has-text("Publicar ahora"), '
                'button:has-text("Publicar ahora"), '
                '.TUXModal button:has-text("Publicar ahora")'
            ).first
            if await confirm_modal_btn.count() > 0 and await confirm_modal_btn.is_visible():
                logger.info("👉 Ventana emergente 'Publicar ahora' detectada en espera. Haciendo clic...")
                await confirm_modal_btn.click()
                await self.page.wait_for_timeout(2000)

            body_text = await self.page.evaluate("() => document.body ? document.body.innerText : ''")
            if any(k in body_text.lower() for k in ["se ha publicado", "publicado con éxito", "gestionar tus publicaciones"]):
                logger.info("🎉 ¡VIDEO PUBLICADO CON ÉXITO EN TIKTOK! (Mensaje de éxito detectado)")
                published = True
                break

            await self.page.wait_for_timeout(2000)

        if published:
            # Esperar 3 segundos para que TikTok asiente la publicación en su base de datos
            await self.page.wait_for_timeout(3000)
            # Restablecer la pestaña a la pantalla inicial de subida
            logger.info(f"🔄 Restableciendo la pestaña de TikTok a la pantalla inicial de subida ({TIKTOK_UPLOAD_URL})...")
            await self.page.goto(TIKTOK_UPLOAD_URL, wait_until="domcontentloaded")
            await self.page.wait_for_timeout(2000)
            return True
        else:
            logger.error("No se confirmó la publicación tras 60 segundos. No se forzó la navegación para evitar cancelar subidas en curso.")
            return False

    async def publish_video_pipeline(
        self,
        video_path: Path | str,
        caption: str,
        hashtags: Optional[List[str]] = None,
        dry_run: bool = False,
    ) -> bool:
        """Ejecuta el flujo completo de publicación en TikTok Studio."""
        print("\n" + "=" * 65)
        print("📱 INICIANDO PUBLICACIÓN EN TIKTOK STUDIO")
        print("=" * 65)
        print(f"📁 Video: {video_path}")
        print(f"📝 Caption: {caption}")
        print(f"🏷️ Hashtags: {hashtags}")
        print(f"🛡️ Modo Dry-Run: {dry_run}")
        print("=" * 65 + "\n")

        # 1. Conectar al navegador
        if not await self.connect():
            return False

        # 2. Localizar o abrir la pestaña de subida
        await self.get_or_open_upload_page()

        # 3. Subir el archivo de video
        if not await self.upload_video(video_path):
            logger.error("Fallo durante la subida del video.")
            return False

        # 4. Asignar descripción y hashtags
        if not await self.set_description(caption, hashtags):
            logger.error("Fallo al configurar la descripción.")
            return False

        # 5. Activar etiqueta de Contenido generado por IA
        if not await self.enable_ai_content_label():
            logger.warning("No se pudo confirmar la etiqueta de IA, continuando...")

        # 6. Publicar
        success = await self.publish(dry_run=dry_run)

        # Cerrar conexión CDP (mantiene el navegador del usuario abierto)
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()

        return success


async def main():
    parser = argparse.ArgumentParser(description="Publicador autónomo en TikTok Studio")
    parser.add_argument("--video", "-v", type=str, help="Ruta al archivo .mp4 a subir")
    parser.add_argument("--caption", "-c", type=str, default="¡Nueva aventura épica en vertical! 🚀🎬", help="Descripción del video")
    parser.add_argument("--hashtags", "-t", nargs="+", default=["ia", "googleflow", "cine", "viral", "video"], help="Lista de hashtags")
    parser.add_argument("--dry-run", action="store_true", help="Carga el video, rellena los datos y activa IA pero NO hace clic en Publicar")
    parser.add_argument("--publish", action="store_true", help="Publica definitivamente el video")

    args = parser.parse_args()

    # Si no se pasó video, buscar el más reciente en output_videos
    video_to_publish = args.video
    if not video_to_publish:
        output_dir = Path("output_videos")
        mp4_files = sorted(output_dir.glob("*.mp4"), key=lambda f: f.stat().st_mtime, reverse=True)
        if mp4_files:
            video_to_publish = str(mp4_files[0])
            logger.info(f"No se especificó video. Seleccionado el más reciente: {video_to_publish}")
        else:
            logger.error("No se encontró ningún archivo .mp4 en output_videos/.")
            sys.exit(1)

    # Por defecto, si no se especifica --publish, ejecutamos en dry_run por seguridad a menos que se indique explícitamente
    is_dry_run = args.dry_run or (not args.publish)

    publisher = TikTokPublisher()
    await publisher.publish_video_pipeline(
        video_path=video_to_publish,
        caption=args.caption,
        hashtags=args.hashtags,
        dry_run=is_dry_run,
    )


if __name__ == "__main__":
    asyncio.run(main())
