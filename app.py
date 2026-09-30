import os
import json
import soundfile as sf
import numpy as np
import ttkbootstrap as tb
from ttkbootstrap.constants import *
from ttkbootstrap.dialogs import Messagebox
from tkinter import filedialog
import threading

STRINGS = {
    "en": {
        "title": "Batch WAV Trimmer",
        "frame_source": "1. Source Files",
        "btn_load": "Load WAV Files",
        "lbl_no_files": "No files loaded",
        "lbl_files_loaded": "{} file(s) loaded",
        "frame_params": "2. Parameters",
        "lbl_threshold": "Threshold (dB):",
        "lbl_fade_in": "Fade In (ms):",
        "lbl_fade_out": "Fade Out (ms):",
        "frame_dest": "3. Destination",
        "btn_select_folder": "Select Folder",
        "btn_trim": "TRIM FILES",
        "status_ready": "",
        "status_processing": "Processing...",
        "status_complete": "Completed: {} saved. ({} skipped/failed)",
        "msg_title_missing": "Missing Input",
        "msg_no_files": "Please load WAV files first.",
        "msg_title_dest": "Missing Output",
        "msg_no_dest": "Please select a destination folder.",
        "msg_title_invalid": "Invalid Input",
        "msg_invalid_param": "Parameters must be valid numbers."
    },
    "jp": {
        "title": "バッチWAVトリマー",
        "frame_source": "1. ソースファイル",
        "btn_load": "WAVを読み込む",
        "lbl_no_files": "ファイルが読み込まれていません",
        "lbl_files_loaded": "{} 個のファイルを読み込みました",
        "frame_params": "2. パラメータ",
        "lbl_threshold": "しきい値 (dB):",
        "lbl_fade_in": "フェードイン (ms):",
        "lbl_fade_out": "フェードアウト (ms):",
        "frame_dest": "3. 保存先",
        "btn_select_folder": "フォルダを選択",
        "btn_trim": "トリミング実行",
        "status_ready": "",
        "status_processing": "処理中...",
        "status_complete": "完了: {} 個保存 ({} 個スキップ/失敗)",
        "msg_title_missing": "入力エラー",
        "msg_no_files": "先にWAVファイルを読み込んでください。",
        "msg_title_dest": "出力エラー",
        "msg_no_dest": "保存先フォルダを選択してください。",
        "msg_title_invalid": "入力エラー",
        "msg_invalid_param": "パラメータには有効な数値を入力してください。"
    }
}

