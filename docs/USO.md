# Brújula — búsqueda local para Zorin OS

Aplicación GTK para encontrar archivos por significado, nombre y texto, con filtros por disco, carpeta y zonas personales. Código en `/ruta/a/brujula`.

## Abrir

Busca **Brújula** en el menú de Zorin, o ejecuta:

```bash
cd /ruta/a/brujula
./run.sh
```

La interfaz usa `/usr/bin/python3` y GTK 4/libadwaita del sistema. El motor usa `.venv/bin/python` en el checkout si existe, o el runtime privado preparado por la instalación .deb. Sin runtime preparado, el backend básico usa el Python del sistema. Consulta [instalación .deb](PAQUETE_DEB.md).

**La búsqueda semántica necesita que terminen tanto la descarga como la instalación de dependencias.** La interfaz, los metadatos y la búsqueda por nombre funcionan sin el modelo. El texto se extrae sin modelo cuando están disponibles los extractores.

## Buscador emergente

El menú y el atajo abren ahora una barra compacta. La ventana grande se conserva como **Configuración y ubicaciones**, accesible con ⚙. Ambas comparten el mismo motor e índice.

- **Texto:** escribe una descripción; busca al dejar de escribir o al pulsar Enter.
- **Imagen:** pulsa el icono de imagen, arrastra un archivo o pega una imagen del portapapeles con Ctrl+V. El adjunto muestra solo su miniatura y el botón para quitarlo; no muestra el nombre del archivo.
- **Audio:** pulsa el micrófono para grabar una consulta; vuelve a pulsarlo para terminar. Máximo 30 segundos. También puedes adjuntar o arrastrar un archivo de audio (se usan sus primeros 30 segundos).
- Texto más imagen/audio se combina mediante el promedio normalizado de sus embeddings. Las consultas adjuntas no se añaden al índice y sus conversiones temporales se eliminan.
- La voz se usa como consulta semántica directa, **sin transcripción**. La calidad de voz en español debe evaluarse con tus grabaciones; puede ayudar añadir una descripción escrita.

Los resultados aparecen en la misma ventana: hasta doce coincidencias ordenadas por relevancia a la izquierda y una vista previa de la selección a la derecha. Imágenes, fotogramas de video y primera página de PDF pueden tener miniaturas. Los demás formatos conservan su icono y, si existe, muestra de texto. Los videos muestran un fotograma muestreado; Abrir inicia la aplicación habitual, sin salto automático a ese instante. No hay reproducción integrada en el panel.

**↑/↓** selecciona; **Enter** abre el resultado; **Ctrl+Enter** abre su carpeta; **Esc** oculta. Si estás escribiendo una nueva consulta, Enter busca en lugar de abrir el resultado anterior.

**Ocultar la barra o cerrar la ventana de configuración no detiene Brújula.** El proceso permanece activo e indexa según los intervalos y la condición de GPU. Para detenerlo usa **Salir de Brújula** en la ventana grande. El modelo sigue liberándose por inactividad. No se instala un servicio de inicio de sesión; abre Brújula una vez para activar el proceso.

Las miniaturas se guardan en `~/.local/share/brujula/thumbnails`. Contienen información visual de tus archivos, pueden conservarse para discos desconectados y no se suben. Puedes borrar esa carpeta con Brújula cerrada para liberar su caché.

## Primer uso

1. Pulsa **Añadir carpeta**. Puedes escribir una ruta, usar **Añadir Descargas** o **Examinar carpetas**. No hay ubicaciones incluidas por defecto.
2. El índice comienza por metadatos y continúa con contenido cuando el modelo está disponible.
3. Escribe algo como `tutorial para instalar Linux` y pulsa Enter.
4. Selecciona una ubicación, un disco o una zona en la barra lateral.
5. Ajusta tipo, tamaño mínimo/máximo en **GB decimales**, fecha de modificación y orden. Pulsa **Aplicar** para los filtros de tamaño/fecha.
6. **Actualizar** revisa cambios y procesa contenido pendiente. **Pausar** conserva el trabajo; **Continuar** reanuda. **Detener** finaliza después de la operación actual.

