# Guía de Configuración: Ejecución Autónoma 24/7 en Laptop Linux (Cron)

Esta guía detalla paso a paso cómo dejar tu laptop Linux ejecutando el pipeline autónomo **3 veces al día (7:00 AM, 3:00 PM y 11:00 PM)** con la **pantalla bloqueada** (e incluso con la tapa cerrada) sin que el sistema entre en suspensión.

---

## 1. Preparación Inicial del Entorno (Una sola vez)

Si acabas de clonar el repositorio en la laptop, asegúrate de copiar tus archivos privados (que no están en GitHub por seguridad) dentro de la carpeta del proyecto:
* `.env` *(en la raíz del proyecto)*
* `archetypes/cuy.json` *(dentro de la carpeta `archetypes/`)*
* `history_cuy.json` *(opcional, en la raíz del proyecto para conservar el historial de ciudades visitadas)*

Luego, instala las dependencias en la terminal:

```bash
# 1. Instalar ffmpeg (necesario para verificar los videos descargados)
sudo apt update && sudo apt install -y ffmpeg curl

# 2. Crear entorno virtual e instalar librerías
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium

# 3. Asegurar permisos de ejecución en los scripts
chmod +x launch_browser.sh run_daily.sh
```

---

## 2. Desactivar la Suspensión Automática (Mantener Viva con Pantalla Bloqueada)

En Linux, cuando bloqueas la pantalla (`Super + L`), todos tus procesos en segundo plano y el navegador siguen funcionando al 100%. Lo único que debemos evitar es que la laptop entre en **Suspensión (Sleep)** por inactividad o al bajar la tapa.

### A. Evitar suspensión al cerrar la tapa de la laptop
Ejecuta este comando en la terminal para editar la configuración de energía de `systemd`:

```bash
sudo nano /etc/systemd/logind.conf
```

Busca las siguientes líneas (o agrégalas al final del archivo sin el símbolo `#` adelante):

```ini
HandleLidSwitch=ignore
HandleLidSwitchExternalPower=ignore
HandleLidSwitchDocked=ignore
```

Guarda los cambios (`Ctrl + O`, luego `Enter`) y sal (`Ctrl + X`). Aplica la configuración ejecutando:

```bash
sudo systemctl restart systemd-logind
```

### B. Evitar suspensión por inactividad en el escritorio
1. Abre la **Configuración del Sistema -> Energía (Power)**.
2. En **Suspensión automática (Automatic Suspend)**:
   * Desactívala para **"Cuando esté enchufado" (Plugged In -> Off / Nunca)**.
   * *(Opcional)* Puedes dejar que la pantalla se apague tras 5 minutos para ahorrar energía; que el monitor se apague o esté bloqueado **no detiene** el script.

Si usas GNOME (Ubuntu/Debian/Fedora), también puedes desactivar la suspensión por inactividad desde terminal con:

```bash
gsettings set org.gnome.settings-daemon.plugins.power sleep-inactive-ac-type 'nothing'
```

---

## 3. Programar el Cron (7:00 AM, 3:00 PM y 11:00 PM)

El proyecto incluye el script [`run_daily.sh`](./run_daily.sh), que activa el entorno virtual, lanza el generador del Cuy y guarda todo el historial de ejecución en `cron_log.txt`.

### Paso 1: Obtener la ruta exacta de tu carpeta
Dentro de la carpeta del proyecto, ejecuta:

```bash
pwd
```
*(Copia la ruta que te devuelva, por ejemplo: `/home/tu_usuario/Documentos/cuy-flow-automation`).*

### Paso 2: Editar la tabla de Cron
Abre el programador de tareas de tu usuario:

```bash
crontab -e
```
*(Si es la primera vez y te pregunta qué editor usar, escribe `1` para elegir `nano` y presiona `Enter`).*

### Paso 3: Añadir la regla de las 3 ejecuciones diarias
Ve al final del archivo y pega la siguiente línea (reemplazando `/ruta/exacta/a/cuy-flow-automation` por la ruta que obtuviste con `pwd`):

```cron
0 7,15,23 * * * /ruta/exacta/a/cuy-flow-automation/run_daily.sh
```

* **`0`**: Minuto 0.
* **`7,15,23`**: A las **07:00** (7 AM), **15:00** (3 PM) y **23:00** (11 PM).
* **`* * *`**: Todos los días del mes, todos los meses, todos los días de la semana.

Guarda (`Ctrl + O`, `Enter`) y cierra (`Ctrl + X`).

### Paso 4: Verificar que el Cron quedó registrado
```bash
crontab -l
```
Deberías ver en pantalla la línea que acabas de guardar.

---

## 4. Rutina de Uso en la Laptop

Cada vez que enciendas o reinicies la laptop, solo debes hacer estos **3 pasos**:

1. **Iniciar sesión** con tu usuario en Linux.
2. **Levantar el navegador con puerto CDP (una sola vez):**
   ```bash
   cd /ruta/exacta/a/cuy-flow-automation
   ./launch_browser.sh
   ```
   *(Verifica la primera vez que tu cuenta de Google Flow y la de TikTok Studio tengan la sesión iniciada en esa ventana de Brave. Déjala abierta, no cierres Brave).*
3. **Bloquear la pantalla:**
   Presiona **`Super + L`** (tecla Windows + L) para dejar tu sesión bloqueada de forma segura (y baja la tapa si lo deseas, manteniendo el cargador conectado).

---

## 5. Monitoreo y Diagnóstico

* **Ver el registro en tiempo real de las ejecuciones del Cron:**
  ```bash
  tail -f cron_log.txt
  ```
* **Probar manualmente el mismo script que ejecuta el Cron:**
  ```bash
  ./run_daily.sh
  ```
* **Comprobar si el navegador tiene el puerto 9222 abierto:**
  ```bash
  curl http://127.0.0.1:9222/json/version
  ```
