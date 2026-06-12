import os
import subprocess
import imageio_ffmpeg
from groq import Groq

class GroqService:
    def __init__(self, api_key=None):
        self.api_key = api_key or os.getenv("GROQ_API_KEY")
        self.client = None
        if self.api_key:
            self.client = Groq(api_key=self.api_key)
            
    def is_configured(self):
        return self.client is not None

    def extract_audio(self, video_path, audio_output_path="extracted_audio.mp3"):
        """Extrae el audio del video en formato MP3 con bajo bitrate usando ffmpeg directamente"""
        print(f"Extrayendo audio de {video_path} usando ffmpeg...")
        
        if os.path.exists(audio_output_path):
            try:
                os.remove(audio_output_path)
            except Exception:
                pass
                
        ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
        cmd = [
            ffmpeg_exe,
            "-i", video_path,
            "-vn",
            "-acodec", "libmp3lame",
            "-ac", "1",
            "-ab", "16k",
            "-ar", "16000",
            "-y",
            audio_output_path
        ]
        
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if result.returncode != 0:
            err_msg = result.stderr.decode("utf-8", errors="ignore")
            raise IOError(f"Error al extraer audio con ffmpeg (código {result.returncode}):\n{err_msg}")
            
        print("Audio extraído exitosamente.")
        return audio_output_path

    def transcribe_audio(self, audio_path, progress_callback=None):
        """
        Envía el audio a la API de Groq usando whisper-large-v3.
        Devuelve una lista de segmentos con timestamps.
        """
        if not self.is_configured():
            raise ValueError("API Key de Groq no configurada.")
            
        print("Iniciando transcripción súper rápida con Groq...")
        if progress_callback:
            progress_callback(0.2, "Subiendo audio a la red de Groq (Whisper Large V3)...")
            
        # Groq requiere leer el archivo en bytes
        with open(audio_path, "rb") as file:
            audio_data = file.read()
            
        # Límite duro de Groq es 25MB
        file_size_mb = len(audio_data) / (1024 * 1024)
        print(f"Tamaño del archivo de audio: {file_size_mb:.2f} MB")
        if file_size_mb > 25:
            raise ValueError(f"El archivo de audio es demasiado grande para la API de Groq ({file_size_mb:.2f} MB). Límite es 25MB.")

        if progress_callback:
            progress_callback(0.5, "Procesando transcripción con Inteligencia Artificial (LPU)...")

        try:
            transcription = self.client.audio.transcriptions.create(
                file=("audio.mp3", audio_data),
                model="whisper-large-v3",
                prompt="Transcripción de clase académica o técnica. Nombres de conceptos clave, explicaciones detalladas, definiciones y términos precisos.",
                response_format="verbose_json",
                language="es"
            )
            
            if progress_callback:
                progress_callback(0.9, "Procesando resultados estructurados...")
                
            # Extraer segmentos de la respuesta
            formatted_segments = []
            if hasattr(transcription, "segments") and transcription.segments:
                for seg in transcription.segments:
                    if isinstance(seg, dict):
                        formatted_segments.append({
                            "start": float(seg.get("start", 0)),
                            "end": float(seg.get("end", 0)),
                            "text": seg.get("text", "").strip()
                        })
                    else:
                        formatted_segments.append({
                            "start": float(getattr(seg, "start", 0)),
                            "end": float(getattr(seg, "end", 0)),
                            "text": getattr(seg, "text", "").strip()
                        })
            else:
                # Fallback si por alguna razón no hay segmentos detallados
                formatted_segments = [{
                    "start": 0.0,
                    "end": 99999.0,
                    "text": getattr(transcription, "text", str(transcription))
                }]
                
            return formatted_segments
            
        except Exception as e:
            raise Exception(f"Error al transcribir con Groq API: {str(e)}")
