import os
import time
import subprocess
import imageio_ffmpeg
from google import genai
from google.genai import types
from PIL import Image
from pydantic import BaseModel, Field
from typing import List

# Definición de estructuras para la salida estructurada de Gemini (Pydantic v2 compatible)
class TranscriptSegment(BaseModel):
    start: float = Field(description="Tiempo de inicio del segmento en segundos")
    end: float = Field(description="Tiempo de fin del segmento en segundos")
    text: str = Field(description="Texto transcrito en este intervalo de tiempo")

class TranscriptResponse(BaseModel):
    segments: List[TranscriptSegment]

class GeminiService:
    def __init__(self, api_key=None):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        self.client = None
        if self.api_key:
            self.client = genai.Client(api_key=self.api_key)
            
    def is_configured(self):
        return self.client is not None

    def _generate_content_with_fallback(self, contents, config=None):
        """
        Llama a la API de Gemini con reintentos automáticos ante errores 503 (Alta Demanda)
        y con fallback automático si el modelo principal no está disponible.
        """
        models_to_try = ["gemini-3.5-flash"]
        last_exception = None
        
        for model_name in models_to_try:
            retries = 3
            delay = 2.0
            for attempt in range(retries):
                try:
                    # Llamar al modelo correspondiente
                    if config:
                        response = self.client.models.generate_content(
                            model=model_name,
                            contents=contents,
                            config=config
                        )
                    else:
                        response = self.client.models.generate_content(
                            model=model_name,
                            contents=contents
                        )
                    return response
                except Exception as e:
                    last_exception = e
                    err_msg = str(e)
                    err_msg_lower = err_msg.lower()
                    # Identificar si el error es de límite de cuota diario (no reintentable hoy)
                    if "exceeded your current quota" in err_msg_lower or "billing details" in err_msg_lower:
                        if "please retry in" in err_msg_lower:
                            delay = 60 # El límite es por minuto (RPM), forzar pausa de 1 minuto
                        else:
                            raise ValueError(f"Has excedido tu cuota gratuita de la API de Gemini. Por favor, revisa tu plan en Google AI Studio.\n\nError: {err_msg}")
                    
                    # Identificar si el error es temporal (503 alta demanda, 429 rate limit por minuto)
                    is_temporary = any(term in err_msg_lower for term in [
                        "503", "429", "resource_exhausted", "unavailable", "demand", "limit"
                    ])

                    
                    if is_temporary and attempt < retries - 1:
                        print(f"La API de Gemini está experimentando alta demanda en {model_name}. Reintentando en {delay} segundos...")
                        time.sleep(delay)
                        delay *= 2 # Backoff exponencial (2s -> 4s)
                    else:
                        # Si no es un error temporal, o ya agotamos los reintentos, pasamos al siguiente modelo
                        print(f"Falló llamada con {model_name}: {err_msg}")
                        break
            
        # Si llegamos aquí, ambos modelos fallaron definitivamente
        raise last_exception

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



    def synthesize_slide_batch(self, slides_batch):
        """
        Envía un lote de diapositivas a Gemini para reducir peticiones (bypasseando el límite 429).
        slides_batch es una lista de diccionarios: [{"id": int, "image_path": str, "transcript": str}, ...]
        Retorna un diccionario: {slide_id: explanation_string}
        """
        if not self.is_configured():
            raise ValueError("API Key de Gemini no configurada.")
            
        prompt = (
            "Eres un experto académico y docente. Analizarás un LOTE de diapositivas proyectadas "
            "en una clase junto con la transcripción de lo que dijo el orador en ese momento.\n"
            "Debes generar una explicación unificada y detallada para CADA diapositiva de forma independiente, "
            "procesándolas juntas en una sola respuesta.\n\n"
            "REGLAS ESTRICTAS PARA CADA DIAPOSITIVA:\n"
            "1. NO utilices introducciones genéricas ni repetitivas (ej. 'En esta diapositiva vemos...', 'Esta imagen muestra...'). Entra directamente al tema principal.\n"
            "2. RETENCIÓN DE DETALLES (NO RESUMIR EN EXCESO): Integra de forma exhaustiva la imagen de la diapositiva y la transcripción de audio. NO omitas información de valor. Conserva nombres de conceptos, fórmulas, datos técnicos, ejemplos, tablas y explicaciones específicas presentadas en la diapositiva o mencionadas por el orador.\n"
            "3. FIDELIDAD ESTRICTA: NO inventes ni agregues información externa, ni asumas conclusiones o resúmenes finales a menos que el orador los haya expresado explícitamente.\n"
            "4. TABLAS Y FORMATO: Si hay datos estructurados, clasificaciones o datos numéricos, preséntalos en tablas de Markdown claras.\n"
            "5. ACLARACIÓN DE ERRORES (SILENCIOSA): Incluye la sección '### Aclaración de Errores' ÚNICAMENTE si detectas que el orador cometió una contradicción directa, error conceptual obvio o desliz factual con respecto a lo expuesto en la diapositiva. Si todo es correcto y consistente, NO agregues esta sección ni menciones nada sobre ella (debe omitirse por completo, sin dejar títulos vacíos).\n\n"
            "FORMATO DE SALIDA OBLIGATORIO:\n"
            "Tu respuesta debe separar la explicación de cada diapositiva usando este marcador exacto:\n"
            "===DIAPOSITIVA_ID_X===\n"
            "Donde X es el número de la diapositiva que estás explicando. Debajo de ese marcador, escribe todo el análisis detallado de esa diapositiva. "
            "Repite este proceso para cada diapositiva proporcionada."
        )
        
        contents = [prompt]
        
        for slide in slides_batch:
            slide_id = slide["id"]
            contents.append(f"\n\n--- DATOS DE LA DIAPOSITIVA {slide_id} ---")
            contents.append(Image.open(slide["image_path"]))
            contents.append(f"\nTranscripción del orador durante la Diapositiva {slide_id}:\n{slide['transcript']}\n")
            
        # Generación (sin búsqueda en vivo para lotes grandes para evitar timeouts)
        config = types.GenerateContentConfig(temperature=0.2)
        response = self._generate_content_with_fallback(contents=contents, config=config)
        
        response_text = response.text
        results = {}
        
        import re
        # Dividir por el marcador ===DIAPOSITIVA_ID_X===
        parts = re.split(r'===DIAPOSITIVA_ID_(\d+)===', response_text)
        
        # El split genera: [texto_antes_del_primer_marcador, id1, contenido1, id2, contenido2...]
        for i in range(1, len(parts), 2):
            try:
                s_id = int(parts[i])
                s_content = parts[i+1].strip()
                results[s_id] = s_content
            except ValueError:
                pass
                
        # Por seguridad, si el LLM no usó bien los IDs o faltan, llenar los vacíos
        for slide in slides_batch:
            if slide["id"] not in results:
                results[slide["id"]] = "Error: El modelo de IA no generó una respuesta estructurada para esta diapositiva."
                
        return results

    def edit_text_with_critique(self, draft_text, critique_text, transcript_text):
        """Agente Editor Médico (Gemini): Recibe su propio borrador y una crítica de auditoría, para generar la versión final."""
        if not self.is_configured():
            return draft_text
            
        if "APROBADO" in critique_text.upper() and len(critique_text) < 20:
            return draft_text # No hay cambios necesarios
            
        prompt = (
            "Eres el Agente Editor Médico en Jefe. Recibirás una transcripción original, un borrador médico y un "
            "Reporte de Auditoría.\n\n"
            "Tu tarea es REESCRIBIR el borrador para solucionar todas las críticas del Auditor. Si el auditor indica "
            "que FALTA un dato, intégralo fluidamente desde la transcripción original.\n\n"
            "REGLAS ESTRICTAS DE FORMATO:\n"
            "1. NO pongas introducciones genéricas (ej. 'Esta diapositiva muestra...').\n"
            "2. NO inventes conclusiones (ej. 'En resumen...').\n"
            "3. NO escribas la sección de 'Corroboración Científica' a menos que el orador tenga un error médico explícito.\n\n"
            f"--- TRANSCRIPCIÓN ORIGINAL ---\n{transcript_text}\n\n"
            f"--- BORRADOR ACTUAL ---\n{draft_text}\n\n"
            f"--- CRÍTICAS DEL AUDITOR ---\n{critique_text}\n\n"
            "Escribe la versión final y definitiva basándote en la corrección de las críticas. Sé directo y profesional."
        )
        
        try:
            response = self._generate_content_with_fallback([prompt])
            return response.text
        except Exception as e:
            print(f"Error en Gemini Editor: {e}")
            return draft_text

    def supervise_and_edit_text(self, image_path, draft_text, transcript_text):
        """
        Agente Supervisor y Editor Académico de Gemini: Toma el borrador, la imagen de la diapositiva y la transcripción,
        revisa que no haya omisiones o resúmenes excesivos, corrige errores y produce la versión final.
        """
        if not self.is_configured():
            return draft_text
            
        prompt = (
            "Eres el Agente Supervisor y Editor Académico de Gemini. Tu trabajo es revisar un borrador de explicación "
            "de una diapositiva frente a la diapositiva original (imagen) y la transcripción del audio del orador.\n\n"
            "INSTRUCCIONES DE EDICIÓN:\n"
            "1. CORRECCIÓN DE OMISIONES (NO RESUMIR EN EXCESO): Asegúrate de que no se haya omitido ninguna información "
            "clave de la diapositiva o del audio. Si el orador proporcionó detalles, explicaciones, ejemplos o datos en la transcripción, "
            "o si la diapositiva tiene textos importantes, fórmulas o clasificaciones que el borrador omitió, intégralos detalladamente.\n"
            "2. ESTILO DIRECTO: Elimina introducciones redundantes (ej. 'Esta diapositiva...', 'Como podemos ver...') "
            "y conclusiones o resúmenes repetitivos al final.\n"
            "3. MEJORA DE FORMATO: Mantén y optimiza el uso de Markdown (subtemas '###', negritas, listas).\n"
            "4. TABLAS: Asegúrate de que los datos estructurados, numéricos o clasificaciones se presenten en tablas de Markdown.\n"
            "5. ACLARACIÓN DE ERRORES (SILENCIOSA): Si detectas que el orador cometió una contradicción directa o error "
            "factual evidente con respecto a lo expuesto visualmente en la diapositiva, añade una sección final llamada '### Aclaración de Errores' "
            "explicando de forma neutral la corrección. Si el contenido de la transcripción y el borrador es correcto y "
            "coherente, NO agregues esta sección bajo ningún concepto (omítela por completo, no dejes títulos vacíos ni confirmaciones de éxito).\n\n"
            f"--- TRANSCRIPCIÓN ORIGINAL DEL ORADOR ---\n{transcript_text}\n\n"
            f"--- BORRADOR PREVIO ---\n{draft_text}\n\n"
            "Escribe directamente la explicación final depurada. No agregues preámbulos, explicaciones adicionales, "
            "ni comentarios del revisor. Solo la explicación final lista para el informe."
        )
        
        try:
            from PIL import Image
            contents = [prompt, Image.open(image_path)]
            response = self._generate_content_with_fallback(contents)
            return response.text.strip()
        except Exception as e:
            print(f"Error en Supervisor Gemini: {e}")
            return draft_text
