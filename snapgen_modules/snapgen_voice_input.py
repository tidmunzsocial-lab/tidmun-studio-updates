# -*- coding: utf-8 -*-
"""Voice input module for SnapGen"""
import threading
try:
    import speech_recognition as sr
    _HAS_SR = True
except Exception:
    _HAS_SR = False
try:
    import pyaudio
    _HAS_PA = True
except Exception:
    _HAS_PA = False
_AVAILABLE = _HAS_SR and _HAS_PA
_MIC_INDEX = None

def is_available():
    return _AVAILABLE

def list_microphones():
    if not _AVAILABLE:
        return []
    try:
        names = sr.Microphone.list_microphone_names()
        return [(i, name) for i, name in enumerate(names)]
    except Exception:
        return []

def set_mic_index(index):
    global _MIC_INDEX
    _MIC_INDEX = int(index) if index is not None else None

_WHISPER_MODEL = None

def listen_once(on_text=None, on_error=None, on_status=None, lang="th-TH"):
    if not _AVAILABLE:
        if callable(on_error):
            on_error("no speech_recognition or pyaudio")
        return
    def _worker():
        r = sr.Recognizer()
        try:
            if callable(on_status):
                on_status("listening")
            r.energy_threshold = 300
            r.dynamic_energy_threshold = False
            r.pause_threshold = 1.0
            with sr.Microphone(device_index=_MIC_INDEX) as source:
                r.adjust_for_ambient_noise(source, duration=0.5)
                audio = r.listen(source, timeout=30, phrase_time_limit=30)
            if callable(on_status):
                on_status("processing")
            text = None
            try:
                from faster_whisper import WhisperModel
                global _WHISPER_MODEL
                if _WHISPER_MODEL is None:
                    _WHISPER_MODEL = WhisperModel("tiny", device="cpu", cpu_threads=2, num_workers=1)
                import io, wave
                buf = io.BytesIO()
                with wave.open(buf, "wb") as wf:
                    wf.setnchannels(1)
                    wf.setsampwidth(2)
                    wf.setframerate(16000)
                    wf.writeframes(audio.get_wav_data())
                buf.seek(0)
                segments, _ = _WHISPER_MODEL.transcribe(buf, language="th", beam_size=3, vad_filter=True)
                text = " ".join(s.text for s in segments).strip()
            except Exception:
                pass
            if not text:
                try:
                    text = r.recognize_google(audio, language=lang)
                except Exception:
                    pass
            if not text:
                try:
                    text = r.recognize_google(audio, language="en-US")
                except Exception:
                    pass
            if callable(on_status):
                on_status("done")
            if text:
                if callable(on_text):
                    on_text(text)
            else:
                if callable(on_error):
                    on_error("could not hear anything")
        except Exception as e:
            if callable(on_error):
                on_error(str(e))
            if callable(on_status):
                on_status("done")
    threading.Thread(target=_worker, daemon=True).start()

def set_bridge(base, key):
    pass

def create_mic_icon_button(parent, text_widget, root, size=28, log_fn=None):
    import tkinter as tk
    frame = tk.Frame(parent, width=size, height=size, bg="#1E293B", highlightthickness=0, bd=0)
    frame.pack_propagate(False)
    label = tk.Label(frame, text="\U0001F399\U0000FE0F", bg="#1E293B", fg="#FFFFFF", font=("Segoe UI Emoji", 16), bd=0, padx=0, pady=0)
    label.pack(fill="both", expand=True)
    def _do_place():
        try:
            frame.place_forget()
            frame.place(x=2, y=text_widget.winfo_height() - size, width=size, height=size)
            frame.lift()
        except Exception:
            pass
    _do_place()
    text_widget.bind("<Configure>", lambda e: _do_place(), add="+")
    _idle_bg = "#1E293B"
    _listening_bg = "#DC2626"
    _processing_bg = "#F59E0B"
    def _log(msg):
        if callable(log_fn):
            try:
                log_fn(msg)
            except Exception:
                pass
    def on_click(e=None):
        if getattr(frame, "_listening", False):
            return
        frame._listening = True
        label.config(text="\U0001F3A4")
        frame.config(bg=_listening_bg)
        label.config(bg=_listening_bg)
        _log("\U0001F3A4 listening...")
        def _on_text(text):
            root.after(0, lambda: _insert(text))
            _log("\u2705 " + text[:80])
        def _insert(text):
            try:
                text_widget.insert("insert", text + " ")
                text_widget.focus_set()
            except Exception:
                pass
        def _on_error(err):
            root.after(0, _error_reset)
        def _error_reset():
            frame._listening = False
            label.config(text="\U0001F399\U0000FE0F")
            frame.config(bg=_idle_bg)
            label.config(bg=_idle_bg)
        def _on_status(status):
            def _update():
                if status == "listening":
                    label.config(text="\U0001F3A4")
                    frame.config(bg=_listening_bg)
                    label.config(bg=_listening_bg)
                    _log("\U0001F3A4 listening...")
                elif status == "processing":
                    label.config(text="\U0001F50D")
                    frame.config(bg=_processing_bg)
                    label.config(bg=_processing_bg)
                    _log("\U0001F50D processing...")
                elif status == "done":
                    frame._listening = False
                    label.config(text="\U0001F399\U0000FE0F")
                    frame.config(bg=_idle_bg)
                    label.config(bg=_idle_bg)
            root.after(0, _update)
        listen_once(on_text=_on_text, on_error=_on_error, on_status=_on_status)
    label.bind("<Button-1>", on_click)
    frame.bind("<Button-1>", on_click)
    return frame
