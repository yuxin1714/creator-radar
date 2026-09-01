import os
import site
import threading
from pathlib import Path

_model = None
_model_key = None
_lock = threading.Lock()
_dll_handles = []

def _prepare_nvidia_runtime():
    if os.name != "nt": return
    for root in site.getsitepackages():
        for relative in ("nvidia/cublas/bin", "nvidia/cudnn/bin"):
            directory = Path(root) / relative
            if directory.is_dir():
                os.environ["PATH"] = str(directory) + os.pathsep + os.environ.get("PATH", "")
                _dll_handles.append(os.add_dll_directory(str(directory)))

def get_model(model_path: str, device: str, compute_type: str):
    global _model, _model_key
    key = (model_path, device, compute_type)
    with _lock:
        if _model is None or _model_key != key:
            _prepare_nvidia_runtime()
            from faster_whisper import WhisperModel
            _model = WhisperModel(model_path, device=device, compute_type=compute_type)
            _model_key = key
    return _model

def transcribe_file(media_path: Path, model_path: str, device: str, compute_type: str):
    model = get_model(model_path, device, compute_type)
    segments, info = model.transcribe(str(media_path), beam_size=5, vad_filter=True)
    rows, texts = [], []
    for segment in segments:
        text = segment.text.strip()
        if text:
            rows.append({"start": round(segment.start, 3), "end": round(segment.end, 3), "text": text})
            texts.append(text)
    return {"language": info.language, "segments": rows, "text": "\n".join(texts)}
