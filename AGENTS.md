# Guía para agentes que continúen Brújula

Estado documentado: 14 de octubre de 2026, después de la entrega experimental v0.2.0. Este archivo orienta el trabajo; el código y las pruebas son la fuente de verdad del comportamiento actual.

## Leer antes de cambiar

1. `README.md`: producto, instalación y límites visibles para el usuario.
2. `docs/CONTINUIDAD.md`: decisiones, evolución, evidencia y pendientes.
3. `docs/ARQUITECTURA.md`: procesos, datos e invariantes.
4. `docs/MANTENIMIENTO.md`: desarrollo, verificación y publicación.
5. `docs/USO.md`, `docs/PAQUETE_DEB.md` y `docs/VALIDACION.md` según la tarea.

## Objetivo y preferencias del usuario

Buscador semántico local para Linux/Zorin, con cobertura general y consumo acotado. No se pretende examinar exhaustivamente videos largos. La interfaz habitual es una barra emergente simple; la ventana grande sirve para configurar ubicaciones, discos y recursos. Una imagen adjunta se representa **solo con miniatura y botón de quitar**, sin nombre textual. Mantener Python editable y distribuir un .deb pequeño con IA descargada aparte.

## Mapa rápido

- `embedding_app/app.py`, `quick.py`, `progress.py`: GTK, barra, gestión y progreso compartido.
- `backend.py`: protocolo JSON por líneas, CLI, planificador y preparación de IA.
- `storage.py`, `indexer.py`, `volumes.py`: SQLite, reconciliación incremental y discos.
- `readers.py`, `inference.py`, `search.py`, `resources.py`, `thumbnails.py`: extracción, embeddings, ranking, GPU y vistas previas.
- `paths.py`, `setup_ai.py`: separación código/datos/runtime y descarga verificable.
- `scripts/`, `packaging/`, `.github/workflows/deb.yml`: desarrollo, paquete y CI.

Los módulos citados sin directorio están dentro de `embedding_app/`.

## Invariantes que deben conservarse

- Leer los archivos originales; no modificarlos, moverlos ni subirlos. Excluir enlaces simbólicos y directorios virtuales al escanear raíces.
- No purgar archivos de discos desconectados ni después de recorridos incompletos/con errores. Reconciliar rutas por UUID cuando sea posible.
- No regenerar embeddings de archivos sin cambios. No duplicar propiedad entre una raíz de disco y sus sububicaciones. Conservar IDs, estrellas, vectores e historial al reasignar una subcarpeta.
- Desmarcar una ubicación conserva su índice; quitarla elimina registros, nunca los originales. Casilla del disco = inclusión; botón con nombre = filtro.
- Una aplicación y un backend por directorio de datos. Ocultar ventanas sigue trabajando; Salir libera procesos. No añadir silenciosamente un servicio de arranque.
- stdout del backend contiene **exclusivamente JSON del protocolo**. Logs, pip, descargas y diagnósticos deben ir a stderr o archivos.
- No bloquear el hilo GTK con extracción, descarga, inferencia ni generación de miniaturas.
- GPU libre es una condición para indexación, no una reserva exclusiva. Consultas interactivas omiten esa espera; pausa manual tiene prioridad. CPU no necesita sondeo NVIDIA.
- Embedding no es resumen ni transcripción. Una consulta admite un adjunto; otro lo sustituye. Texto + adjunto promedia vectores normalizados, sin prometer condiciones conjuntas exactas.
- Modelo fijado por revisión y SHA-256; no cambiarlo a `main` móvil. Mantener coherencia entre receta, dimensiones y fingerprint de segmentos.

## Separar desarrollo de datos personales

La interfaz utiliza `/usr/bin/python3` con GI del sistema. El backend selecciona el runtime según `paths.py`; no asumir que toda la aplicación se ejecuta en `.venv`.

Para pruebas que escriban datos, definir **antes de importar módulos** `BRUJULA_DATA` con una ruta absoluta aislada. `DATA` se calcula al importar `paths.py`. Un `Store` temporal por sí solo no redirige la descarga/preparación de IA. Consultar la precedencia de rutas en arquitectura. No borrar ni migrar el índice personal para probar una hipótesis.

No versionar `.venv/`, `models/`, `work/`, `dist/`, índices SQLite, registros, secretos ni archivos del usuario. Reutilizar los pesos locales para comprobaciones; no repetir descargas grandes sin necesidad. El checkout original está en `/home/randy/Python/Embedding_APP`; un clon puede tener otra ruta.

## Verificación y entregas

Usar pruebas relevantes al cambio; para documentación basta comprobar consistencia y enlaces. Para cambios de índice, filtros, recursos o multimedia, ejecutar las regresiones descritas en mantenimiento. Las pruebas con doubles no demuestran calidad del modelo: distinguirlas de inferencia real y de pruebas con archivos del usuario.

Repositorio: `https://github.com/Maxdesigna7x/brujula`, privado al documentar esta entrega. Release experimental: v0.2.0. No cambiar visibilidad ni elegir una licencia por cuenta propia. Publicar cuando forme parte de la solicitud del usuario; consultar mantenimiento para los pasos reproducibles. No sobrescribir un binario publicado por una actualización solo documental.

## Limitaciones importantes

No hay OCR, resumen generativo, transcripción, inotify, SearchProvider GNOME, seek al abrir videos ni perfiles por ubicación. Uso = aperturas desde esta app; importancia = estrella manual. La caché de miniaturas no tiene cuota automática. Mover un archivo se trata como baja/alta y puede perder estrella/historial. No existe framework de migraciones SQLite. La instalación global del .deb seguía pendiente de ejecutarse con privilegios; las pruebas aisladas no la sustituyen.

Actualizar esta guía y los documentos afectados cuando cambie una decisión o se cierre una limitación. Documentar motivo, comportamiento resultante, evidencia de pruebas y riesgos pendientes, sin convertir planes en funciones ya implementadas.
