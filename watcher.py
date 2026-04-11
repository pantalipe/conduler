"""
watcher.py
Monitora WATCH_FOLDER por novos arquivos de vídeo.
Chama on_new_video(filepath) para cada arquivo ainda não visto.
"""

import os
import time
import logging
from config import WATCH_FOLDER, POLL_INTERVAL, VIDEO_EXTENSIONS

logger = logging.getLogger(__name__)


class FolderWatcher:
    def __init__(self, on_new_video):
        self.on_new_video  = on_new_video
        self.seen          = set()
        self.watch_folder  = WATCH_FOLDER
        self.poll_interval = POLL_INTERVAL
        self._running      = False

        os.makedirs(self.watch_folder, exist_ok=True)

    def _scan(self):
        try:
            entries = os.listdir(self.watch_folder)
        except OSError as e:
            logger.warning("Erro ao listar pasta: %s", e)
            return

        for name in entries:
            ext = os.path.splitext(name)[1].lower()
            if ext not in VIDEO_EXTENSIONS:
                continue

            path = os.path.join(self.watch_folder, name)

            if path in self.seen:
                continue

            # Aguarda o arquivo terminar de ser escrito (tamanho estável por 2s)
            if not self._is_stable(path):
                continue

            self.seen.add(path)
            logger.info("Novo vídeo detectado: %s", name)

            try:
                self.on_new_video(path)
            except Exception as e:
                logger.error("Erro ao processar %s: %s", name, e)

    def _is_stable(self, path, wait=2.0):
        """Retorna True se o arquivo não cresceu em `wait` segundos."""
        try:
            size1 = os.path.getsize(path)
            time.sleep(wait)
            size2 = os.path.getsize(path)
            return size1 == size2 and size1 > 0
        except OSError:
            return False

    def run_forever(self):
        self._running = True
        logger.info("Watcher iniciado — monitorando: %s", self.watch_folder)
        while self._running:
            self._scan()
            time.sleep(self.poll_interval)

    def stop(self):
        self._running = False
