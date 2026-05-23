import os
import streamlit as st
import tempfile
import time
from video_processor import VideoProcessor, format_timestamp
from groq_service import GroqService
from exporter import create_word_report
from dotenv import load_dotenv

# Cargar variables de entorno si existen
load_dotenv()

# Configuración de la página
st.set_page_config(
    page_title="Analizador de Clases con IA",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Estilos CSS personalizados para una estética Premium (Glassmorphism, sombras suaves y degradados)
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;700&display=swap');
    
    /* Configuración de tipografía global */
    html, body, [class*="css"] {
        font-family: 'Outfit', sans-serif;
    }
    
    /* Encabezado principal animado */
    .title-container {
        background: linear-gradient(135deg, #1e3a8a 0%, #3b82f6 50%, #06b6d4 100%);
        padding: 40px;
        border-radius: 20px;
        color: white;
        text-align: center;
        margin-bottom: 30px;
        box-shadow: 0 10px 25px rgba(59, 130, 246, 0.2);
    }
    .title-container h1 {
        font-weight: 700;
        font-size: 3rem;
        margin: 0;
        letter-spacing: -0.5px;
    }
    .title-container p {
        font-weight: 300;
        font-size: 1.2rem;
        margin-top: 10px;
        opacity: 0.9;
    }
    
    /* Estilo de tarjetas de diapositivas (Glassmorphism) */
    .slide-card {
        background: rgba(255, 255, 255, 0.08);
        backdrop-filter: blur(10px);
        -webkit-backdrop-filter: blur(10px);
        border: 1px solid rgba(255, 255, 255, 0.15);
        border-radius: 16px;
        padding: 24px;
        margin-bottom: 25px;
        box-shadow: 0 8px 32px 0 rgba(31, 38, 135, 0.07);
        transition: transform 0.2s ease, box-shadow 0.2s ease;
    }
    .slide-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 12px 40px 0 rgba(31, 38, 135, 0.12);
        border: 1px solid rgba(59, 130, 246, 0.3);
    }
    
    /* Etiquetas del timestamp */
    .timestamp-badge {
        background: linear-gradient(90deg, #1e3a8a 0%, #3b82f6 100%);
        color: white;
        padding: 4px 12px;
        border-radius: 20px;
        font-size: 0.85rem;
        font-weight: 600;
        display: inline-block;
        margin-bottom: 12px;
    }
    
    /* Botones principales */
    div.stButton > button:first-child {
        background: linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%);
        color: white;
        font-weight: 600;
        padding: 12px 24px;
        border-radius: 10px;
        border: none;
        box-shadow: 0 4px 15px rgba(37, 99, 235, 0.3);
        transition: all 0.3s ease;
        width: 100%;
    }
    div.stButton > button:first-child:hover {
        background: linear-gradient(135deg, #1d4ed8 0%, #1e40af 100%);
        box-shadow: 0 6px 20px rgba(29, 78, 216, 0.4);
        transform: translateY(-1px);
    }
</style>
""", unsafe_allow_html=True)

# Título y Banner Superior
st.markdown("""
<div class="title-container">
    <h1>Analizador de Videos de Clases 🎓</h1>
    <p>Extrae diapositivas automáticamente y genera reportes inteligentes unificando imagen y voz con IA</p>
</div>
""", unsafe_allow_html=True)

# Inicializar estados de sesión
if "processed" not in st.session_state:
    st.session_state.processed = False
if "slides_data" not in st.session_state:
    st.session_state.slides_data = None
if "report_title" not in st.session_state:
    st.session_state.report_title = "Reporte de Clase"
if "docx_path" not in st.session_state:
    st.session_state.docx_path = None
if "error_message" not in st.session_state:
    st.session_state.error_message = None
if "processing" not in st.session_state:
    st.session_state.processing = False

# Sidebar - Configuración y API Key
with st.sidebar:
    st.header("⚙️ Configuración")
    
    # API Key de Groq (Transcripción)
    groq_api_key_env = os.getenv("GROQ_API_KEY", "")
    groq_api_key_input = st.text_input(
        "Groq API Key (Para Transcripción Rápida)", 
        value=groq_api_key_env, 
        type="password",
        help="Introduce tu clave de API de Groq para habilitar la transcripción súper rápida del audio."
    )

    # API Key de Gemini (Visión e Inteligencia)
    gemini_api_key_env = os.getenv("GEMINI_API_KEY", "")
    gemini_api_key_input = st.text_input(
        "Gemini API Key (Para Análisis Visual sin alucinaciones)", 
        value=gemini_api_key_env, 
        type="password",
        help="Introduce tu clave de API de Gemini para habilitar el análisis de las imágenes con alta precisión clínica."
    )
    
    st.divider()
    
    st.subheader("⚡ Modo de Procesamiento")
    is_turbo_mode = st.toggle(
        "Modo Turbo (Sin esperas)", 
        value=False,
        help="Si lo activas, el video se procesará sin pausas (requiere una API Key con facturación habilitada o límites altos). Si está desactivado, el sistema hará pausas estratégicas de 5s para no exceder los límites de la API Key Gratuita."
    )
    
    st.divider()
    
    st.subheader("Sensibilidad de Detección")
    
    threshold = st.slider(
        "Umbral de cambio (sensibilidad)", 
        min_value=5.0, 
        max_value=30.0, 
        value=10.0, 
        step=0.5,
        help="Valores más bajos detectan más cambios (más sensible). Valores más altos ignoran pequeños movimientos."
    )
    
    min_duration = st.slider(
        "Duración mínima de diapositiva (segundos)", 
        min_value=2, 
        max_value=30, 
        value=5, 
        help="Evita guardar frames de transiciones rápidas o de diapositivas que duraron muy poco."
    )
    
    sample_interval = st.slider(
        "Intervalo de muestreo (segundos)", 
        min_value=0.5, 
        max_value=5.0, 
        value=1.0, 
        step=0.5,
        help="Cada cuántos segundos se captura un frame para analizar. Menos segundos es más preciso pero más lento."
    )

# Cuerpo principal
col_upload, col_settings = st.columns([2, 1])

# Carga de video primero para poder inferir el nombre por defecto
with col_upload:
    st.subheader("🎥 Seleccionar Video")
    uploaded_file = st.file_uploader(
        "Arrastra y suelta tu archivo de video de clase", 
        type=["mp4", "avi", "mov", "mkv", "webm"],
        help="Formatos recomendados: MP4 o WebM"
    )

# Determinar el título por defecto
default_title = "Reporte de Clase - Análisis Automatizado"
if uploaded_file is not None:
    video_base_name = os.path.splitext(uploaded_file.name)[0]
    default_title = video_base_name.replace("_", " ").replace("-", " ").strip().title()

with col_settings:
    st.subheader("📄 Datos del Reporte")
    report_title = st.text_input("Título del Reporte Word", value=default_title)

if uploaded_file is not None:
    # Mostrar reproductor de video
    st.video(uploaded_file)
    
    # Botón para iniciar el análisis
    button_clicked = st.button("Iniciar Procesamiento y Análisis 🚀")
    
    if button_clicked:
        if not groq_api_key_input or not gemini_api_key_input:
            st.error("Por favor, introduce las API Keys de Groq y de Gemini válidas en la barra lateral.")
        else:
            st.session_state.processing = True
            st.session_state.report_title = report_title
            st.session_state.processed = False
            st.session_state.error_message = None
            st.session_state.slides_data = None
            st.session_state.docx_path = None
            st.rerun()

    # Mostrar error si existe de un intento anterior
    if st.session_state.error_message:
        st.error(st.session_state.error_message)

    # Si el procesamiento está activo, ejecutarlo
    if st.session_state.processing:
        try:
            # Crear carpetas temporales para el procesamiento
            temp_dir = tempfile.mkdtemp()
            video_path = os.path.join(temp_dir, uploaded_file.name)
            
            with open(video_path, "wb") as f:
                f.write(uploaded_file.getbuffer())
                
            # Inicializar variables de tiempo de procesamiento usando un diccionario mutable para evitar errores de ámbito nonlocal
            times = {
                "start": time.time(),
                "step1_start": time.time(),
                "step2_start": None,
                "step3_start": None,
                "step4_start": None,
                "step1_actual": None,
                "step2_actual": None,
                "step3_actual": None
            }
            
            # Inicializar procesador para obtener duración de video
            slides_output_dir = os.path.join(temp_dir, "extracted_slides")
            processor = VideoProcessor(video_path, output_dir=slides_output_dir)
            video_info = processor.get_video_info()
            video_duration = video_info["duration"]
            
            # Crear la interfaz del panel de control de progreso
            st.write("---")
            st.markdown("### 📊 Panel de Control y Progreso en Tiempo Real")
            
            # Contenedor con estilo premium de cristal y degradado sutil
            st.markdown("""
            <div style="background: linear-gradient(135deg, rgba(37, 99, 235, 0.05) 0%, rgba(6, 182, 212, 0.05) 100%); border: 1px solid rgba(37, 99, 235, 0.15); border-radius: 12px; padding: 20px; box-shadow: 0 4px 12px rgba(0,0,0,0.05); margin-bottom: 25px;">
            """, unsafe_allow_html=True)
            
            step_status_placeholder = st.empty()
            
            total_text_placeholder = st.empty()
            total_progress_placeholder = st.empty()
            
            step_text_placeholder = st.empty()
            step_progress_placeholder = st.empty()
            
            time_metrics_placeholder = st.empty()
            
            st.markdown("</div>", unsafe_allow_html=True)
            
            # Variable compartida de diapositivas para que la estimación sea precisa
            slides_data = None
            
            def format_duration(seconds):
                if seconds is None or seconds < 0:
                    return "Calculando..."
                m = int(seconds // 60)
                s = int(seconds % 60)
                return f"{m:02d}:{s:02d}"

            def update_dashboard(step_idx, step_progress, status_message):
                # Registrar tiempos de inicio reales si se cambia de paso
                now = time.time()
                if step_idx == 1:
                    pass
                elif step_idx == 2 and times["step2_start"] is None:
                    times["step2_start"] = now
                    times["step1_actual"] = now - times["step1_start"]
                elif step_idx == 3 and times["step3_start"] is None:
                    times["step3_start"] = now
                    if times["step2_start"] is not None:
                        times["step2_actual"] = now - times["step2_start"]
                    else:
                        times["step2_actual"] = 30.0 # fallback
                elif step_idx == 4 and times["step4_start"] is None:
                    times["step4_start"] = now
                    if times["step3_start"] is not None:
                        times["step3_actual"] = now - times["step3_start"]
                    else:
                        times["step3_actual"] = 30.0 # fallback
                
                # Calcular progreso total ponderado
                if step_idx == 1:
                    total_progress = step_progress * 0.30
                elif step_idx == 2:
                    total_progress = 0.30 + (step_progress * 0.30)
                elif step_idx == 3:
                    total_progress = 0.60 + (step_progress * 0.35)
                elif step_idx == 4:
                    total_progress = 0.95 + (step_progress * 0.05)
                else:
                    total_progress = 1.0
                    
                total_progress = min(1.0, max(0.0, total_progress))
                
                # Tiempo transcurrido
                elapsed = now - times["start"]
                
                # Estimar duración total del proceso
                est_total = 0.0
                if step_idx == 1:
                    # Paso 1: Extracción de diapositivas
                    if step_progress > 0.01:
                        est_step1 = elapsed / step_progress
                    else:
                        est_step1 = video_duration * 0.05
                    est_step2 = 25.0 + video_duration * 0.01
                    est_step3 = max(3, video_duration / 45) * 4.5
                    est_step4 = 1.0
                    est_total = est_step1 + est_step2 + est_step3 + est_step4
                elif step_idx == 2:
                    # Paso 2: Audio y Transcripción
                    elapsed_in_step2 = now - times["step2_start"]
                    if step_progress > 0.01:
                        est_step2 = elapsed_in_step2 / step_progress
                    else:
                        est_step2 = 25.0 + video_duration * 0.01
                    if slides_data:
                        est_step3 = len(slides_data) * 4.5
                    else:
                        est_step3 = max(3, video_duration / 45) * 4.5
                    est_step4 = 1.0
                    est_total = times["step1_actual"] + est_step2 + est_step3 + est_step4
                elif step_idx == 3:
                    # Paso 3: Síntesis con Gemini
                    elapsed_in_step3 = now - times["step3_start"]
                    if step_progress > 0.01:
                        est_step3 = elapsed_in_step3 / step_progress
                    else:
                        est_step3 = len(slides_data) * 4.5
                    est_step4 = 1.0
                    est_total = times["step1_actual"] + times["step2_actual"] + est_step3 + est_step4
                elif step_idx == 4:
                    # Paso 4: Exportación
                    est_total = times["step1_actual"] + times["step2_actual"] + times["step3_actual"] + 1.0
                
                remaining = max(0.0, est_total - elapsed)
                if total_progress >= 1.0:
                    remaining = 0.0
                
                # Actualizar los elementos de Streamlit
                step_status_placeholder.markdown(f"### {status_message}")
                total_text_placeholder.markdown(f"**Progreso General: {int(total_progress * 100)}%**")
                total_progress_placeholder.progress(total_progress)
                
                step_text_placeholder.markdown(f"**Progreso del Paso: {int(step_progress * 100)}%**")
                step_progress_placeholder.progress(step_progress)
                
                time_metrics_placeholder.markdown(
                    f"""
                    <div style="display: flex; justify-content: space-between; font-size: 0.95rem; color: #1e3a8a; margin-top: 10px;">
                        <span>⏱️ <b>Tiempo Transcurrido:</b> {format_duration(elapsed)}</span>
                        <span>⏳ <b>Tiempo Restante Estimado (ETA):</b> {format_duration(remaining)}</span>
                    </div>
                    """,
                    unsafe_allow_html=True
                )

            # Paso 1: Extracción de Slides
            def step1_callback(val):
                update_dashboard(step_idx=1, step_progress=val, status_message="🔄 Paso 1 de 4: Analizando estructura del video y extrayendo diapositivas...")
                
            # Extraer diapositivas
            slides_data = processor.extract_slides(
                threshold=threshold,
                min_slide_duration=min_duration,
                sample_interval=sample_interval,
                progress_callback=step1_callback
            )
            
            update_dashboard(step_idx=1, step_progress=1.0, status_message=f"✅ Paso 1 Completado: Se detectaron {len(slides_data)} diapositivas estables.")
            time.sleep(1)
            
            if not slides_data:
                st.warning("No se detectaron diapositivas estables. Intenta bajar el umbral de cambio.")
                st.session_state.processing = False
                st.rerun()
            else:
                # Galería visual inicial de diapositivas extraídas
                st.write("### Diapositivas detectadas:")
                cols = st.columns(min(len(slides_data), 4))
                for idx, slide in enumerate(slides_data):
                    with cols[idx % 4]:
                        st.image(
                            slide["image_path"], 
                            caption=f"Diapositiva {slide['id']} ({format_timestamp(slide['start_time'])})"
                        )
                
                # Paso 2: Audio y Transcripción (Con Groq Whisper - Rápido)
                update_dashboard(step_idx=2, step_progress=0.0, status_message="🔄 Paso 2 de 4: Iniciando extracción de audio...")
                from groq_service import GroqService
                groq_svc = GroqService(api_key=groq_api_key_input)
                
                audio_path = os.path.join(temp_dir, "audio.mp3")
                groq_svc.extract_audio(video_path, audio_path)
                
                update_dashboard(step_idx=2, step_progress=0.1, status_message="🔄 Paso 2 de 4: Audio extraído. Subiendo a Groq Whisper...")
                
                def transcribe_callback(step_val, msg):
                    adjusted_progress = 0.1 + (step_val * 0.9)
                    update_dashboard(step_idx=2, step_progress=adjusted_progress, status_message=f"🔄 Paso 2 de 4: {msg}")
                
                transcript_segments = groq_svc.transcribe_audio(audio_path, progress_callback=transcribe_callback)
                update_dashboard(step_idx=2, step_progress=1.0, status_message="✅ Paso 2 Completado: Transcripción de audio ultra-rápida exitosa.")
                time.sleep(1)
                
                # Paso 3: Sincronizar y Sintetizar (Con Gemini Vision Batch - Sin alucinaciones)
                update_dashboard(step_idx=3, step_progress=0.0, status_message="🔄 Paso 3 de 4: Preparando lotes para Google Gemini...")
                from gemini_service import GeminiService
                gemini_svc = GeminiService(api_key=gemini_api_key_input)
                
                # Preparar datos
                for slide in slides_data:
                    # Filtrar segmentos de texto que correspondan al tiempo de la diapositiva
                    slide_transcript_parts = []
                    for seg in transcript_segments:
                        if not (seg["end"] < slide["start_time"] or seg["start"] > slide["end_time"]):
                            slide_transcript_parts.append(seg["text"])
                            
                    slide_transcript = " ".join(slide_transcript_parts)
                    if not slide_transcript.strip():
                        slide_transcript = "[El orador no habló o hubo silencio durante esta diapositiva]"
                    slide["transcript"] = slide_transcript
                    slide["explanation"] = "" # Inicializar

                batch_size = 5
                total_batches = (len(slides_data) + batch_size - 1) // batch_size
                
                for i in range(0, len(slides_data), batch_size):
                    batch = slides_data[i:i+batch_size]
                    batch_idx = (i // batch_size) + 1
                    
                    update_dashboard(
                        step_idx=3, 
                        step_progress=(batch_idx - 1) / total_batches, 
                        status_message=f"🔄 Paso 3 de 4: Gemini analizando Lote {batch_idx} de {total_batches} diapositivas (Evitando alucinaciones)..."
                    )
                    
                    batch_results = gemini_svc.synthesize_slide_batch(batch)
                    
                    # Asignar y supervisar con Gemini
                    for idx, slide in enumerate(batch):
                        raw_explanation = batch_results.get(slide["id"], "Error: No se pudo generar explicación para esta diapositiva.")
                        
                        # Progreso detallado dentro del lote (de 50% a 100% del lote)
                        progress_in_batch = 0.5 + (idx / len(batch)) * 0.5
                        step_progress_val = ((batch_idx - 1) / total_batches) + (progress_in_batch / total_batches)
                        
                        update_dashboard(
                            step_idx=3, 
                            step_progress=step_progress_val, 
                            status_message=f"🔍 Agente Supervisor (Gemini) auditando y refinando Diapositiva {slide['id']}..."
                        )
                        
                        # El Agente 2 (Gemini Supervisor) realiza la supervisión y edición multimodal directa
                        refined_explanation = gemini_svc.supervise_and_edit_text(slide["image_path"], raw_explanation, slide["transcript"])
                        slide["explanation"] = refined_explanation
                        
                    # Pausa estratégica de 5 segundos solo si está en modo gratis
                    if not is_turbo_mode and batch_idx < total_batches:
                        time.sleep(5)
                        
                update_dashboard(step_idx=3, step_progress=1.0, status_message="✅ Paso 3 Completado: Análisis y Síntesis de Diapositivas finalizado.")
                time.sleep(1)
                
                # Guardar en sesión
                st.session_state.slides_data = slides_data
                st.session_state.report_title = report_title
                
                # Paso 4: Generar reporte Word
                update_dashboard(step_idx=4, step_progress=0.0, status_message="🔄 Paso 4 de 4: Generando archivo Word (.docx)...")
                
                video_base_name = os.path.splitext(uploaded_file.name)[0]
                docx_output_name = f"{video_base_name}.docx"
                docx_path = os.path.join(temp_dir, docx_output_name)
                
                create_word_report(
                    slides_data, 
                    class_title=report_title, 
                    output_filename=docx_path
                )
                
                update_dashboard(step_idx=4, step_progress=1.0, status_message="✅ Paso 4 Completado: ¡Archivo Word generado con éxito!")
                time.sleep(1)
                
                st.session_state.docx_path = docx_path
                st.session_state.processed = True
                st.session_state.processing = False
                st.rerun()
                
        except Exception as e:
            import traceback
            error_trace = traceback.format_exc()
            st.session_state.error_message = f"❌ Ocurrió un error durante el procesamiento: {str(e)}\n\n{error_trace}"
            st.session_state.processing = False
            st.rerun()

# Mostrar resultados si ya se procesaron
if st.session_state.processed and st.session_state.slides_data:
    st.divider()
    st.header("📊 Reporte Generado")
    
    # Botón de descarga del Word
    if st.session_state.docx_path and os.path.exists(st.session_state.docx_path):
        with open(st.session_state.docx_path, "rb") as f:
            st.download_button(
                label="📥 Descargar Reporte Completo en Word (.docx)",
                data=f,
                file_name=f"{st.session_state.report_title}.docx",
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            )
            
    st.write("---")
    
    # Mostrar resultados en pantalla
    for slide in st.session_state.slides_data:
        start_str = format_timestamp(slide["start_time"])
        end_str = format_timestamp(slide["end_time"])
        
        # Estructura visual de dos columnas en Streamlit
        st.markdown(f"""
        <div class="slide-card">
            <h3>Diapositiva {slide['id']} <span class="timestamp-badge">{start_str} - {end_str}</span></h3>
        </div>
        """, unsafe_allow_html=True)
        
        col_img, col_txt = st.columns([1, 1])
        with col_img:
            st.image(slide["image_path"], use_container_width=True)
        with col_txt:
            st.markdown("##### Explicación Integrada:")
            st.markdown(slide["explanation"])
        st.write("")
