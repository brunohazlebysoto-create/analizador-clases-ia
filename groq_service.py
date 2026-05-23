import os
import base64
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
            # Groq Python SDK puede devolver los segments como atributos de objeto o como diccionario
            formatted_segments = []
            if hasattr(transcription, "segments") and transcription.segments:
                for seg in transcription.segments:
                    # Dependiendo de cómo lo deserializa el SDK de Groq
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

    def _encode_image(self, image_path):
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode('utf-8')

    def synthesize_slide(self, image_path, transcript_text):
        if not self.is_configured():
            raise ValueError("API Key de Groq no configurada.")
            
        base64_image = self._encode_image(image_path)
        
        prompt = (
            "Eres un experto académico y revisor científico. Te proporcionaré una diapositiva "
            "proyectada en una clase médica junto con la transcripción de lo que dijo el orador.\n"
            "Genera una explicación unificada y detallada, pero ve directo al grano.\n\n"
            f"--- TRANSCRIPCIÓN DEL ORADOR ---\n{transcript_text}\n----------------------------------\n\n"
            "Instrucciones estrictas:\n"
            "1. Integra la información visual y la transcripción.\n"
            "2. Evita repetir información introductoria general al inicio. Entra directo al tema central de esta diapositiva.\n"
            "3. NO incluyas conclusiones, resúmenes o cierres al final, a menos que el orador los haya dicho explícitamente.\n"
            "4. Si hay casos clínicos o datos numéricos, conviértelos en tablas de Markdown.\n"
            "5. Usa subtemas (### Subtema) si se abordan distintos conceptos.\n"
            "6. Sección '### Corroboración Científica': Esta sección debe ser SILENCIOSA. Escríbela ÚNICAMENTE si detectas que la diapositiva o el orador dijeron algo médicamente incorrecto o desactualizado. Si la información es correcta, omite esta sección por completo."
        )

        models_to_try = [
            "meta-llama/llama-4-scout-17b-16e-instruct",
            "llama-3.2-90b-vision-preview",
            "llama-3.2-11b-vision-preview",
            "llama-3.2-90b-vision-instruct",
            "llama-3.2-11b-vision-instruct"
        ]
        
        last_error = None
        for model_name in models_to_try:
            try:
                chat_completion = self.client.chat.completions.create(
                    messages=[
                        {
                            "role": "user",
                            "content": [
                                {"type": "text", "text": prompt},
                                {
                                    "type": "image_url",
                                    "image_url": {
                                        "url": f"data:image/jpeg;base64,{base64_image}",
                                    },
                                },
                            ],
                        }
                    ],
                    model=model_name,
                    temperature=0.2
                )
                return chat_completion.choices[0].message.content
            except Exception as e:
                print(f"Error en Groq Vision con {model_name}: {e}")
                last_error = e
                err_msg = str(e).lower()
                # Si el modelo fue retirado o no existe, probar con el siguiente
                if "decommissioned" in err_msg or "does not exist" in err_msg or "not found" in err_msg:
                    continue
                # Si es otro error (como límite de cuota o clave mala), frenar
                raise ValueError(f"Error crítico en Groq Vision: {e}")
                
        raise ValueError(f"Todos los modelos visuales de Groq fallaron. Último error: {last_error}")

    def supervise_text(self, draft_text, transcript_text):
        """Agente Auditor Médico: Busca errores de omisión o exceso de resúmenes."""
        if not self.is_configured():
            return "No se pudo auditar (API Key faltante)."
            
        prompt = (
            "Eres el Agente Auditor Médico. Tu trabajo es leer la transcripción original del orador y compararla "
            "con el borrador generado por otro modelo de IA.\n\n"
            "Tu ÚNICA tarea es encontrar si la IA omitió información médica importante que sí estaba en la transcripción, "
            "o si resumió tanto que se perdió contexto clínico vital.\n\n"
            f"--- TRANSCRIPCIÓN ORIGINAL ---\n{transcript_text}\n\n"
            f"--- BORRADOR DE LA IA ---\n{draft_text}\n\n"
            "REGLAS PARA TU REPORTE:\n"
            "1. NO reescribas el texto. Solo haz una lista de críticas directas y cortas.\n"
            "2. Si la IA omitió algo importante, di 'FALTA: [dato]'.\n"
            "3. Verifica que no haya introducciones repetitivas inútiles ni conclusiones inventadas.\n"
            "4. Si el borrador está perfecto y no le falta nada vital, responde ÚNICAMENTE con la palabra: 'APROBADO'."
        )
        
        try:
            chat_completion = self.client.chat.completions.create(
                messages=[{"role": "user", "content": prompt}],
                model="llama-3.3-70b-versatile",
                temperature=0.1
            )
            return chat_completion.choices[0].message.content.strip()
        except Exception as e:
            print(f"Error en Auditor Groq: {e}")
            return "APROBADO" # Fallback silencioso

    def supervise_and_edit_text(self, draft_text, transcript_text):
        """
        Agente Supervisor y Editor Médico de Groq: Toma el borrador de Gemini y la transcripción,
        los compara y produce la versión final depurada y enriquecida directamente.
        """
        if not self.is_configured():
            return draft_text
            
        prompt = (
            "Eres el Agente Supervisor y Editor Académico de Groq. Tu trabajo es revisar el borrador "
            "de explicación de una diapositiva generado por Gemini y compararlo con la transcripción "
            "original de lo que dijo el orador, con el fin de producir la versión final y definitiva del reporte.\n\n"
            "INSTRUCCIONES DE SUPERVISIÓN:\n"
            "1. CORRECCIÓN DE OMISIONES (NO RESUMIR EN EXCESO): Asegúrate de que no se haya omitido ninguna información "
            "de valor de la transcripción original ni de la diapositiva. Si el orador proporcionó detalles, explicaciones, "
            "ejemplos o datos específicos en la transcripción que no están en el borrador de Gemini, intégralos de forma "
            "fluida y sumamente detallada.\n"
            "2. ESTILO ACADÉMICO DIRECTO: Elimina introducciones redundantes (ej. 'Esta diapositiva...', 'Como vemos aquí...') "
            "y conclusiones/resúmenes repetitivos al final. Ve directo al grano académico.\n"
            "3. MEJORA DE FORMATO: Mantén y optimiza el uso de Markdown (subtemas '###', negritas, listas ordenadas y viñetas).\n"
            "4. TABLAS: Si hay datos estructurados, clasificaciones o números útiles, asegúrate de presentarlos en tablas de Markdown.\n"
            "5. ACLARACIÓN DE ERRORES (SILENCIOSA): Si y solo si detectas una contradicción directa o error factual obvio "
            "del orador con respecto a lo expuesto en la diapositiva, añade una sección final llamada '### Aclaración de Errores' "
            "explicando de forma neutral la corrección. Si el contenido de la transcripción y el borrador es correcto y "
            "coherente, NO agregues esta sección bajo ningún concepto (omítela por completo, no dejes títulos vacíos ni confirmaciones de éxito).\n\n"
            f"--- TRANSCRIPCIÓN ORIGINAL DEL ORADOR ---\n{transcript_text}\n\n"
            f"--- BORRADOR DE GEMINI ---\n{draft_text}\n\n"
            "Escribe directamente la explicación final depurada. No agregues preámbulos, comentarios del revisor, "
            "ni textos introductorios del estilo 'Aquí está el resultado'. Solo la explicación lista para el informe."
        )
        
        try:
            chat_completion = self.client.chat.completions.create(
                messages=[{"role": "user", "content": prompt}],
                model="llama-3.3-70b-versatile",
                temperature=0.2
            )
            return chat_completion.choices[0].message.content.strip()
        except Exception as e:
            print(f"Error en Supervisor Groq: {e}")
            return draft_text