La **barra de progreso** aparece en la ventana de gestión y, mientras hay trabajo, en el panel emergente. Durante el escaneo indica actividad y archivos encontrados; cuando se conoce la tanda pendiente, muestra porcentaje, contador y archivo actual. El avance incluye las muestras del archivo en curso. Pausado y Esperando GPU quedan señalados; no se inventa una duración estimada. El porcentaje corresponde a esta revisión, no al total histórico del índice; revisa los errores en Actividad. El panel compacto oculta el indicador cuando termina.

El índice se conserva entre reinicios y se revisa al abrir la aplicación. Se revisan cambios cada 15 minutos mientras la aplicación está abierta. Las carpetas ocultas, enlaces simbólicos y algunas extensiones de credenciales se excluyen. La lista no sustituye una revisión de tus carpetas: elige explícitamente qué indexar.

## Discos y zonas

- **Discos:** la casilla incluye/excluye el contenido del volumen; el botón con su nombre solo filtra la búsqueda. **Incluido completo** = todo el volumen admitido, **Parcial** = solo algunas ubicaciones y **No incluido** = no participa en búsquedas ni análisis. Desmarcar conserva el índice y nunca elimina archivos originales.
- Para indexar un disco de datos completo, marca su casilla. Para incluir solo una carpeta, añádela por ruta o mediante el selector. El disco principal también se puede marcar; se omiten directorios virtuales, temporales, ocultos y exclusiones, y no se atraviesan otros sistemas de archivos montados. Puede contener muchos archivos; la barra muestra el progreso y la condición de GPU sigue aplicándose.
- **Zona:** agrupación de ubicaciones ya indexadas. Crea `Trabajo`, `Personal` o `Multimedia` y elige sus carpetas. El mismo archivo puede aparecer en varias zonas sin duplicarse.
- Para cambiar una zona, utiliza **Crear zona**, escribe su nombre existente y selecciona su nuevo conjunto.
- **Limitar a una carpeta:** filtra por ruta dentro de una ubicación indexada.
- Los volúmenes se identifican por UUID cuando es posible. Un disco desconectado conserva su índice. Al volver a montarlo se actualizan sus rutas.
- No se duplican archivos al incluir un disco completo que ya tenía carpetas añadidas. Esas carpetas conservan sus registros y zonas; el resto del disco se indexa por separado. También puedes añadir una carpeta concreta dentro de un disco completo para controlarla individualmente. Se rechazan otras raíces solapadas.
- Las casillas junto a **Ubicaciones** permiten excluir carpetas individualmente. Un disco completo con alguna carpeta excluida aparece como **Parcial**. **Gestionar ubicaciones** elimina índices o zonas, nunca archivos originales. Detén la indexación primero.

## Configuración

- **Ligero:** 12 fotogramas, 4 ventanas de audio de 20 segundos, 3.000 palabras seleccionadas.
- **Equilibrado:** 24 fotogramas, 8 ventanas de 30 segundos, 5.000 palabras.
- **Personalizado:** permite modificar esos límites individualmente.
- **Procesamiento:** automático, CPU o CUDA. Automático usa NVIDIA si PyTorch puede acceder a ella.
- **Dimensiones:** 128/256/512/768. Predeterminado 256. Para imágenes/audio, compara la calidad antes de elegir 128.
- **Liberar modelo:** tras 120 segundos de inactividad; al finalizar una tanda de indexación también se libera.
- **Tipos/exclusiones:** controla qué archivos se incluyen. Las exclusiones son nombres exactos de directorios, no patrones ni rutas.
- Cambiar límites o dimensiones requiere **Actualizar** para regenerar los segmentos afectados. Durante esa actualización las búsquedas siguen utilizando nombre/texto y vectores compatibles.
- El perfil es global en esta versión, no individual por ubicación.

## Actualización incremental y GPU libre

La revisión periódica compara tamaño y fecha de modificación: los archivos sin cambios conservan sus embeddings. Un archivo nuevo o modificado queda pendiente; no se vuelve a analizar toda la carpeta. Los cambios de configuración que afectan al contenido sí pueden requerir una reindexación más amplia.

En Configuración puedes ajustar dos intervalos independientes:

