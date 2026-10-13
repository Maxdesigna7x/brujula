# Estado de validación

La verificación se ejecuta con archivos sintéticos y un directorio de datos temporal; no se indexa automáticamente la biblioteca personal.

## Comprobado sin modelo

- Pruebas de filtros por ubicación/carpeta/tamaño y zona vacía.
- Normalización de tildes para coincidencia literal.
- Exclusión de carpetas privadas, enlaces y extensiones sensibles.
- Invalidación de vectores al modificar archivos y limpieza tras eliminación.
- Conservación de registros al desconectar discos y actualización de rutas al remontar por UUID.
- Zonas sin duplicar y rechazo de raíces solapadas.
- Muestreo de principio/centro/final y puntos repartidos en multimedia.
- Arranque GTK bajo Xvfb; captura en `work/interface.png`.

## Inferencia real

**Completada en este equipo.**

- Descarga de 1.488.915.288 bytes de pesos, SHA-256 verificado contra `197a32965d4b1105faf060417baa899e193fb73cd401f42ec9295234d5553d79`.
- Runtime importado y requisitos de dependencias comprobados en el entorno efectivo, incluyendo las bibliotecas heredadas por system-site-packages.
- Embeddings de texto finitos, normalizados y de 256 dimensiones.
- Consulta sobre instalación de Linux: similitud 0,822 con el manual y 0,540 con la receta.
- Inferencia de imagen y audio comprobada con muestras sintéticas.
- Indexación de cinco archivos: dos textos, imagen, audio y video con fotogramas/audio. Todos en estado ready.
- Búsqueda de Ubuntu devuelve primero el manual de Linux.
- Veinticuatro pruebas de regresión del índice y filtros, incluyendo escaneo incompleto y ausencia de bonificación acumulada por múltiples segmentos.
- Nuevos archivos y modificaciones: solo se regeneran los embeddings afectados; los archivos sin cambios no vuelven a pasar por el encoder.
- Guardia de GPU: espera con alta utilización o memoria insuficiente, contabiliza pesos propios, reanuda al quedar libre y permite cancelar; modo CPU omite la condición.
- GTK: arranque, resultados, detalles, configuración, zonas, gestión de ubicaciones y actividad ejercitados bajo Xvfb.
- Prueba de statx comparada con fecha de creación de GNU stat.

Informes: `work/model-validation.json`, `work/model-integrity.json`, `work/benchmark.json`. La evaluación semántica fue pequeña y sintética; no constituye una evaluación de relevancia sobre la biblioteca del usuario ni sobre voz en español.

Picos PyTorch: ~0,55 GB asignados de GPU en consultas cortas y ~1,58 GB en multimodal/audio de 20 segundos. RAM residente del proceso: 2,38–2,79 GB. Ver tabla en README.

## Alcance

El plan completo incluía extensiones GNOME/Nautilus, perfiles por ubicación, OCR y resúmenes opcionales. Esta entrega implementa el núcleo y la aplicación nativa; las extensiones se mantienen pendientes y no se presentan como terminadas.

## Buscador emergente

- Entrada por imagen/audio: preprocesamiento real de Pillow/FFmpeg y búsquedas con vectores controlados; no indexa el archivo de consulta y elimina sus conversiones temporales.
- Miniaturas reales de imagen, video y PDF; recuperación desde caché cuando desaparece el original.
- Panel GTK: resultados, vista previa, selección con teclado, ocultar/reabrir y gestión compartiendo el mismo motor. Captura `work/quick-panel.png` con resultados **sintéticos de demostración**.
- La captura no constituye una evaluación de relevancia sobre archivos personales. No se grabó el micrófono del usuario para probar; la grabación solo empieza con su clic. La recuperación semántica por voz en español sigue pendiente de evaluación con grabaciones representativas.

## Discos y carpetas

Se verificaron estados ninguno/parcial/completo, exclusión sin borrado, reconexión y conservación de IDs al pasar de carpetas a disco completo o al añadir una subcarpeta después. El nuevo selector integrado abrió y navegó a la carpeta de ejemplos y se canceló correctamente, sin añadir automáticamente ubicaciones personales.

## Release .deb 0.2.0

- Paquete construido con dpkg-deb, propietarios root y lanzador validado con desktop-file-validate. No incluye modelos, venv, índices ni cachés personales.
- Instalación/actualización de la aplicación mediante dpkg en una raíz temporal sin privilegios. Las dependencias se marcaron como forzadas porque esa raíz tiene una base dpkg vacía; se utilizaron las librerías nativas del host. **No se pudo instalar globalmente con sudo sin la contraseña del usuario.**
- Runtime nuevo Python 3.12, PyTorch 2.12.0+cpu y torchvision 0.27.0+cpu, preparado mediante el lanzador del paquete; dependencias resueltas desde cero.
- Descarga independiente del modelo reutilizando los archivos ya descargados, con acceso a Hugging Face y SHA-256 completo correcto; sin volver a transferir 1,49 GB.
- Inferencia CPU real de texto, imagen y audio; cinco archivos sintéticos (incluido video con sonido) indexados sin errores. La búsqueda de Linux coloca primero el manual; la búsqueda por imagen devuelve primero la imagen correspondiente.
- Interfaz del código instalado probada bajo Xvfb tanto antes de preparar IA como después: muestra/oculta correctamente el asistente y abre la configuración.
- Veinticuatro pruebas de regresión, incluyendo rutas de instalación y runtime externo. GitHub Actions construye el .deb sin descargar un modelo.

Informes locales en work/deb-runtime-validation.json, work/deb-setup-final.log y work/deb-gui-*.log. CUDA usa el runtime de desarrollo ya probado en el equipo; no se descargó un segundo runtime CUDA limpio para esta release.
