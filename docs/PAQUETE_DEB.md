# Instalación .deb y desarrollo editable

## Instalar

Descarga `brujula_0.2.0_all.deb` y su SHA-256 desde la release del repositorio. En Zorin OS 18 / Ubuntu 24.04 o posterior:

```bash
sha256sum -c brujula_0.2.0_all.deb.sha256
sudo apt install ./brujula_0.2.0_all.deb
brujula
```

El paquete instala el lanzador, icono y código Python. APT resuelve las dependencias nativas. **No descarga nada durante dpkg**, no modifica tus archivos y no instala un servicio de inicio de sesión.

## Preparar IA por separado

En la primera apertura pulsa **Preparar IA**. Puedes elegir CPU (descarga menor) o GPU NVIDIA/CUDA (descarga mayor). También puedes hacerlo desde terminal:

```bash
brujula --prepare-ai cpu
# Alternativa para NVIDIA:
brujula --prepare-ai cuda
```

La preparación crea un entorno Python privado, instala PyTorch y sus dependencias y descarga EmbeddingGemma 2 (aproximadamente 1,49 GB de pesos). Verifica su SHA-256. La descarga se puede reintentar; no borres sus archivos incompletos. Los componentes de PyTorch también ocupan espacio y se descargan por separado del .deb.

El estado se muestra en la interfaz y en `~/.local/share/brujula/setup.log`. Puedes cancelar desde Preparar IA. Al terminar, sal de Brújula y ábrela otra vez para cargar el entorno nuevo.

```bash
brujula --check-runtime
brujula --download-model   # requiere un motor ya preparado
brujula --cli status
```

No se graba audio ni se envían documentos durante la preparación: solo se descargan paquetes y pesos. Las consultas posteriores son locales.

## Dónde queda cada cosa

| Contenido | Ubicación |
|---|---|
| Código instalado y scripts | `/usr/share/brujula/` |
| Lanzador | `/usr/bin/brujula` |
| Entrada de menú | `/usr/share/applications/local.brujula.search.desktop` |
| Índice/configuración | `~/.local/share/brujula/` |
| Modelo del paquete | `~/.local/share/brujula/models/embeddinggemma-2/` |
| Entorno de IA | `~/.local/share/brujula/runtime-cpu/` o `runtime-cuda/` |

Se respeta `XDG_DATA_HOME` y se permiten `BRUJULA_DATA`, `BRUJULA_MODEL_DIR` y `BRUJULA_ENGINE_PYTHON` para pruebas o ubicaciones personalizadas. El paquete no incluye el modelo ni datos personales. Una instalación desde código conserva la carpeta `models/` y `.venv` existentes en el checkout.

## Seguir editando

El .deb **no convierte el código en un ejecutable opaco**. El repositorio continúa siendo la fuente de desarrollo. No edites directamente `/usr/share/brujula`: una actualización reemplaza esos archivos.

```bash
git clone https://github.com/Maxdesigna7x/brujula.git
cd brujula
./scripts/setup.sh
./run.sh
```

Modifica `embedding_app/` y abre con `./run.sh`. También puedes usar el lanzador instalado con un checkout editable:

```bash
BRUJULA_APP_ROOT="$PWD" brujula
```

La interfaz y la inferencia siguen separadas. Si ya existe el entorno de desarrollo, se reutiliza. Índices y modelos no se incluyen en los commits ni en el instalador. Usa `BRUJULA_DATA` para mantener un índice de pruebas separado.

## Construcción

Requiere `dpkg-deb` y Python; **no necesita sudo ni el modelo descargado**:

```bash
python3 scripts/build_deb.py
```

Genera `dist/brujula_0.2.0_all.deb` y el archivo SHA-256. La arquitectura `all` corresponde al código Python; la disponibilidad de PyTorch depende de la plataforma. Se normalizan permisos, propietarios root y fechas usando `SOURCE_DATE_EPOCH` o la fecha del último commit. Para probar reproducibilidad utiliza el mismo commit, contenido y epoch.

## Actualizar o quitar

```bash
sudo apt install ./brujula_VERSION_all.deb
sudo apt remove brujula
```

APT sustituye el código instalado y conserva los datos de tu usuario. Eliminar el paquete **no borra el índice, el modelo ni el runtime**. Puedes conservarlos para reinstalar o eliminarlos manualmente con Brújula cerrada.

Si antes instalaste el lanzador de desarrollo en `~/.local/share/applications`, ese lanzador puede tener prioridad sobre el del sistema. Conserva el de desarrollo si quieres abrir tu checkout, o quítalo para usar el paquete. Un atajo antiguo también puede apuntar a `run.sh`: cambia su comando a `brujula` para abrir la versión instalada.

## Alcance de las pruebas

Consulta `docs/VALIDACION.md`. La instalación global requiere privilegios de administrador; las verificaciones aisladas no sustituyen esa instalación en el sistema real. Esta release está orientada a Zorin OS 18 / Ubuntu 24.04 en x86_64, con motor CPU probado; CUDA mantiene la instalación opcional y requiere un driver compatible.
