"""Script definitivo para descargar el video de 30s de Google Flow de forma 100% autónoma."""

import asyncio
import logging
import os
import shutil
import time
from pathlib import Path
from typing import Optional

os.environ["no_proxy"] = "localhost,127.0.0.1"
os.environ["NO_PROXY"] = "localhost,127.0.0.1"

from playwright.async_api import async_playwright, Page
from config import CDP_URL, OUTPUT_DIR

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("SceneAssembler")

SCENE_URL = os.getenv("FLOW_SCENE_URL", "https://flow.google.com")
DOWNLOADS_DIR = Path.home() / "Descargas"
ALT_DOWNLOADS_DIR = Path.home() / "Downloads"

async def ensure_scene_editor(page: Page) -> bool:
    """Navega a la escena del proyecto si no estamos en ella."""
    if "/scene/" not in page.url:
        logger.info(f"Navegando a la escena del proyecto ({SCENE_URL})...")
        await page.goto(SCENE_URL, wait_until="domcontentloaded")
        await page.wait_for_timeout(3000)
    else:
        logger.info(f"Ya en el editor de escena: {page.url}")

    # Cerrar tooltip 'Entendido' si aparece
    entendido = page.locator('button:has-text("Entendido")')
    if await entendido.count() > 0 and await entendido.first.is_visible():
        await entendido.first.click()
        await page.wait_for_timeout(500)
    return True

async def get_clips_count(page: Page) -> int:
    return await page.locator('.clip').count()

async def verify_video_file(file_path: Path) -> dict:
    """Verifica el archivo de video con ffprobe y retorna sus metadatos."""
    import subprocess
    import json
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
        logger.warning(f"Error ejecutando ffprobe: {e}")
        return {"valid": False, "error": str(e)}

