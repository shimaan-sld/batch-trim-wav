import os
import soundfile as sf
import numpy as np
import ttkbootstrap as tb
from ttkbootstrap.constants import *
from ttkbootstrap.dialogs import Messagebox
from tkinter import filedialog
import threading

class BatchWavTrimmerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Batch WAV Trimmer")
        self.root.geometry("600x450")
        
        self.wav_paths = []
        self.dest_folder = ""
        
        self.setup_ui()

    def setup_ui(self):
        # 1. Load WAV Files
        file_frame = tb.LabelFrame(self.root, text="1. Source Files", padding=15)
        file_frame.pack(fill=X, padx=20, pady=10)
        
        self.btn_load = tb.Button(file_frame, text="Load WAV Files", command=self.load_wavs, bootstyle=PRIMARY)
        self.btn_load.pack(side=LEFT, padx=(0, 10))
        
        self.lbl_files = tb.Label(file_frame, text="No files loaded", bootstyle=SECONDARY)
        self.lbl_files.pack(side=LEFT, fill=X, expand=True)

        # 2. Parameters (Threshold + Fades)
        param_frame = tb.LabelFrame(self.root, text="2. Parameters", padding=15)
        param_frame.pack(fill=X, padx=20, pady=10)
        
        # Threshold
        tb.Label(param_frame, text="Threshold (dB):").pack(side=LEFT, padx=(0, 5))
        self.threshold_var = tb.StringVar(value="-96.0")
        self.ent_threshold = tb.Entry(param_frame, textvariable=self.threshold_var, width=8)
        self.ent_threshold.pack(side=LEFT, padx=(0, 15))

        # Fade In
        tb.Label(param_frame, text="Fade In (ms):").pack(side=LEFT, padx=(0, 5))
        self.fade_in_var = tb.StringVar(value="5.0")
        self.ent_fade_in = tb.Entry(param_frame, textvariable=self.fade_in_var, width=6)
        self.ent_fade_in.pack(side=LEFT, padx=(0, 15))

        # Fade Out
        tb.Label(param_frame, text="Fade Out (ms):").pack(side=LEFT, padx=(0, 5))
        self.fade_out_var = tb.StringVar(value="50.0")
        self.ent_fade_out = tb.Entry(param_frame, textvariable=self.fade_out_var, width=6)
        self.ent_fade_out.pack(side=LEFT)

        # 3. Destination Folder
        dest_frame = tb.LabelFrame(self.root, text="3. Destination", padding=15)
        dest_frame.pack(fill=X, padx=20, pady=10)
        
        self.dest_var = tb.StringVar()
        self.ent_dest = tb.Entry(dest_frame, textvariable=self.dest_var, state="readonly")
        self.ent_dest.pack(side=LEFT, fill=X, expand=True, padx=(0, 10))
        
        self.btn_dest = tb.Button(dest_frame, text="Select Folder", command=self.select_destination, bootstyle=INFO)
        self.btn_dest.pack(side=LEFT)

        # Action Button & Status
        self.btn_process = tb.Button(
            self.root, 
            text="TRIM FILES", 
            command=self.start_processing_thread, 
            bootstyle=(SUCCESS, OUTLINE)
        )
        # fill=X makes it expand horizontally
        # padx=20 aligns its edges with the frames above it
        # ipady=15 keeps the button physically taller
        self.btn_process.pack(fill=X, padx=20, pady=20, ipady=15) 
        
        self.lbl_status = tb.Label(self.root, text="", font=("Arial", 10, "bold"))
        self.lbl_status.pack()

    def load_wavs(self):
        paths = filedialog.askopenfilenames(filetypes=[("WAV Audio", "*.wav")])
        if paths:
            self.wav_paths = list(paths)
            self.lbl_files.config(text=f"{len(self.wav_paths)} file(s) loaded", bootstyle=INFO)

    def select_destination(self):
        folder = filedialog.askdirectory()
        if folder:
            self.dest_folder = folder
            self.dest_var.set(self.dest_folder)

    def start_processing_thread(self):
        if not self.wav_paths:
            Messagebox.show_warning("Please load WAV files first.", "Missing Input")
            return
        if not self.dest_folder:
            Messagebox.show_warning("Please select a destination folder.", "Missing Output")
            return
            
        try:
            float(self.threshold_var.get())
            float(self.fade_in_var.get())
            float(self.fade_out_var.get())
        except ValueError:
            Messagebox.show_error("Parameters must be valid numbers.", "Invalid Input")
            return

        self.btn_process.config(state=DISABLED)
        self.lbl_status.config(text="Processing...", bootstyle=WARNING)
        
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
        
        # Fade Processing
        fade_in_samples = int((fade_in_ms / 1000.0) * samplerate)
        fade_out_samples = int((fade_out_ms / 1000.0) * samplerate)
        
        # Ensure fades don't exceed file length[cite: 1]
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
                    error_count += 1 # Completely silent files
            except Exception as e:
                print(f"Failed to process {path}: {e}")
                error_count += 1
                
        self.root.after(0, self.update_status_complete, success_count, error_count)

    def update_status_complete(self, success, errors):
        self.btn_process.config(state=NORMAL)
        msg = f"Completed: {success} saved."
        if errors > 0:
            msg += f" ({errors} skipped/failed)"
        self.lbl_status.config(text=msg, bootstyle=SUCCESS if errors == 0 else DANGER)

if __name__ == "__main__":
    app_root = tb.Window(themename="darkly")
    app = BatchWavTrimmerApp(app_root)
    app_root.mainloop()