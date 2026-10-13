# Diagnóstico

## El modelo tarda en llegar

Lee `work/model-download.log` y el tamaño de los `.incomplete` en `models/embeddinggemma-2/.cache/huggingface/download/`. Con Xet el archivo puede crecer por bloques; no recibir mensajes nuevos no demuestra que se detuvo. Reiniciar `scripts/download_model.py` conserva archivos ya descargados. No borres los `.incomplete` ni inicies una segunda descarga mientras la primera sigue viva.

Si Hugging Face cambia permisos o solicita aceptar condiciones, el script registra el error: autentica tu cuenta fuera de la aplicación. Nunca pongas tokens en los archivos del proyecto.

## Falta una librería o EmbeddingGemma2Model

Ejecuta `.venv/bin/python scripts/check_runtime.py` y revisa `work/dependencies.log`. Se necesita Transformers >=5.18 y Sentence Transformers >=6.1. El modelo no funciona con la versión 5.10 que estaba en el Python compartido. El instalador actualiza solo el venv.

Si falta una dependencia transitiva, instala la indicada dentro de `.venv`, no en el Python global. En una máquina nueva usa `scripts/setup.sh`; puede requerir una descarga adicional de PyTorch. GTK requiere los paquetes de Zorin `python3-gi`, `gir1.2-gtk-4.0` y `gir1.2-adw-1`.

## GPU sin memoria

Elige Configuración → Procesamiento → CPU, o cierra otras aplicaciones que usan CUDA. Busca el error en `~/.local/share/brujula/backend.log` y pulsa Reintentar errores. La indexación procesa muestras individualmente, pero los pesos/activaciones siguen necesitando memoria. CPU consume RAM y puede ser más lenta.

## No encuentro un archivo

Comprueba que su ubicación está añadida, el disco está disponible y los filtros permiten su tipo/tamaño/fecha. Mira Estado en Detalles y Actividad. El muestreo puede omitir temas; prueba el nombre o una descripción más general. Un PDF escaneado no tiene OCR en esta versión. Actualizar procesa archivos pendientes; Reintentar errores vuelve a procesar fallos.

## “Brújula ya está abierta”

Usa **Salir de Brújula** en la ventana de gestión antes de CLI/daemon. Ocultar la barra no cierra el motor. El bloqueo se libera al terminar el proceso; no es necesario borrar backend.lock. Nunca ejecutes dos indexadores contra la misma base.

## Reiniciar el índice

Usa **Salir de Brújula**. Renombra `~/.local/share/brujula` como copia de seguridad. La próxima apertura crea un índice vacío; vuelve a añadir tus ubicaciones. Esto no borra archivos originales ni modelos. Eliminar una ubicación desde la interfaz elimina solamente sus registros.

## Quitar la aplicación

Usa **Salir de Brújula** y elimina el lanzador `~/.local/share/applications/local.brujula.search.desktop`. El proyecto, modelo e índice se pueden conservar o eliminar por separado.

## Micrófono o miniaturas

Configura el micrófono predeterminado desde Sonido en Zorin. La app usa pw-record o arecord, sin descargar otro modelo de reconocimiento de voz. Si no puede grabar, adjunta un archivo de audio. La consulta no produce una transcripción.

Fotos usan Pillow; videos requieren FFmpeg y PDF requieren pdftoppm. Si no se genera miniatura, aparece un icono y las acciones siguen disponibles. Los originales no se modifican. La caché se puede borrar tras salir de la aplicación.

## Error al añadir carpeta

La versión actual usa un selector GTK integrado en lugar del selector Native/portal anterior. **Añadir carpeta** ofrece tres vías: escribir una ruta, **Añadir Descargas** o **Examinar carpetas**. Una selección en Examinar rellena la ruta; pulsa **Añadir esta ruta** para incluirla. No se añade nada al cancelar. Las ubicaciones incluidas y las casillas de discos muestran qué participa realmente; los discos detectados no están incluidos por defecto.
