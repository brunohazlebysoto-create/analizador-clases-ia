import os
import cv2
import numpy as np
from PIL import Image


def format_timestamp(seconds):
    """Convierte segundos a formato hh:mm:ss"""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def is_black_image(image_path, brightness_threshold=15.0, std_threshold=10.0):
    """
    Determina si una imagen es mayormente negra o vacía de transición.
    Usa el promedio y la desviación estándar de la escala de grises.
    """
    img = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
    if img is None:
        return True
    mean_val = np.mean(img)
    std_val = np.std(img)

    if mean_val < brightness_threshold:
        return True
    if std_val < std_threshold and mean_val < 30.0:
        return True
    return False


def are_images_similar(img1, img2, similarity_threshold=12.0, block_match_ratio=0.85):
    """
    Compara dos imágenes en escala de grises usando división por bloques (8x8)
    para ser tolerante a movimientos parciales del orador.
    """
    if img1 is None or img2 is None:
        return False

    img1_res = cv2.resize(img1, (320, 180))
    img2_res = cv2.resize(img2, (320, 180))

    global_diff = np.mean(cv2.absdiff(img1_res, img2_res))
    if global_diff < similarity_threshold * 0.7:
        return True

    rows, cols = 8, 8
    h, w = img1_res.shape
    bh, bw = h // rows, w // cols

    matching_blocks = 0
    total_blocks = rows * cols

    for r in range(rows):
        for c in range(cols):
            block1 = img1_res[r*bh:(r+1)*bh, c*bw:(c+1)*bw]
            block2 = img2_res[r*bh:(r+1)*bh, c*bw:(c+1)*bw]
            if np.mean(cv2.absdiff(block1, block2)) < similarity_threshold:
                matching_blocks += 1

    return (matching_blocks / total_blocks) >= block_match_ratio


