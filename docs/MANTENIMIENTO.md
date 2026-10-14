# Desarrollo, verificación y publicación

## Preparar una modificación

Leer [AGENTS.md](../AGENTS.md), revisar `git status` y conservar cambios ajenos. Usar el checkout editable, no modificar `/usr/share/brujula`. No hace falta descargar el modelo para editar UI, documentación o construir el paquete.

```bash
./scripts/setup.sh
./run.sh
```

El .deb también puede abrir un checkout mediante `BRUJULA_APP_ROOT="$PWD" brujula`. Salir de la instancia anterior primero: la aplicación tiene un ID único y otra activación puede presentar el proceso que ya estaba abierto. El lanzador local y el atajo pueden apuntar al checkout anterior; consultar [PAQUETE_DEB.md](PAQUETE_DEB.md).

Para pruebas de índice, escoger un directorio de datos distinto antes de iniciar el proceso:

```bash
BRUJULA_DATA="$PWD/work/prueba-aislada" ./run.sh
```

No utilizar el índice personal como fixture. Modelo y runtime pueden reutilizarse con los overrides documentados en arquitectura. No lanzar una CLI sobre el mismo índice que un backend activo: ocultar la barra no libera el bloqueo.

## Verificaciones según el cambio

| Cambio | Verificación adecuada |
|---|---|
| Documentación | Revisar enlaces relativos, comandos y coherencia con código; no inferencia necesaria. |
| Índice, filtros, disco, recursos o contrato multimedia | Regresiones unitarias; ampliar solo para comportamientos nuevos relevantes. |
| UI | Regresiones pertinentes y apertura GTK; comprobar interacción y estados vacíos/pausados/errores. |
| Encoder, dependencias o extracción | Comprobación de runtime e inferencia real sintética, separada de doubles. |
| Empaquetado | Construcción, metadatos/contenido, checksum, launcher y prueba aislada; instalación global por separado. |

```bash
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python scripts/check_runtime.py
.venv/bin/python scripts/validate_model.py
.venv/bin/python scripts/benchmark.py
```

`check_runtime.py` comprueba bibliotecas; las dos últimas órdenes requieren pesos locales y consumen memoria. Revisar los scripts antes de ejecutar inferencia: usan fixtures e informes en `work/`. No confundir rendimiento de fixtures con capacidad sobre un disco real. La CI ejecuta regresiones sin descargar Torch ni el modelo.

`scripts/test_ui.py` y `scripts/capture_ui.py` ayudan a probar/capturar GTK; revisar sus requisitos, incluidos Xvfb y dependencias del escritorio. `scripts/capture_quick.py` requiere fixtures locales en `work/popup-assets`, que no se entregan en Git. Las comprobaciones ad hoc de `work/` de la entrega original tampoco forman una suite portable.

## Construir y revisar el .deb

```bash
python3 scripts/build_deb.py
```

Para verificar el checksum, ejecutar desde su directorio, ya que contiene el nombre del archivo sin prefijo:

```bash
cd dist
sha256sum -c brujula_0.2.0_all.deb.sha256
cd ..
dpkg-deb --info dist/brujula_0.2.0_all.deb
dpkg-deb --contents dist/brujula_0.2.0_all.deb
```

El constructor toma `__version__` de `embedding_app/__init__.py`. Ajustar nombres anteriores cuando cambie la versión. Incluye código, scripts, docs, assets, examples, README, requisitos y lanzadores. Excluye pesos, entorno, índice, cachés y datos personales. El AGENTS raíz orienta el checkout; no se copia actualmente como archivo raíz del paquete.

Reproducibilidad: mismo contenido y `SOURCE_DATE_EPOCH`, preferiblemente desde un checkout limpio del mismo commit. El constructor utiliza Git para obtener el timestamp predeterminado; ejecutarlo en un checkout Git. Propietarios root dentro del paquete no implican necesidad de sudo para construirlo.

Probar un runtime limpio y un directorio de datos aislado si se cambian dependencias/preparación. Extraer un .deb prueba el layout, pero no demuestra resolución de dependencias por APT. Una instalación rootless con dependencias forzadas tampoco la demuestra. La comprobación completa incluye instalar con `sudo apt install ./...deb` en un sistema compatible y comprobar arranque/preparación.

## Actualizar versión y publicar

1. Actualizar versión y referencias de instalación/documentación. Revisar también `app_version` escrito por `setup_ai.py`; actualmente está fijado a 0.2.0.
2. Ejecutar verificaciones relevantes, revisar diff y confirmar que no hay datos personales ni dependencias/modelos añadidos a Git.
3. Hacer commit, subir los cambios autorizados y comprobar CI. El workflow produce artefactos; no publica releases automáticamente.
4. Construir desde el commit que se va a etiquetar, verificar .deb y checksum. No alterar un activo existente con contenido diferente bajo el mismo nombre/versión.
5. Crear tag y release cuando la tarea incluya publicación. Redactar notas concretas: qué cambia, cómo instalar, modelo separado, pruebas y límites. Para una entrega experimental marcar prerelease.
6. Subir .deb y SHA-256; descargar de nuevo y comprobar que coincide con el archivo local.

Con `gh`, escribir notas multilínea en un archivo y usar `--notes-file`; mantener repo privado y no cambiar licencia/visibilidad como parte incidental del empaquetado. Las credenciales no van en archivos versionados. Una actualización documental no requiere otra versión ni sustituir el .deb publicado.

## Diagnóstico de fallos y cambios de datos

Consultar [SOLUCION_DE_PROBLEMAS.md](SOLUCION_DE_PROBLEMAS.md). Logs del backend/preparación y estado runtime están en el directorio de datos. stdout RPC debe permanecer limpio; un mensaje de pip puede romper la comunicación si se redirige allí.

Antes de una migración futura, cerrar la aplicación y respaldar índice/configuración. La base usa WAL: no copiar solo el archivo principal mientras hay un escritor activo. No hay framework de migraciones actualmente. Un cambio de receta, modelo o dimensiones debe invalidar vectores coherentemente, manteniendo metadatos y los originales. No eliminar índices de discos offline para resolver un fallo de montaje.
