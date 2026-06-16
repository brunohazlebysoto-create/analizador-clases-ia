import os
import time
import re
from google import genai
from google.genai import types
from PIL import Image


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
        Llama a la API de Gemini con reintentos automáticos ante errores 503/429
        y fallback al modelo siguiente si el primero no responde.
        """
        models_to_try = ["gemini-2.0-flash", "gemini-1.5-flash"]
        last_exception = None

        for model_name in models_to_try:
            retries = 3
            delay = 2.0
            for attempt in range(retries):
                try:
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

                    if "exceeded your current quota" in err_msg_lower or "billing details" in err_msg_lower:
                        if "please retry in" in err_msg_lower:
                            delay = 60
                        else:
                            raise ValueError(
                                f"Has excedido tu cuota gratuita de la API de Gemini. "
                                f"Por favor, revisa tu plan en Google AI Studio.\n\nError: {err_msg}"
                            )

                    is_temporary = any(term in err_msg_lower for term in [
                        "503", "429", "resource_exhausted", "unavailable", "demand", "limit"
                    ])

                    if is_temporary and attempt < retries - 1:
                        print(f"Alta demanda en {model_name}. Reintentando en {delay}s...")
                        time.sleep(delay)
                        delay *= 2
                    else:
                        print(f"Falló llamada con {model_name}: {err_msg}")
                        break

        raise last_exception

    def synthesize_slide_batch(self, slides_batch):
        """
        Envía un lote de diapositivas a Gemini para generar explicaciones integradas.
        slides_batch: [{"id": int, "image_path": str, "transcript": str}, ...]
        Retorna: {slide_id: explanation_string}
        """
        if not self.is_configured():
            raise ValueError("API Key de Gemini no configurada.")

        prompt = (
            "Eres un asistente de apuntes de clase. Para cada diapositiva recibirás:\n"
            "- La imagen de la diapositiva (lo que estaba proyectado en pantalla)\n"
            "- La transcripción de lo que dijo el profesor mientras esa diapositiva estaba visible\n\n"
            "TU ÚNICA TAREA: Convertir la transcripción en apuntes escritos limpios y bien formateados. "
            "La imagen sirve para dos cosas únicamente: (1) recuperar datos visuales que el profesor mencionó "
            "pero no deletreó en voz alta (tablas, fórmulas, clasificaciones, listas), y (2) saber de qué "
            "tema estamos hablando para organizar mejor el formato.\n\n"
            "REGLAS ABSOLUTAS:\n"
            "1. NO RESUMIR: Cada punto que el profesor mencionó debe aparecer en los apuntes. No elimines "
            "nada por considerarlo redundante o secundario. Si el profesor lo dijo, va en los apuntes.\n"
            "2. SÍ LIMPIAR: Elimina muletillas ('eh', 'este', 'bueno'), repeticiones exactas involuntarias "
            "y falsos comienzos de frase. El contenido se queda; solo la forma oral se pule.\n"
            "3. DATOS VISUALES: Si la diapositiva tiene una tabla, fórmula, esquema o lista que el profesor "
            "explicó en voz alta, inclúyelos en los apuntes con formato Markdown (tablas, código, etc.).\n"
            "4. FORMATO: Usa subtítulos (###) cuando el profesor cambie de subtema. Usa negritas para "
            "términos técnicos la primera vez que aparecen. Listas cuando el profesor enumere cosas.\n"
            "5. VOZ NEUTRAL: Escribe en tercera persona o forma impersonal, no como 'el profesor dijo...'. "
            "Simplemente expón el contenido como apuntes directos.\n"
            "6. ACLARACIÓN DE ERRORES (SILENCIOSA): Si el profesor dijo algo que contradice directamente "
            "lo que muestra la imagen, añade al final '### Nota de Corrección' explicándolo brevemente. "
            "Si todo es coherente, omite esta sección completamente.\n\n"
            "FORMATO DE SALIDA OBLIGATORIO — separa cada diapositiva con:\n"
            "===DIAPOSITIVA_ID_X===\n"
            "Repite para cada diapositiva del lote."
        )

        contents = [prompt]
        for slide in slides_batch:
            slide_id = slide["id"]
            contents.append(f"\n\n--- DATOS DE LA DIAPOSITIVA {slide_id} ---")
            contents.append(Image.open(slide["image_path"]))
            contents.append(f"\nTranscripción del orador durante la Diapositiva {slide_id}:\n{slide['transcript']}\n")

        config = types.GenerateContentConfig(temperature=0.2)
        response = self._generate_content_with_fallback(contents=contents, config=config)

        results = {}
        parts = re.split(r'===DIAPOSITIVA_ID_(\d+)===', response.text)

        for i in range(1, len(parts), 2):
            try:
                s_id = int(parts[i])
                s_content = parts[i + 1].strip()
                results[s_id] = s_content
            except (ValueError, IndexError):
                pass

        for slide in slides_batch:
            if slide["id"] not in results:
                results[slide["id"]] = "Error: El modelo de IA no generó una respuesta estructurada para esta diapositiva."

        return results

    def supervise_and_edit_text(self, image_path, draft_text, transcript_text):
        """
        Agente Supervisor: revisa el borrador contra la imagen y la transcripción,
        corrige omisiones y produce la versión final lista para el informe.
        """
        if not self.is_configured():
            return draft_text

        prompt = (
            "Eres el Revisor de Apuntes. Tienes delante un borrador de apuntes de clase, "
            "la transcripción original del profesor y la imagen de la diapositiva.\n\n"
            "TU TRABAJO: Verificar que los apuntes capturen TODO lo que el profesor dijo "
            "y corregir si algo falta o sobra. Luego devolver la versión final.\n\n"
            "CHECKLIST DE REVISIÓN:\n"
            "1. COMPLETITUD: Compara el borrador con la transcripción línea a línea. "
            "¿Hay algún punto que el profesor mencionó que no está en el borrador? Si falta, agrégalo. "
            "No elimines nada del borrador a menos que sea una repetición exacta.\n"
            "2. DATOS VISUALES: Mira la imagen. ¿Hay tablas, fórmulas o listas en la diapositiva "
            "que el profesor explicó y que no están en los apuntes? Inclúyelos.\n"
            "3. LIMPIEZA ORAL: ¿Quedaron muletillas o fragmentos de frases incompletas del habla? "
            "Elimínalos sin quitar contenido.\n"
            "4. FRASES INDESEADAS: Si el borrador dice 'la diapositiva muestra...', 'el profesor dijo...', "
            "'según la transcripción...', reescribe esas frases como apuntes directos sin atribuir la fuente.\n"
            "5. NOTA DE CORRECCIÓN (SILENCIOSA): Solo si el profesor afirmó algo que contradice "
            "directamente lo que está en la imagen, añade al final '### Nota de Corrección'. "
            "Si todo es coherente, no añadas ninguna sección extra.\n\n"
            f"--- TRANSCRIPCIÓN ORIGINAL ---\n{transcript_text}\n\n"
            f"--- BORRADOR ---\n{draft_text}\n\n"
            "Devuelve directamente los apuntes finales corregidos, sin introducción ni comentarios."
        )

        try:
            contents = [prompt, Image.open(image_path)]
            response = self._generate_content_with_fallback(contents)
            return response.text.strip()
        except Exception as e:
            print(f"Error en Supervisor Gemini: {e}")
            return draft_text