class BatchWavTrimmerApp:
    CONFIG_FILE = "trimmer_config.json"

    def __init__(self, root):
        self.root = root
        
        self.wav_paths = []
        
        config = self.load_config()
        
        # Load Geometry (Size and Position)
        saved_geometry = config.get("geometry", "600x480")
        self.root.geometry(saved_geometry)
        
        self.lang_var = tb.StringVar(value=config.get("language", "en"))
        self.threshold_var = tb.StringVar(value=config.get("threshold", "-96.0"))
        self.fade_in_var = tb.StringVar(value=config.get("fade_in", "5.0"))
        self.fade_out_var = tb.StringVar(value=config.get("fade_out", "50.0"))
        self.dest_folder = config.get("dest_folder", "")
        self.dest_var = tb.StringVar(value=self.dest_folder)
        
        self.setup_ui()
        self.update_language()
        
        # Intercept window close to save position
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    def load_config(self):
        if os.path.exists(self.CONFIG_FILE):
            try:
                with open(self.CONFIG_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                print(f"Failed to load config: {e}")
        return {}

    def save_config(self):
        config = {
            "language": self.lang_var.get(),
            "threshold": self.threshold_var.get(),
            "fade_in": self.fade_in_var.get(),
            "fade_out": self.fade_out_var.get(),
            "dest_folder": self.dest_folder,
            "geometry": self.root.geometry() # Captures WxH+X+Y
        }
        try:
            with open(self.CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(config, f, indent=4)
        except Exception as e:
            print(f"Failed to save config: {e}")

    def on_closing(self):
        self.save_config()
        self.root.destroy()

    def setup_ui(self):
        lang_frame = tb.Frame(self.root)
        lang_frame.pack(fill=X, padx=20, pady=(10, 0))
        
        tb.Radiobutton(lang_frame, text="English", variable=self.lang_var, value="en", command=self.on_language_change).pack(side=RIGHT, padx=5)
        tb.Radiobutton(lang_frame, text="日本語", variable=self.lang_var, value="jp", command=self.on_language_change).pack(side=RIGHT, padx=5)

        self.file_frame = tb.LabelFrame(self.root, padding=15)
        self.file_frame.pack(fill=X, padx=20, pady=10)
        self.btn_load = tb.Button(self.file_frame, command=self.load_wavs, bootstyle=PRIMARY)
        self.btn_load.pack(side=LEFT, padx=(0, 10))
        self.lbl_files = tb.Label(self.file_frame, bootstyle=SECONDARY)
        self.lbl_files.pack(side=LEFT, fill=X, expand=True)

        self.param_frame = tb.LabelFrame(self.root, padding=15)
        self.param_frame.pack(fill=X, padx=20, pady=10)
        self.lbl_threshold = tb.Label(self.param_frame)
        self.lbl_threshold.pack(side=LEFT, padx=(0, 5))
        self.ent_threshold = tb.Entry(self.param_frame, textvariable=self.threshold_var, width=8)
        self.ent_threshold.pack(side=LEFT, padx=(0, 15))
        self.ent_threshold.bind("<FocusOut>", lambda e: self.save_config())

        self.lbl_fade_in = tb.Label(self.param_frame)
        self.lbl_fade_in.pack(side=LEFT, padx=(0, 5))
        self.ent_fade_in = tb.Entry(self.param_frame, textvariable=self.fade_in_var, width=6)
        self.ent_fade_in.pack(side=LEFT, padx=(0, 15))
        self.ent_fade_in.bind("<FocusOut>", lambda e: self.save_config())

        self.lbl_fade_out = tb.Label(self.param_frame)
        self.lbl_fade_out.pack(side=LEFT, padx=(0, 5))
        self.ent_fade_out = tb.Entry(self.param_frame, textvariable=self.fade_out_var, width=6)
        self.ent_fade_out.pack(side=LEFT)
        self.ent_fade_out.bind("<FocusOut>", lambda e: self.save_config())

        self.dest_frame = tb.LabelFrame(self.root, padding=15)
        self.dest_frame.pack(fill=X, padx=20, pady=10)
        self.ent_dest = tb.Entry(self.dest_frame, textvariable=self.dest_var, state="readonly")
        self.ent_dest.pack(side=LEFT, fill=X, expand=True, padx=(0, 10))
        self.btn_dest = tb.Button(self.dest_frame, command=self.select_destination, bootstyle=INFO)
        self.btn_dest.pack(side=LEFT)

        self.btn_process = tb.Button(self.root, command=self.start_processing_thread, bootstyle=(SUCCESS, OUTLINE))
        self.btn_process.pack(fill=X, padx=20, pady=20, ipady=15)
        
        self.lbl_status = tb.Label(self.root, font=("Arial", 10, "bold"))
        self.lbl_status.pack()

    def on_language_change(self):
        self.update_language()
        self.save_config()

    def update_language(self):
        lang = self.lang_var.get()
        t = STRINGS[lang]
        
        self.root.title(t["title"])
        self.file_frame.config(text=t["frame_source"])
        self.btn_load.config(text=t["btn_load"])
        
        if not self.wav_paths:
            self.lbl_files.config(text=t["lbl_no_files"])
        else:
            self.lbl_files.config(text=t["lbl_files_loaded"].format(len(self.wav_paths)))
            
        self.param_frame.config(text=t["frame_params"])
        self.lbl_threshold.config(text=t["lbl_threshold"])
        self.lbl_fade_in.config(text=t["lbl_fade_in"])
        self.lbl_fade_out.config(text=t["lbl_fade_out"])
        
        self.dest_frame.config(text=t["frame_dest"])
        self.btn_dest.config(text=t["btn_select_folder"])
        self.btn_process.config(text=t["btn_trim"])
        
        if not self.lbl_status.cget("text") or "Processing" in self.lbl_status.cget("text") or "処理中" in self.lbl_status.cget("text"):
            self.lbl_status.config(text=t["status_ready"])

    def load_wavs(self):
        paths = filedialog.askopenfilenames(filetypes=[("WAV Audio", "*.wav")])
        if paths:
            self.wav_paths = list(paths)
            lang = self.lang_var.get()
            self.lbl_files.config(text=STRINGS[lang]["lbl_files_loaded"].format(len(self.wav_paths)), bootstyle=INFO)

    def select_destination(self):
        folder = filedialog.askdirectory()
        if folder:
            self.dest_folder = folder
            self.dest_var.set(self.dest_folder)
            self.save_config()

    def start_processing_thread(self):
        lang = self.lang_var.get()
        t = STRINGS[lang]

        if not self.wav_paths:
            Messagebox.show_warning(t["msg_no_files"], t["msg_title_missing"])
            return
        if not self.dest_folder:
            Messagebox.show_warning(t["msg_no_dest"], t["msg_title_dest"])
            return
            
        try:
            float(self.threshold_var.get())
            float(self.fade_in_var.get())
            float(self.fade_out_var.get())
        except ValueError:
            Messagebox.show_error(t["msg_invalid_param"], t["msg_title_invalid"])
            return

        self.save_config()
        self.btn_process.config(state=DISABLED)
        self.lbl_status.config(text=t["status_processing"], bootstyle=WARNING)
        threading.Thread(target=self.process_files, daemon=True).start()

    def trim_dsp(self, audio_array, threshold_db, samplerate, fade_in_ms, fade_out_ms):
        threshold_linear = 10 ** (threshold_db / 20)
        
        if audio_array.ndim > 1:
            abs_max = np.max(np.abs(audio_array), axis=1)
        else:
            abs_max = np.abs(audio_array)
            
        non_silent_indices = np.where(abs_max > threshold_linear)[0]
        if len(non_silent_indices) == 0: 
            return None
            
        start_idx = non_silent_indices[0]
        end_idx = non_silent_indices[-1] + 1
        processed = audio_array[start_idx:end_idx].copy()
        
        fade_in_samples = int((fade_in_ms / 1000.0) * samplerate)
        fade_out_samples = int((fade_out_ms / 1000.0) * samplerate)
        
        fade_in_samples = min(fade_in_samples, len(processed))
        fade_out_samples = min(fade_out_samples, len(processed) - fade_in_samples)

        def make_exp_curve(length):
            if length <= 0: return np.array([])
            x = np.linspace(0, 1, length)
            return (np.exp(5 * x) - 1) / (np.exp(5) - 1)

        if fade_in_samples > 0:
            curve_in = make_exp_curve(fade_in_samples)
            if processed.ndim > 1: curve_in = curve_in[:, np.newaxis]
            processed[:fade_in_samples] *= curve_in
            
        if fade_out_samples > 0:
            curve_out = make_exp_curve(fade_out_samples)[::-1]
            if processed.ndim > 1: curve_out = curve_out[:, np.newaxis]
            processed[-fade_out_samples:] *= curve_out

        return processed

    def process_files(self):
        threshold_db = float(self.threshold_var.get())
        fade_in_ms = float(self.fade_in_var.get())
        fade_out_ms = float(self.fade_out_var.get())
        
        success_count = 0
        error_count = 0
        
        for path in self.wav_paths:
            try:
                data, samplerate = sf.read(path)
                orig_info = sf.info(path)
                
                trimmed_data = self.trim_dsp(data, threshold_db, samplerate, fade_in_ms, fade_out_ms)
                
                if trimmed_data is not None:
                    filename = os.path.basename(path)
                    out_path = os.path.join(self.dest_folder, filename)
                    sf.write(out_path, trimmed_data, samplerate, format=orig_info.format, subtype=orig_info.subtype)
                    success_count += 1
                else:
                    error_count += 1 
            except Exception as e:
                print(f"Failed to process {path}: {e}")
                error_count += 1
                
        self.root.after(0, self.update_status_complete, success_count, error_count)

    def update_status_complete(self, success, errors):
        lang = self.lang_var.get()
        t = STRINGS[lang]
        self.btn_process.config(state=NORMAL)
        msg = t["status_complete"].format(success, errors)
        self.lbl_status.config(text=msg, bootstyle=SUCCESS if errors == 0 else DANGER)

if __name__ == "__main__":
    app_root = tb.Window(themename="darkly")
    app = BatchWavTrimmerApp(app_root)
    app_root.mainloop()