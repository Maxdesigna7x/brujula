# Arquitectura e implementación

## Procesos

`run.sh` → GTK/libadwaita (`app.py`, Python del sistema) → JSON por stdin/stdout → `backend.py` (venv) → proceso `inference.py` (PyTorch/Sentence Transformers).

No hay servidor HTTP ni puerto de red local. La interfaz envía operaciones en hilos para no bloquear GTK. El backend mantiene un hilo de indexación y un planificador de revisiones. El acceso al encoder se serializa: no se cargan dos modelos completos al mismo tiempo. El proceso del modelo usa terminación vinculada al padre en Linux para evitar modelos huérfanos.

SQLite usa WAL, conexiones por operación y cierre explícito. Un bloqueo `flock` impide dos motores sobre el mismo directorio de datos. El índice es persistente; no se guarda el progreso parcial de un archivo, pero cada archivo terminado queda confirmado por transacción.

## Módulos

| Archivo | Función |
|---|---|
| `storage.py` | Esquema SQLite, configuración, zonas, registro |
| `volumes.py` | lsblk, UUID, asociación carpeta/volumen, cambio de montaje |
| `metadata.py` | statx para fecha de creación, desconocida si no disponible |
| `readers.py` | Tipos, texto, muestreo y FFmpeg/FFprobe |
| `indexer.py` | Escaneo, exclusiones, reconciliación y segmentos |
| `inference.py` | Modelo offline, prompts, normalización, proceso aislado |
| `search.py` | Filtros SQL, coincidencias literales y producto escalar |
| `resources.py` | Consulta NVIDIA, umbrales de uso/memoria y espera cancelable |
| `backend.py` | RPC, CLI, ciclo periódico y coordinación |
| `app.py` | Motor compartido de UI, ventana de gestión y ciclo de vida |
| `progress.py` | Indicador compartido de descubrimiento, muestras y avance de la tanda |
| `quick.py` | Panel emergente, consultas multimedia, resultados y vista previa |
| `thumbnails.py` | Caché visual local de fotos, videos y PDF |

## Identidad y coherencia

La clave de archivo es `(location_id, relative)`, no el inode: funciona entre sistemas ext/NTFS y remounts. Tamaño y mtime nanosegundos detectan modificaciones. Un cambio elimina vectores obsoletos y marca pendiente. Mover un archivo dentro de una ubicación se procesa como eliminación/alta; en esta versión no conserva su estrella ni historial.

El escaneo utiliza un token por ubicación. Solo se eliminan registros no vistos tras un recorrido completo, sin errores y con volumen aún disponible. No se purga un volumen desconectado. Los enlaces simbólicos no se recorren.

Los segmentos llevan identidad de modelo (revisión fijada), receta y dimensiones. Buscar ignora vectores incompatibles. La receta global incluye límites de extracción y tipos/exclusiones. Antes/después del análisis se verifica que el archivo no cambió. Archivos modificados hace menos de cinco segundos se dejan pendientes hasta la siguiente revisión.

La fecha de creación se obtiene con statx/STATX_BTIME. No se sustituye por ctime. El tamaño mostrado es lógico (bytes), no bloques físicos ocupados.

## Representaciones

Textos: prompt `document`; consultas: prompt `query`, según configuración oficial. Cada fragmento contiene hasta 650 palabras y el nombre del archivo. Documentos largos toman principio/centro/final; PDF selecciona páginas repartidas. Fotos se codifican directamente con presupuesto visual de 140 soft tokens. Videos se representan mediante fotogramas repartidos y ventanas independientes de audio; no se introducen dos horas de video en una sola llamada. Audio mono a 16 kHz.

La salida de 768 dimensiones se trunca por MRL y se renormaliza. Se guarda float32 little-endian. Con 256 dimensiones son 1.024 bytes por segmento, antes del overhead SQLite. Se conserva una representación del nombre por archivo y varios segmentos cuando hay contenido.

El resultado de un archivo usa la mejor coincidencia entre sus segmentos más una bonificación literal acotada. No se presentan los scores como probabilidades. Modalidades distintas no han sido calibradas con una colección real del usuario; esto es una oportunidad de evaluación posterior.

## Recursos

El modelo se carga solo cuando se necesita. Consultas puramente textuales pueden cargar únicamente el encoder de texto; una indexación multimodal requiere ampliarlo. PyTorch usa BF16 en CUDA compatible, FP32 en CPU. Nunca FP16. Inferencia secuencial y dos hilos CPU para limitar picos. Al terminar una tanda se cierra el proceso; después de inactividad también.

La interfaz permanece funcional mientras se descarga. El índice inicialmente ofrece nombres/metadatos y texto extraíble. Un cambio a modelo disponible dispara una nueva revisión con la app abierta.

