# Micro Open Source

Dictado local y gratuito para macOS, inspirado en la experiencia de las aplicaciones de dictado por pulsacion. Mantiene una combinacion de teclas, graba la voz y pega la transcripcion en la aplicacion activa.

El audio se procesa en el propio Mac con Whisper y MLX. No se incluye ninguna API de pago ni se envia el audio a un servidor.

## Funciones

- Dictado global manteniendo `Ctrl + Option` o mediante una pulsacion corta.
- Transcripcion privada en el Mac con Whisper Large V3 Turbo y MLX.
- Espanol, ingles y deteccion automatica.
- Selector de microfono y varios atajos configurables.
- Diccionario personal para nombres, marcas y vocabulario propio.
- Comandos hablados de puntuacion, parrafos, interrogaciones, exclamaciones y comillas.
- Historial local, sonidos y restauracion del portapapeles configurables.
- Copiar, pegar o deshacer la ultima transcripcion desde la barra de menu.
- Limpieza inteligente opcional con Ollama, tambien local y sin API.

## Requisitos

- Mac con Apple Silicon (M1 o posterior)
- macOS 13 o posterior
- Python 3.12
- [uv](https://docs.astral.sh/uv/getting-started/installation/)
- Herramientas de linea de comandos de Xcode (`xcode-select --install`)

La primera ejecucion descarga el modelo `mlx-community/whisper-large-v3-turbo`, que ocupa aproximadamente 1,6 GB.

## Instalacion

```bash
git clone https://github.com/danielmonroy-niteragency/micro-opensource.git
cd micro-opensource
./install.sh
```

El instalador comprueba que el Mac sea compatible, instala `uv` desde su web oficial si hace falta y crea `~/Applications/Dictado.app`. Tambien prepara un entorno aislado en `~/Dictado` y configura el arranque automatico al iniciar sesion.

## Permisos de macOS

La primera vez, macOS solicitara estos permisos para `Dictado`:

- **Microfono**, para capturar la voz.
- **Monitorizacion de entrada**, para detectar la combinacion global.
- **Accesibilidad**, para pegar el texto en la aplicacion activa.

Se gestionan en `Ajustes del Sistema > Privacidad y seguridad`. Si Accesibilidad no esta concedida, el texto queda en el portapapeles para pegarlo manualmente.

## Uso

- Mantener `Ctrl + Option`: graba mientras se mantienen pulsadas; al soltar, transcribe y pega.
- Pulsacion corta: deja la grabacion activa sin mantener las teclas. Otra pulsacion la detiene.
- Icono de microfono: permite cambiar idioma y atajo, editar el diccionario, abrir el historial o pegar la ultima transcripcion.

Idiomas incluidos: espanol, ingles y deteccion automatica.

### Limpieza inteligente local opcional

El modo literal funciona sin ningun programa adicional. Para corregir puntuacion y muletillas con un modelo local, instala [Ollama](https://ollama.com/download), abre su aplicacion y activa `Limpieza inteligente local (Ollama)` desde el icono de Dictado.

Por defecto se usa `llama3.2:3b`. Puede elegirse otro modelo antes de abrir Dictado:

```bash
export DICTADO_OLLAMA_MODEL="nombre-del-modelo"
```

El modo inteligente es opcional y puede consumir memoria adicional. Si Ollama no responde, Dictado conserva el texto literal para no perder la transcripcion.

## Privacidad

- El audio se procesa localmente y no se conserva despues de transcribir.
- Las transcripciones se guardan solo en `~/.dictado/historial.txt` para que el menu pueda abrir el historial.
- La configuracion y el diccionario personal se guardan en `~/.dictado/`.
- Esos archivos, el modelo, los logs y el entorno virtual no forman parte del repositorio.

## Desinstalacion

```bash
./uninstall.sh
```

Este comando desactiva el arranque automatico. Para eliminarlo completamente, borra manualmente `~/Applications/Dictado.app`, `~/Dictado` y `~/.dictado`.

## Desarrollo

Ejecutar sin instalar:

```bash
uv run --python 3.12 dictado.py
```

Comprobar la sintaxis:

```bash
python3 -m py_compile dictado.py text_processing.py
python3 -m unittest discover -s tests -v
```

## Licencia

[MIT](LICENSE)

