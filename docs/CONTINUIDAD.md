# Contexto, decisiones y estado de la entrega

Actualizado el 14 de octubre de 2026. Complementa la guía técnica [AGENTS.md](../AGENTS.md). Es un registro del estado conocido, no una promesa sobre cambios posteriores.

## Qué se pidió y cómo se tradujo

El usuario quería encontrar archivos por lo que recuerda de ellos, incluyendo Descargas y discos externos, con tamaño, fechas y una importancia configurable. Prefiere identificar el tema general de un video/documento a recuperar cada detalle. Por ello se eligió muestreo acotado con embeddings locales. No se añadieron resúmenes generativos: necesitan otro modelo y un proceso distinto.

DigUp para macOS sirvió de referencia visual. Se implementó un producto Linux en Python/GTK/libadwaita, conservando integración con el escritorio y código fácil de editar. No se portó su código Swift. SQLite y comparación vectorial directa evitan un servidor adicional; la escala de millones de segmentos queda por medir.

## Evolución y motivos

| Cambio entregado | Motivo y decisión |
|---|---|
| Motor separado de GTK | GI pertenece al Python del sistema; Torch y sus bibliotecas tienen un entorno independiente. JSON por líneas mantiene el contrato sencillo. |
| Índice incremental | Comparar tamaño/mtime evita repetir inferencia; confirmar por archivo permite conservar trabajo frente a interrupciones. |
| Revisión periódica y condición GPU | Detectar novedades sin interferir continuamente con otras tareas. Sondeo configurable; no se necesita exclusividad ni se terminan procesos ajenos. |
| Barra emergente y gestión separada | La búsqueda diaria debe ser rápida; filtros avanzados, ubicaciones y preparación quedan en gestión. Ambas comparten motor. |
| Consultas multimedia y miniaturas | Se puede buscar con imagen/audio. El adjunto de imagen muestra solo la miniatura, tal como pidió el usuario. |
| Progreso en ambas ventanas | Distinguir descubrimiento, procesamiento, pausa y espera GPU; porcentaje únicamente con un total conocido. |
| Inclusión explícita por carpetas/discos | Ver qué participa en el índice. No incluir Descargas ni discos automáticamente; conservar el índice al desmarcar. |
| Selector GTK y entrada de ruta | FileChooserNative estaba mostrando cancelaciones. Se sustituyó por diálogo persistente y GIO local, con alternativa de ruta escrita. |
| .deb con IA separada | Instalar como app tradicional sin empaquetar pesos/venv/datos personales. Runtime privado por usuario; Python continúa editable. |

## Decisiones de representación y recursos

Perfil ligero: 12 fotogramas repartidos por video, cuatro ventanas de audio de 20 segundos y selección de hasta 3.000 palabras. Equilibrado: 24 fotogramas, ocho ventanas de 30 segundos y 5.000 palabras. PDF selecciona hasta unas seis páginas. Nombre y muestras tienen segmentos separados; el ranking agrupa por archivo usando la mejor coincidencia. Esta cobertura puede omitir escenas/temas.

EmbeddingGemma 2 usa una revisión fijada y pesos BF16 de aproximadamente 1,49 GB. Se guardan 256 dimensiones por defecto, normalizadas, con 1.024 bytes de vector float32 por segmento; SQLite, textos y miniaturas agregan espacio. Las consultas de texto pueden cargar solo el encoder textual; imagen/audio requieren el encoder completo. CUDA utiliza BF16 y CPU FP32. Se libera el proceso al finalizar tandas o tras inactividad.

No se infiere importancia automáticamente ni se observa uso universal: estrellas manuales y aperturas desde Brújula. La fecha de creación se muestra solo si statx la proporciona; no se usa ctime como sustituto. Tamaño significa bytes lógicos, no bloques físicos.

## Evidencia disponible y sus límites

- 24 regresiones cubren reconciliación, filtros, volúmenes, consultas multimedia, recursos y rutas del paquete. Varias usan modelos simulados y no evalúan relevancia real.
- Hubo inferencia real sintética en RTX 3060 y en un runtime CPU limpio. Las cifras y condiciones están en [VALIDACION.md](VALIDACION.md) y [USO.md](USO.md).
- GTK se comprobó bajo Xvfb, incluido el selector de carpetas, miniaturas y vistas del paquete extraído. Eso no equivale a probar cada interacción en todas las sesiones Wayland/X11.
- El .deb se instaló/actualizó en un entorno aislado, se verificó reproducibilidad y se comparó el activo descargado de GitHub. La instalación global en el sistema del usuario seguía pendiente: `sudo` requería contraseña.
- Los informes `work/` son locales e ignorados por Git. No esperar encontrarlos en un clon; los scripts versionados permiten repetir las verificaciones descritas en mantenimiento.

## Distribución conocida

Repositorio privado [Maxdesigna7x/brujula](https://github.com/Maxdesigna7x/brujula). La [release v0.2.0](https://github.com/Maxdesigna7x/brujula/releases/tag/v0.2.0) es experimental e incluye .deb y SHA-256. El commit de esa entrega es `228cf4ba14086b3ed272fbbf10f418556d3c160e`. Las actualizaciones documentales posteriores no reconstruyen ni sustituyen ese activo.

CI compila el paquete y ejecuta regresiones; sube artefactos de Actions. La publicación de una release es un paso separado. No hay licencia del proyecto elegida; no asumir que las condiciones del modelo conceden licencia al código de la app.

## Trabajo pendiente

Prioridades posibles, que deben elegirse según la siguiente solicitud:

1. Validar instalación global y preparación CUDA desde un sistema limpio, además de relevancia con fotos, voz española y videos reales del usuario.
2. Medir búsqueda y tamaño de índice con bibliotecas grandes antes de introducir un índice aproximado.
3. Añadir política de caché de miniaturas y migraciones de esquema antes de cambios incompatibles de datos.
4. Mejorar identidad al mover archivos si se necesita preservar historial y estrellas.
5. Ampliar portapapeles a URIs de archivos, múltiples adjuntos y semántica de combinación si el usuario lo pide. Actualmente otro adjunto reemplaza el primero.
6. Explorar inotify, inicio de sesión opcional, SearchProvider GNOME, OCR y perfiles por ubicación; todavía no existen.

La coordinación entre escaneo, consultas y cambios de configuración merece pruebas concurrentes adicionales. No se ha demostrado ausencia de todas las carreras. El sondeo de GPU no garantiza que otra aplicación no empiece a usarla inmediatamente después.