## Extensiones previstas

Agregar backend Q8/llama.cpp, inotify, OCR, miniaturas, perfil por ubicación y filtros de etiquetas múltiples. Integración GNOME SearchProvider2 y menú de Nautilus sobre el mismo motor, evitando bases duplicadas. Resúmenes generativos serían un paso separado, cacheado y explícitamente configurable.

## Referencias

- https://github.com/ARahim3/DigUp — referencia de diseño: motor separado, descarga de memoria y espacio multimodal. No se ha portado código Swift.
- https://ai.google.dev/gemma/docs/embeddinggemma/model_card_2
- https://ai.google.dev/gemma/docs/embeddinggemma/multimodal-embeddinggemma-with-sentence-transformers
- https://huggingface.co/google/embeddinggemma-2/tree/main

## Planificación por recursos

El escaneo de metadatos no necesita GPU. Antes de extraer muestras de un archivo pendiente y entre embeddings, ResourceGate comprueba la GPU a intervalos configurables. La espera puede cancelarse con Detener y respeta Pausar. No mantiene el encoder cargado mientras espera a otra tarea. Las consultas interactivas usan directamente Encoder y no pasan por ResourceGate.

El sondeo de nvidia-smi tiene timeout de cinco segundos y utiliza GPU 0, como el encoder. La memoria de nuestro proceso puede sumarse a la libre porque se puede liberar. Una lectura no garantiza exclusividad: otra tarea puede empezar después; el siguiente sondeo la detectará. No se mata ni modifica ningún proceso externo.

## Panel emergente y consultas multimedia

Adw.Application mantiene una sola instancia por sesión y usa hold para seguir trabajando con ventanas ocultas. Una activación nueva presenta la barra existente, sin duplicar backend. La ventana de gestión comparte Client. Salir cierra el encoder/backend; Esc únicamente oculta.

Las consultas de imagen se redimensionan a 1024 px como máximo; el presupuesto visual del modelo sigue siendo 140 soft tokens. El audio de referencia se convierte con FFmpeg a 16 kHz mono y se limita a 30 s. Texto y referencia se codifican por separado, promedian y renormalizan; no se promete razonamiento composicional de la consulta combinada.

Las miniaturas se generan fuera de la inferencia, en hasta tres hilos, con timeout para FFmpeg/Poppler. El identificador incluye archivo, mtime, tamaño y posición. El panel conserva la posición del segmento que produjo la mejor similitud y puede representar ese fotograma como vista previa, pero abrir el video no hace seek. Los iconos son el fallback si falta un extractor o el archivo está desconectado sin caché.

La grabación empieza solo tras pulsar el micrófono, usa el dispositivo predeterminado de PipeWire (pw-record) o ALSA (arecord) y se detiene a los 30 segundos o al ocultar el panel. No se graba en segundo plano ni se envía audio a servicios remotos.

## Progreso

Indexer publica stage, scanned, done/total, part_done/part_total, location y current. El porcentaje es (done + part_done/part_total) / total cuando el total de archivos pendientes se conoce. El escaneo y la extracción textual previa al modelo usan actividad indeterminada. IndexProgress consume el mismo estado en ambas ventanas y mantiene el porcentaje durante pausas/esperas. Un error cuenta como archivo revisado y se señala por separado; 100% no garantiza que todos los archivos se hayan indexado correctamente.

## Inclusión por disco y selector de carpetas

Los discos muestran un estado derivado de locations.enabled y de sus raíces: ninguno/parcial/completo. El toggle incluye el volumen completo o deshabilita todas sus ubicaciones, sin purgar SQLite. Se admiten raíces de volumen mediante set_disk; la operación normal de añadir ruta sigue validando ubicaciones.

Un recorrido de raíz excluye sububicaciones existentes para mantener una sola pertenencia por archivo. Si se añade una subcarpeta posteriormente, se reasignan los registros coincidentes conservando IDs, vectores, estrellas e historial. La búsqueda de una ubicación padre expande sus sububicaciones. El escaneo usa st_dev para no cruzar otros discos, evita directorios virtuales y considera únicamente archivos regulares.

Los cambios de inclusión detienen la tanda actual, esperan su cierre y arrancan otra revisión; los archivos confirmados ya están persistidos. El selector de carpetas usa Gtk.FileChooserDialog integrado y una referencia persistente, evitando el ciclo del selector Native/portal que estaba dando cancelación. GIO usa el backend local directo para el sistema de archivos, sin depender de montajes GVfs. Se ofrece además entrada por ruta y un botón basado en xdg-user-dir DOWNLOAD.
