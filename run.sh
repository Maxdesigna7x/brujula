#!/usr/bin/env bash
set -e
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
export GIO_USE_VFS=local
exec /usr/bin/python3 -m embedding_app.app "$@"
