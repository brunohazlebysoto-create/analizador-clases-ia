---
title: Analizador de Clases IA
emoji: 🎓
colorFrom: blue
colorTo: cyan
sdk: streamlit
sdk_version: 1.41.0
app_file: app.py
pinned: false
license: mit
---

# Analizador de Clases IA

Sube un video de clase y obtén automáticamente:

- **Pantallazos** de cada diapositiva detectada
- **Apuntes completos** por diapositiva (imagen + lo explicado por el profesor, sin repetir)
- **Reporte Word (.docx)** listo para descargar

## Cómo usar

1. Introduce tu **Groq API Key** (transcripción de audio con Whisper)
2. Introduce tu **Gemini API Key** (análisis visual y generación de apuntes)
3. Sube el video de clase (MP4, AVI, MOV, MKV, WebM)
4. Ajusta la sensibilidad de detección si es necesario
5. Pulsa **Iniciar Procesamiento**

## APIs necesarias

- [Groq](https://console.groq.com) — gratis, para transcripción con Whisper Large V3
- [Google AI Studio](https://aistudio.google.com) — gratis, para análisis con Gemini 2.0 Flash
