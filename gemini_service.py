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
            "Eres un experto académico. Tu tarea es procesar un LOTE de diapositivas de clase y generar "
            "una explicación unificada para cada una.\n\n"
            "CONCEPTO CLAVE DE TU TRABAJO:\n"
            "Recibirás dos fuentes de información por diapositiva: la imagen (esqueleto visual con títulos, "
            "esquemas, datos) y la transcripción del orador (la carne: el profesor ampliando, ejemplificando "
            "y explicando cada punto). Tu trabajo NO es reproducir ambas por separado. Tu trabajo es "
            "SINTETIZARLAS en una sola explicación coherente, como si fueras el mejor alumno de la clase "
            "escribiendo sus apuntes: los conceptos de la diapositiva enriquecidos con todo lo que el "
            "profesor dijo sobre ellos, en una narrativa fluida y única.\n\n"
            "REGLAS ESTRICTAS:\n"
            "1. PROHIBIDO separar fuentes: NO escribas 'la diapositiva muestra...', 'el orador dijo...', "
            "'según la imagen...', 'según la transcripción...'. La explicación debe fluir como si todo "
            "viniera de una sola voz experta.\n"
            "2. SÍNTESIS REAL: Los títulos y bullets de la diapositiva son los temas a cubrir. La "
            "transcripción contiene la explicación profunda de esos temas. Únelos: expande cada concepto "
            "visual con la explicación verbal del profesor.\n"
            "3. COMPLETITUD: No omitas datos de valor. Fórmulas, nombres, cifras, ejemplos clínicos, "
            "casos prácticos y clasificaciones deben estar en la explicación final.\n"
            "4. FIDELIDAD: No inventes ni extrapolues. Si el profesor no mencionó algo, no lo agregues.\n"
            "5. FORMATO: Usa subtítulos (###) para los conceptos principales, negritas para términos clave, "
            "y tablas de Markdown para datos comparativos o clasificaciones.\n"
            "6. ACLARACIÓN DE ERRORES (SILENCIOSA): Añade '### Aclaración de Errores' SOLO si detectas "
            "una contradicción directa entre lo visual y lo verbal. Si todo es coherente, omite esta "
            "sección completamente, sin dejar títulos vacíos.\n\n"
            "FORMATO DE SALIDA OBLIGATORIO:\n"
            "Separa cada diapositiva con el marcador exacto:\n"
            "===DIAPOSITIVA_ID_X===\n"
            "Donde X es el ID de la diapositiva. Repite para cada una."
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
            "Eres el Agente Supervisor Académico. Recibirás un borrador de apuntes de clase, "
            "la imagen original de la diapositiva y la transcripción del orador. Tu trabajo es "
            "detectar si el borrador VERDADERAMENTE unifica ambas fuentes o si simplemente las repite "
            "por separado, y producir la versión final correcta.\n\n"
            "LO QUE DEBES DETECTAR Y CORREGIR:\n"
            "A) SEPARACIÓN DE FUENTES: Si el borrador dice frases como 'la diapositiva muestra...', "
            "'el profesor mencionó...', 'según la imagen...', 'la transcripción indica...', REESCRIBE "
            "esas partes fusionando el concepto visual con la explicación verbal en una sola voz.\n"
            "B) INFORMACIÓN OMITIDA: Si la imagen contiene datos, fórmulas, clasificaciones o esquemas "
            "que el borrador no desarrolló, intégralos. Si el orador dio ejemplos, cifras o aclaraciones "
            "que no están en el borrador, añádelos en el lugar conceptual correcto.\n"
            "C) REDUNDANCIA: Si el borrador repite la misma idea dos veces (una de la imagen y otra de "
            "la transcripción), unifica en una sola exposición más rica.\n"
            "D) FORMATO: Subtítulos (###) para conceptos principales, negritas para términos clave, "
            "tablas de Markdown para datos comparativos. Elimina introducciones vacías.\n"
            "E) ACLARACIÓN DE ERRORES (SILENCIOSA): Solo si hay contradicción directa entre imagen y "
            "transcripción, añade '### Aclaración de Errores'. Si todo es coherente, omite esta sección.\n\n"
            f"--- TRANSCRIPCIÓN ORIGINAL ---\n{transcript_text}\n\n"
            f"--- BORRADOR A REVISAR ---\n{draft_text}\n\n"
            "Escribe directamente los apuntes finales. Sin preámbulos ni comentarios del revisor."
        )

        try:
            contents = [prompt, Image.open(image_path)]
            response = self._generate_content_with_fallback(contents)
            return response.text.strip()
        except Exception as e:
            print(f"Error en Supervisor Gemini: {e}")
            return draft_text