class VideoProcessor:
    def __init__(self, video_path, output_dir="extracted_slides"):
        self.video_path = video_path
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)

    def get_video_info(self):
        """Obtiene información básica del video"""
        cap = cv2.VideoCapture(self.video_path)
        if not cap.isOpened():
            raise ValueError(f"No se pudo abrir el video: {self.video_path}")

        try:
            fps = cap.get(cv2.CAP_PROP_FPS)
            frame_count = cap.get(cv2.CAP_PROP_FRAME_COUNT)
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            duration = frame_count / fps if fps > 0 else 0
        finally:
            cap.release()

        return {
            "fps": fps,
            "frame_count": frame_count,
            "width": width,
            "height": height,
            "duration": duration
        }

    def extract_slides(self, threshold=10.0, min_slide_duration=5.0, sample_interval=1.0, progress_callback=None):
        """
        Extrae las diapositivas del video.

        - threshold: Umbral de diferencia media de píxeles para detectar cambio (0-255).
        - min_slide_duration: Duración mínima en segundos de una diapositiva para considerarla válida.
        - sample_interval: Cada cuántos segundos muestrear el video.
        - progress_callback: Función para reportar progreso.
        """
        cap = cv2.VideoCapture(self.video_path)
        if not cap.isOpened():
            raise ValueError(f"No se pudo abrir el video: {self.video_path}")

        # Obtener duración del cap ya abierto (evita abrir el video dos veces)
        fps = cap.get(cv2.CAP_PROP_FPS)
        frame_count = cap.get(cv2.CAP_PROP_FRAME_COUNT)
        duration = frame_count / fps if fps > 0 else 0

        slides = []
        last_saved_frame_gray = None
        last_saved_timestamp = 0.0

        # Limpiar carpeta de salida
        for file in os.listdir(self.output_dir):
            if file.endswith(('.png', '.jpg', '.jpeg')):
                try:
                    os.remove(os.path.join(self.output_dir, file))
                except Exception:
                    pass

        t = 0.0
        slide_count = 0

        try:
            while t < duration:
                if progress_callback:
                    progress_callback(t / duration)

                cap.set(cv2.CAP_PROP_POS_MSEC, int(t * 1000))
                ret, frame = cap.read()
                if not ret:
                    break

                frame_resized = cv2.resize(frame, (640, 360))
                frame_gray = cv2.cvtColor(frame_resized, cv2.COLOR_BGR2GRAY)

                # Ignorar frames de transición negra
                if np.mean(frame_gray) < 12.0:
                    t += sample_interval
                    continue

                frame_gray = cv2.GaussianBlur(frame_gray, (5, 5), 0)

                if last_saved_frame_gray is None:
                    slide_count += 1
                    img_name = f"slide_{slide_count:03d}.png"
                    img_path = os.path.join(self.output_dir, img_name)
                    cv2.imwrite(img_path, frame)

                    last_saved_frame_gray = frame_gray
                    last_saved_timestamp = t
                    slides.append({
                        "id": slide_count,
                        "image_path": img_path,
                        "image_name": img_name,
                        "start_time": t,
                        "end_time": duration
                    })
                else:
                    diff = cv2.absdiff(frame_gray, last_saved_frame_gray)
                    mean_diff = np.mean(diff)

                    if mean_diff > threshold:
                        stable_t = min(t + sample_interval, duration - 0.1)
                        cap.set(cv2.CAP_PROP_POS_MSEC, int(stable_t * 1000))
                        ret_stable, frame_stable = cap.read()

                        if ret_stable:
                            stable_resized = cv2.resize(frame_stable, (640, 360))
                            stable_gray = cv2.cvtColor(stable_resized, cv2.COLOR_BGR2GRAY)

                            if np.mean(stable_gray) < 12.0:
                                t += sample_interval
                                continue

                            stable_gray = cv2.GaussianBlur(stable_gray, (5, 5), 0)
                            stable_mean_diff = np.mean(cv2.absdiff(frame_gray, stable_gray))

                            if stable_mean_diff < threshold * 0.5:
                                duration_of_prev = t - last_saved_timestamp
                                if duration_of_prev >= min_slide_duration:
                                    slides[-1]["end_time"] = t

                                    slide_count += 1
                                    img_name = f"slide_{slide_count:03d}.png"
                                    img_path = os.path.join(self.output_dir, img_name)
                                    cv2.imwrite(img_path, frame)

                                    last_saved_frame_gray = frame_gray
                                    last_saved_timestamp = t

                                    slides.append({
                                        "id": slide_count,
                                        "image_path": img_path,
                                        "image_name": img_name,
                                        "start_time": t,
                                        "end_time": duration
                                    })

                t += sample_interval

        finally:
            cap.release()

        if slides:
            slides[-1]["end_time"] = duration

        # POST-PROCESAMIENTO 1: Eliminar diapositivas negras
        non_black_slides = []
        for idx, slide in enumerate(slides):
            if is_black_image(slide["image_path"]):
                try:
                    if os.path.exists(slide["image_path"]):
                        os.remove(slide["image_path"])
                except Exception:
                    pass
                if non_black_slides:
                    non_black_slides[-1]["end_time"] = slide["end_time"]
                elif idx + 1 < len(slides):
                    slides[idx + 1]["start_time"] = slide["start_time"]
            else:
                non_black_slides.append(slide)
        slides = non_black_slides

        # POST-PROCESAMIENTO 2: Fusionar diapositivas adyacentes similares
        merged_slides = []
        if slides:
            current_slide = slides[0]
            for next_slide in slides[1:]:
                img1_gray = cv2.imread(current_slide["image_path"], cv2.IMREAD_GRAYSCALE)
                img2_gray = cv2.imread(next_slide["image_path"], cv2.IMREAD_GRAYSCALE)

                if are_images_similar(img1_gray, img2_gray, similarity_threshold=threshold, block_match_ratio=0.85):
                    current_slide["end_time"] = next_slide["end_time"]
                    try:
                        if os.path.exists(next_slide["image_path"]):
                            os.remove(next_slide["image_path"])
                    except Exception:
                        pass
                else:
                    merged_slides.append(current_slide)
                    current_slide = next_slide
            merged_slides.append(current_slide)
            slides = merged_slides

        # POST-PROCESAMIENTO 3: Asegurar continuidad del timeline
        if slides:
            slides[0]["start_time"] = 0.0
            for idx in range(len(slides) - 1):
                slides[idx]["end_time"] = slides[idx + 1]["start_time"]
            slides[-1]["end_time"] = duration

            # POST-PROCESAMIENTO 4: Re-indexar IDs y renombrar archivos secuencialmente
            for idx, slide in enumerate(slides):
                new_id = idx + 1
                old_path = slide["image_path"]
                new_name = f"slide_{new_id:03d}.png"
                new_path = os.path.join(self.output_dir, new_name)

                if old_path != new_path:
                    try:
                        if os.path.exists(new_path):
                            os.remove(new_path)
                        os.rename(old_path, new_path)
                        slide["image_path"] = new_path
                        slide["image_name"] = new_name
                    except Exception as e:
                        print(f"Error renombrando archivo al re-indexar: {e}")

                slide["id"] = new_id

        if progress_callback:
            progress_callback(1.0)

        return slides