- **Revisar cambios cada (min):** 15 minutos por defecto, mientras Brújula está abierta.
- **Comprobar GPU cada (seg):** 60 segundos por defecto para permitir o reanudar análisis pendiente.

**Indexar solo cuando la GPU esté libre** está activado por defecto. Se exige uso GPU ≤15% y al menos 2.500 MiB disponibles. Ambos límites son configurables. Se comprueba GPU NVIDIA 0 mediante `nvidia-smi`, entre archivos y muestras, con lecturas limitadas al intervalo elegido. Si se ocupa, se muestra “Esperando GPU libre”, se libera el modelo y se reintenta automáticamente. No se interrumpe una inferencia o extracción ya iniciada.

Las consultas que haces tú no esperan esta condición. La pausa manual sigue teniendo prioridad. En modo CPU se ignora la condición de GPU; si no se puede comprobar NVIDIA, la indexación espera y puedes seleccionar CPU o desactivar la condición. Al estimar memoria se reconoce la memoria de nuestro propio modelo para evitar bloquearse por sus pesos. El uso de GPU se mide después de un breve descanso de nuestras inferencias; es una muestra, no una reserva exclusiva de la GPU.

Esta revisión funciona mientras el proceso de Brújula está activo, incluso con la barra oculta. **Salir de Brújula** detiene el motor; aún no hay servicio de inicio de sesión.

## Qué ves en los resultados

Tamaño lógico, fecha de modificación, ubicación y modalidad que produjo la coincidencia. Los detalles incluyen fecha de creación **solo cuando Linux la proporciona**, una muestra textual y aperturas realizadas desde Brújula. La estrella es importancia manual; no se infiere automáticamente.

La muestra de texto **no es un resumen generado**. Un embedding es un vector y no redacta descripciones. El muestreo de videos ofrece cobertura general y puede omitir temas o escenas. Los resultados se agrupan por archivo y no prometen precisión por minuto. Se muestran hasta 100 resultados.

## Descarga e instalación

La descarga es reanudable, con dos conexiones concurrentes y reintentos:

```bash
.venv/bin/python scripts/download_model.py
```

Modelo: `google/embeddinggemma-2`, revisión fijada `914f7f89142e33e77833254d9c9b90c3cef7303b`, aproximadamente 1,49 GB de pesos BF16 más tokenizador/configuración. No descargamos el modelo en cada búsqueda. La inferencia usa archivos locales y modo offline.

Si necesitas preparar el entorno:

```bash
./scripts/setup.sh
.venv/bin/python scripts/check_runtime.py
```

No ejecutes dos instaladores o dos descargas del modelo simultáneamente. La preparación integrada registra su salida en `~/.local/share/brujula/setup.log`; `setup-state.json` contiene el estado. Los registros de scripts de desarrollo pueden estar en `work/`.

## Datos y registros

- Índice/configuración: `~/.local/share/brujula/index.sqlite3`.
- Registro del motor: `~/.local/share/brujula/backend.log`.
- Modelo: en el checkout si existe `models/embeddinggemma-2/config.json`; de lo contrario, `~/.local/share/brujula/models/embeddinggemma-2/` (configurable).
- Muestras de audio/fotogramas: archivos temporales, eliminados al terminar cada archivo.
- Los archivos originales se leen; no se modifican, mueven ni suben. El índice contiene rutas, muestras de texto y embeddings, por lo que debes tratarlo como datos personales.
- Abrir un resultado inicia su aplicación predeterminada. Las descargas iniciales contactan Hugging Face; la búsqueda no necesita internet.

## Atajo de teclado

En el equipo original se configuró **Ctrl+Alt+Space** para abrir el panel; un clon o instalación nueva requiere configurar el atajo. El instalador conserva los demás atajos y rechaza conflictos. Reinstalar: `/usr/bin/python3 scripts/install_shortcut.py`. Quitar: añade `--remove`.

Para elegir otra combinación, en Configuración de Zorin → Teclado → Atajos personalizados, edita:

- Nombre: `Brújula`
- Comando: `/ruta/a/brujula/run.sh`
- Combinación sugerida: `Ctrl+Alt+Space` si está libre.

