"""Non-invasive NVIDIA scheduling; interactive searches are never gated."""
import subprocess
import time


def gpu_snapshot():
    """Inspect CUDA device 0, matching the encoder's default GPU."""
    try:
        output = subprocess.check_output(
            ['nvidia-smi', '--id=0',
             '--query-gpu=utilization.gpu,memory.free,memory.total',
             '--format=csv,noheader,nounits'],
            text=True, timeout=5,
        )
        utilization, free, total = [float(x.strip()) for x in output.strip().split(',')]
        return {'available': True, 'utilization': utilization,
                'free_mb': free, 'total_mb': total}
    except FileNotFoundError:
        return {'available': False, 'reason': 'nvidia-smi no está instalado'}
    except (subprocess.SubprocessError, ValueError, OSError) as exc:
        return {'available': False, 'reason': str(exc)}


def own_gpu_memory(pid):
    if not pid:
        return 0
    try:
        output = subprocess.check_output(
            ['nvidia-smi', '--id=0', '--query-compute-apps=pid,used_gpu_memory',
             '--format=csv,noheader,nounits'], text=True, timeout=5,
        )
        return sum(float(memory.strip()) for line in output.splitlines()
                   for process, memory in [line.split(',')]
                   if int(process.strip()) == pid)
    except (subprocess.SubprocessError, ValueError, OSError):
        return 0


def decision(settings, snapshot, own_mb=0):
    if not settings['gpu_idle_only'] or settings['device'] == 'cpu':
        return True, ''
    if not snapshot['available']:
        return False, 'No se puede comprobar la GPU; selecciona CPU para continuar'
    if snapshot['utilization'] > settings['gpu_max_utilization']:
        return False, f"Uso GPU {snapshot['utilization']:.0f}% (límite {settings['gpu_max_utilization']}%)"
    # Existing model memory is reclaimable; don't block ourselves on its weights.
    free = snapshot['free_mb'] + own_mb
    if free < settings['gpu_min_free_mb']:
        return False, f"Memoria disponible {free:.0f} MiB (mínimo {settings['gpu_min_free_mb']} MiB)"
    return True, ''


class ResourceGate:
    def __init__(self):
        self.next_check = 0
        self.last = {}

    def wait(self, get_settings, encoder, state, checkpoint):
        """Called before extraction and between embeddings; only indexer waits."""
        if time.monotonic() < self.next_check:
            return
        while True:
            checkpoint()
            settings = get_settings()
            if not settings['gpu_idle_only'] or settings['device'] == 'cpu':
                self.next_check = 0
                return
            # Let utilization decay after our own inference. Once per probe,
            # not once per file, so this doesn't add seconds to every document.
            settle_until = encoder.last + 2 if encoder.process else 0
            while time.monotonic() < settle_until:
                checkpoint()
                time.sleep(.1)
            snapshot = gpu_snapshot()
            process = encoder.process
            own_mb = own_gpu_memory(process.pid if process else None)
            allowed, reason = decision(settings, snapshot, own_mb)
            self.last = snapshot | {'allowed': allowed, 'reason': reason}
            if allowed:
                self.next_check = time.monotonic() + settings['gpu_check_seconds']
                state['phase'] = 'Analizando contenido'
                return
            state['phase'] = 'Esperando GPU libre · ' + reason
            encoder.close()  # Release our weights while waiting for other work.
            deadline = time.monotonic() + settings['gpu_check_seconds']
            while time.monotonic() < deadline:
                checkpoint()
                # A settings change to CPU or disabling the guard takes effect
                # promptly, even if the configured probe interval is long.
                updated = get_settings()
                if not updated['gpu_idle_only'] or updated['device'] == 'cpu':
                    state['phase'] = 'Analizando contenido'
                    return
                time.sleep(.5)
