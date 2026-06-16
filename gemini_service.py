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
            "Eres un asistente de apuntes de clase. Para cada diapositiva recibirás la imagen "
            "y la transcripción del profesor. Tu tarea es producir apuntes completos (z) siguiendo "
            "esta lógica:\n\n"
            "FUENTES:\n"
            "  x = todo el texto, datos, fórmulas, tablas y esquemas visibles en la imagen\n"
            "  y = todo lo que el profesor dijo en la transcripción\n"
            "  z (tu output) = apuntes donde cada punto aparece UNA SOLA VEZ, completo\n\n"
            "REGLA DE ORO — FUSIÓN SIN DUPLICACIÓN:\n"
            "- Si un concepto aparece tanto en x como en y (el profesor explicó algo que ya estaba "
            "en la slide): escríbelo UNA vez, usando la explicación del profesor para enriquecer "
            "el dato de la slide. No repitas el mismo punto dos veces.\n"
            "- Si algo está en x pero el profesor no lo mencionó: inclúyelo igual en los apuntes.\n"
            "- Si el profesor dijo algo que no estaba en la slide: inclúyelo igual en los apuntes.\n"
            "El resultado debe ser que un alumno que no fue a clase pueda aprender todo leyendo z, "
            "sin necesidad de ver la imagen ni escuchar el audio.\n\n"
            "REGLAS DE FORMATO:\n"
            "- Usa ### para subtemas cuando el profesor cambie de punto o la slide tenga secciones.\n"
            "- Negritas para términos técnicos la primera vez que aparecen.\n"
            "- Tablas de Markdown para clasificaciones, comparaciones o datos numéricos.\n"
            "- NO escribas frases como 'la diapositiva muestra...', 'el profesor dijo...', "
            "'según la imagen...'. Los apuntes son directos.\n"
            "- NO resumir: si el profesor dio un ejemplo, va. Si dio tres sub-puntos, van los tres.\n\n"
            "NOTA DE CORRECCIÓN (SILENCIOSA): Solo si el profesor afirmó algo que contradice "
            "directamente lo visible en la imagen, añade al final '### Nota de Corrección' con "
            "la aclaración. Si todo es coherente, omite esta sección completamente.\n\n"
            "FORMATO DE SALIDA — separa cada diapositiva con:\n"
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
            "Eres el Revisor de Apuntes. Revisa el borrador usando tres fuentes: "
            "la transcripción original, la imagen de la diapositiva y el borrador.\n\n"
            "CHECKLIST — revisa en este orden:\n\n"
            "1. ¿Hay algo en la TRANSCRIPCIÓN que no está en el borrador?\n"
            "   → Agrégalo en el lugar conceptual correcto. No resumas ni omitas.\n\n"
            "2. ¿Hay texto, tablas, fórmulas o datos en la IMAGEN que no están en el borrador?\n"
            "   → Inclúyelos. El texto de la diapositiva que el profesor no leyó en voz alta "
            "también debe estar en los apuntes.\n\n"
            "3. ¿Hay puntos DUPLICADOS? (mismo concepto aparece dos veces: una del slide y otra "
            "de la transcripción)\n"
            "   → Fusiónalos en UNO: el dato de la slide + la explicación del profesor = una sola "
            "entrada completa. Elimina la repetición.\n\n"
            "4. ¿Quedaron frases del tipo 'la diapositiva muestra...', 'el profesor dijo...'?\n"
            "   → Reescríbelas como apuntes directos sin atribuir la fuente.\n\n"
            "5. ¿Quedaron muletillas o fragmentos orales incompletos?\n"
            "   → Elimínalos sin quitar contenido.\n\n"
            "NOTA DE CORRECCIÓN (SILENCIOSA): Solo si el profesor afirmó algo que contradice "
            "directamente la imagen, añade '### Nota de Corrección' al final. Si todo es "
            "coherente, omite esta sección.\n\n"
            f"--- TRANSCRIPCIÓN ORIGINAL ---\n{transcript_text}\n\n"
            f"--- BORRADOR ---\n{draft_text}\n\n"
            "Devuelve directamente los apuntes finales. Sin introducción ni comentarios del revisor."
        )

        try:
            contents = [prompt, Image.open(image_path)]
            response = self._generate_content_with_fallback(contents)
            return response.text.strip()
        except Exception as e:
            print(f"Error en Supervisor Gemini: {e}")
            return draft_text