El paquete instala el lanzador global. En desarrollo puedes instalar el lanzador de usuario con `.venv/bin/python scripts/install_desktop.py`.

## CLI

Usa **Salir de Brújula** antes de usar la CLI: una instancia del motor por índice.

```bash
./cli.sh status
./cli.sh add /ruta/a/carpeta --name Documentos
./cli.sh index
./cli.sh search 'fotos de montañas' --kind image
./cli.sh search 'linux' --location 1
```

Puedes aislar pruebas con `BRUJULA_DATA=/ruta/a/directorio-de-prueba`. No apunta al índice personal si defines esa variable.

## Pruebas

```bash
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python scripts/check_runtime.py
.venv/bin/python scripts/validate_model.py
```

El modelo ya fue descargado y probado en este equipo. La última prueba necesita conservar esos archivos locales. Verifica inferencia real de texto, imagen y audio sintéticos, y búsqueda semántica; registra memoria y tiempos en `work/model-validation.json`.

## Rendimiento medido en este equipo

RTX 3060 de 12 GB, PyTorch BF16. Prueba pequeña con contenido sintético:

| Operación | Tiempo con modelo preparado | Memoria |
|---|---:|---|
| Consulta corta | 30 ms | ~0,55 GB de pico asignado por CUDA |
| Texto de 660 palabras | 134 ms | ~0,66 GB de pico asignado por CUDA |
| Imagen 640×480 | 176 ms | ~1,55 GB de pico asignado por CUDA |
| Audio de 20 segundos | 293 ms | ~1,58 GB de pico asignado por CUDA |

El proceso de inferencia mostró **2,38–2,79 GB de RAM residente**, adicionales a la memoria GPU. El pico reservado por PyTorch llegó a ~1,64 GB; el contexto CUDA puede añadir consumo que estas cifras no incluyen. No son cifras del sistema completo.

La primera carga del proceso y modelo de texto tardó aproximadamente **7 segundos**. Ampliar de texto a multimodal tardó ~4,75 segundos, incluyendo la primera imagen. Una búsqueda posterior es mucho más rápida mientras el modelo permanece cargado. Se libera tras el plazo de inactividad configurado.

Estos tiempos no incluyen todo el escaneo, lectura, extracción FFmpeg ni búsquedas sobre bibliotecas grandes. No permiten prometer archivos por minuto. El audio de prueba fue un tono sintético; comprueba la relevancia en tus grabaciones reales. Informes: `work/benchmark.json`, `work/model-validation.json`, `work/model-integrity.json`.

## Límites de esta versión

- Sin OCR para PDF escaneados ni capturas; esos archivos conservan búsqueda por nombre y, en imágenes, semántica visual.
- PDF: hasta seis páginas repartidas; documentos DOCX/ODT y texto con selección acotada. RTF solo por nombre.
- Sin transcripción completa de voz, resumen generativo, detector automático de importancia o rastreo universal de uso.
- Revisiones periódicas, no vigilancia instantánea con inotify.
- Sin columnas/menús de Nautilus ni proveedor GNOME Shell en esta entrega. Integra el lanzador GTK y permite atajo del sistema.
- Sin perfil individual por carpeta ni ordenación por nombre. El panel muestra miniaturas en lista y vista previa; no hay cuadrícula completa.
- El total en Actividad corresponde a archivos admitidos e indexados; no mide todo el espacio ocupado por una carpeta/disco ni espacio físico asignado.
- El índice vectorial hace comparación directa por segmentos filtrados: simple y adecuado para empezar. Millones de segmentos requerirían medir y adoptar un índice aproximado.

Arquitectura: [docs/ARQUITECTURA.md](ARQUITECTURA.md). Diagnóstico: [docs/SOLUCION_DE_PROBLEMAS.md](SOLUCION_DE_PROBLEMAS.md). Estado de pruebas: [docs/VALIDACION.md](VALIDACION.md).

## Prueba rápida sin tus archivos personales

Añade `/ruta/a/brujula/examples` desde la interfaz. Contiene un manual de Linux y una receta de chocolate. Busca `cómo instalar un sistema operativo`: el manual debería aparecer primero. Quita esa ubicación cuando termines de probar.