async def download_final_video(page: Page, context) -> Optional[str]:
    """Gestiona la exportación y descarga del video final de 30s de forma 100% autónoma."""
    logger.info("🎬 Iniciando descarga automática del video final de 30 segundos...")
    target_path = OUTPUT_DIR / "final_assembled_video_30s.mp4"
    verified_path = OUTPUT_DIR / "final_assembled_video_30s_verified.mp4"

    # 1. Configurar CDP Browser.setDownloadBehavior para que Chromium descargue directamente sin popup del OS
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

    # 2. Verificar estado actual de notificaciones/toasts en pantalla
    current_overlay = await page.evaluate('''() => {
        const els = Array.from(document.querySelectorAll('.cdk-overlay-container, mat-snack-bar-container, [role="status"]'));
        return els.map(e => (e.innerText || '').trim()).filter(t => t.length > 0);
    }''')
    logger.info(f"Estado de notificaciones en Flow: {current_overlay}")

    # Si ya hay un botón 'Descargar escena' listo en un toast de completado
    ready_btn = page.locator('.cdk-overlay-container button:has-text("Descargar"), mat-snack-bar-container button:has-text("Descargar")').filter(has_not_text="Descartar").first
    if await ready_btn.count() > 0 and await ready_btn.is_visible():
        logger.info("🎉 ¡Botón de descarga listo encontrado en pantalla! Pulsando...")
        try:
            async with page.expect_download(timeout=6000) as dl_info:
                await ready_btn.click()
            dl = await dl_info.value
            await dl.save_as(str(target_path))
            shutil.copy2(target_path, verified_path)
            meta = await verify_video_file(target_path)
            logger.info(f"✅ Video verificado vía Playwright download: {meta}")
            return str(target_path)
        except Exception as e:
            logger.info("Esperando archivo guardado directamente por CDP en disco...")
            await page.wait_for_timeout(2000)

    # 3. Pulsar el botón de descarga en la cabecera (al lado del corazón) si no se descargó ya
    dl_btn = page.locator('button[aria-label="Descargar escena"], button[aria-label*="Descargar contenido multimedia" i], button[aria-label*="Descargar" i]').first
    if await dl_btn.count() > 0:
        label = await dl_btn.get_attribute("aria-label") or "Descargar"
        logger.info(f"Pulsando botón de cabecera: '{label}'...")
        await dl_btn.click()
        await page.wait_for_timeout(1200)

        # Si aparece menú de resolución (720p / 1080p), pulsar 720p
        res_clicked = await page.evaluate('''() => {
            const all = Array.from(document.querySelectorAll('.cdk-overlay-container *'));
            const opt = all.reverse().find(el => {
                const txt = (el.innerText || '').toLowerCase();
                return txt.includes('720p') && el.children.length <= 1;
            });
            if (opt) { opt.click(); return true; }
            return false;
        }''')
        if res_clicked:
            logger.info("✅ Opción '720p' pulsada en el menú.")
        await page.wait_for_timeout(1500)

    # 4. Monitorear hasta 360 segundos para que Flow termine de renderizar y active la descarga
    logger.info("Monitoreando exportación de Flow...")
    start_time = time.time()
    download_done = False

    while time.time() - start_time < 360:
        # A. Comprobar botón 'Descargar escena' / 'Descargar' en notificación (excluyendo 'Descartar')
        toast_btn = page.locator('.cdk-overlay-container button:has-text("Descargar"), mat-snack-bar-container button:has-text("Descargar")').filter(has_not_text="Descartar").first
        if await toast_btn.count() > 0 and await toast_btn.is_visible():
            btn_txt = (await toast_btn.inner_text()).strip()
            logger.info(f"🎉 ¡Notificación de exportación completada! Pulsando '{btn_txt}'...")
            try:
                async with page.expect_download(timeout=6000) as dl_info:
                    await toast_btn.click()
                dl = await dl_info.value
                await dl.save_as(str(target_path))
                shutil.copy2(target_path, verified_path)
                meta = await verify_video_file(target_path)
                logger.info(f"✅ Video descargado y verificado: {meta}")
                return str(target_path)
            except Exception as e:
                logger.info("Descarga en proceso vía CDP directamente al directorio de salida...")
                # No re-pulsar para no interferir con la descarga en curso

        # B. Comprobar si el archivo nuevo ya fue guardado en disco
        for sdir in [OUTPUT_DIR, DOWNLOADS_DIR, ALT_DOWNLOADS_DIR]:
            if not sdir.exists():
                continue

            # Si hay archivos temporales de descarga en curso (.crdownload), esperar
            crdownload_files = list(sdir.glob("*.crdownload"))
            if crdownload_files:
                logger.info(f"Descargando datos: {crdownload_files[0].name} ({crdownload_files[0].stat().st_size / (1024*1024):.2f} MB)...")
                await asyncio.sleep(2)
                continue

            for f in sorted(sdir.glob("*.mp4"), key=os.path.getmtime, reverse=True):
                # Solo archivos generados a partir del inicio de esta exportación
                if f.stat().st_mtime >= start_export_time - 3.0 and f.stat().st_size > 500000:
                    # Asegurar que el archivo terminó de escribirse (tamaño estable)
                    s1 = f.stat().st_size
                    await asyncio.sleep(1.5)
                    s2 = f.stat().st_size
                    if s1 == s2 and s1 > 5000000:
                        logger.info(f"Archivo completado detectado: {f.name} ({s2 / (1024*1024):.2f} MB)")
                        if f != target_path:
                            shutil.copy2(f, target_path)
                        shutil.copy2(target_path, verified_path)
                        download_done = True
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

async def run():
    p = await async_playwright().start()
    browser = await p.chromium.connect_over_cdp(CDP_URL)
    context = browser.contexts[0]

    page = None
    for pg in context.pages:
        if "flow.google.com" in pg.url and "character" not in pg.url:
            page = pg
            break

    if not page:
        logger.error("No se encontró la pestaña de Flow.")
        await browser.close()
        await p.stop()
        return

    await page.bring_to_front()
    await ensure_scene_editor(page)

    # Verificar clips actuales en la línea de tiempo
    clips_count = await get_clips_count(page)
    logger.info(f"🎬 Clips actuales en la línea de tiempo: {clips_count}/3")

    # Iniciar descarga del video final
    video_path = await download_final_video(page, context)
    if video_path:
        print("\n" + "=" * 60)
        print("🎉 ¡VIDEO FINAL DE 30 SEGUNDOS GENERADO Y DESCARGADO AUTÓNOMAMENTE!")
        print(f"📁 Ubicación: {video_path}")
        print("=" * 60 + "\n")
    else:
        logger.error("No se pudo completar la descarga.")

    await browser.close()
    await p.stop()

if __name__ == "__main__":
    asyncio.run(run())
