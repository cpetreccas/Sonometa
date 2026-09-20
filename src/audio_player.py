import os
import io
import time
import pygame


class AudioPlayer:
    """Gestor del reproductor de audio integrado para vista previa de pistas."""

    def __init__(self, detail_panel):
        self.panel = detail_panel
        self.app = detail_panel.app
        self.logger = detail_panel.logger

        self.current_file_path = None
        self.is_playing = False
        self.is_paused = False

        self.audio_stream = None
        self.total_length = 0.0
        self.start_time_offset = 0.0
        self.playback_start_real_time = 0.0
        self.volume = 1.0

        self._is_seeking = False
        self._init_mixer()

    def _init_mixer(self):
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init(frequency=44100, size=-16, channels=2)
        except Exception as e:
            self.logger.error(f"No se pudo inicializar el motor de audio: {e}")

    # ------------------------------------------------------------------
    # Control de Reproducción
    # ------------------------------------------------------------------

    def load_track(self, file_path):
        """Asigna la ruta de la pista, obtiene su duración ultrarrápida y resetea la interfaz."""
        if self.current_file_path == file_path and self.total_length > 0:
            return

        # Cambiado keep_duration=True para evitar que la interfaz parpadee o borre la duración a 0
        self.stop_and_unload(keep_duration=True)
        self.current_file_path = file_path

        # Obtener duración al instante leyendo la cabecera del archivo
        self.total_length = self.app.audio_manager.get_fast_audio_duration(file_path)
        self.panel.update_audio_time_display(0, self.total_length)
        if hasattr(self.panel, "slider_audio") and self.panel.slider_audio:
            self.panel.slider_audio.set(0)

    def toggle_play_pause(self):
        """Acción principal del botón Play/Pause."""
        if not self.current_file_path or not os.path.exists(self.current_file_path):
            return

        if self.is_playing:
            if self.is_paused:
                pygame.mixer.music.unpause()
                self.is_paused = False
                self.playback_start_real_time = time.time()
                self.panel.btn_play.configure(text="⏸")
                self._schedule_progress_update()
            else:
                pygame.mixer.music.pause()
                self.is_paused = True
                if self.playback_start_real_time > 0:
                    self.start_time_offset += time.time() - self.playback_start_real_time
                self.playback_start_real_time = 0.0
                self.panel.btn_play.configure(text="▶")
        else:
            self.start_playback(start_time=self.start_time_offset)

    def start_playback(self, start_time=0.0):
        """Carga el audio en memoria y reproduce desde la posición indicada."""
        try:
            if not self.total_length or self.total_length <= 0:
                self.total_length = self.app.audio_manager.get_fast_audio_duration(self.current_file_path)

            # Cargar archivo a búfer en memoria si no está cargado ya
            if self.audio_stream is None:
                with open(self.current_file_path, "rb") as f:
                    self.audio_stream = io.BytesIO(f.read())

            self.audio_stream.seek(0)
            pygame.mixer.music.load(self.audio_stream)
            pygame.mixer.music.set_volume(self.volume)

            # Acotar la posición a un rango válido
            start_time = max(0.0, min(start_time, self.total_length if self.total_length > 0 else start_time))

            # Reproducir desde la posición deseada
            pygame.mixer.music.play(start=start_time)

            self.is_playing = True
            self.is_paused = False
            self.start_time_offset = start_time
            self.playback_start_real_time = time.time()

            self.panel.btn_play.configure(text="⏸")
            self._schedule_progress_update()

        except Exception as e:
            self.logger.error(f"Error reproduciendo audio: {e}")
            self.stop_and_unload(keep_duration=False)

    def stop_and_unload(self, keep_duration=False):
        """Detiene la reproducción y libera recursos sin destruir opcionalmente la duración conocida."""
        try:
            pygame.mixer.music.stop()
            pygame.mixer.music.unload()
        except Exception:
            pass

        if self.audio_stream:
            try:
                self.audio_stream.close()
            except Exception:
                pass

        self.audio_stream = None
        self.is_playing = False
        self.is_paused = False
        self.start_time_offset = 0.0
        self.playback_start_real_time = 0.0

        if not keep_duration:
            self.total_length = 0.0
            self.current_file_path = None

        if hasattr(self.panel, "btn_play") and self.panel.btn_play:
            self.panel.btn_play.configure(text="▶")
            if hasattr(self.panel, "slider_audio") and self.panel.slider_audio:
                self.panel.slider_audio.set(0)
            self.panel.update_audio_time_display(0, self.total_length if keep_duration else 0)

    # ------------------------------------------------------------------
    # Gestión del Bloqueo de Archivos
    # ------------------------------------------------------------------

    def prepare_for_file_write(self):
        """No requiere pausar o liberar el archivo ya que Pygame lee desde el búfer BytesIO."""
        return False, 0.0

    def resume_after_file_write(self, file_path, was_playing, saved_pos):
        """No requiere reanudación."""
        pass

    # ------------------------------------------------------------------
    # Barra de Progreso y Seek
    # ------------------------------------------------------------------

    def _get_current_position(self):
        if not self.is_playing or self.is_paused or self.playback_start_real_time <= 0:
            return self.start_time_offset

        elapsed = self.start_time_offset + (time.time() - self.playback_start_real_time)
        return max(0.0, min(elapsed, self.total_length if self.total_length > 0 else elapsed))

    def _schedule_progress_update(self):
        if self.is_playing and not self.is_paused and not self._is_seeking:
            current_pos = self._get_current_position()

            if not pygame.mixer.music.get_busy() and current_pos > 0:
                self.stop_and_unload(keep_duration=True)
                return

            if current_pos >= self.total_length and self.total_length > 0:
                self.stop_and_unload(keep_duration=True)
                return

            if self.total_length > 0:
                progress = current_pos / self.total_length
                self.panel.slider_audio.set(progress)
                self.panel.update_audio_time_display(current_pos, self.total_length)

            self.app.after(100, self._schedule_progress_update)

    def on_seek_start(self, value):
        self._is_seeking = True

    def on_seek_end(self, value):
        self._is_seeking = False
        if self.total_length > 0 and self.current_file_path:
            target_time = float(value) * self.total_length
            was_playing = self.is_playing and not self.is_paused

            # Preservar referencias antes del stop
            saved_file_path = self.current_file_path
            saved_total_length = self.total_length

            self.stop_and_unload(keep_duration=True)

            self.current_file_path = saved_file_path
            self.total_length = saved_total_length

            if was_playing:
                self.start_playback(start_time=target_time)
            else:
                self.start_time_offset = target_time
                self.playback_start_real_time = 0.0
                self.panel.slider_audio.set(value)
                self.panel.update_audio_time_display(target_time, self.total_length)

    def set_volume(self, value):
        self.volume = float(value)
        pygame.mixer.music.set_volume(self.volume)