import sys
import os
import json
import numpy as np
import soundfile as sf
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                               QHBoxLayout, QGroupBox, QPushButton, QLabel, 
                               QLineEdit, QRadioButton, QFileDialog, QListWidget, 
                               QAbstractItemView, QMessageBox, QMenu, QCheckBox)
from PySide6.QtGui import QPalette, QColor
from PySide6.QtCore import Qt, QThread, Signal

STRINGS = {
    "en": {
        "title": "Batch WAV Trimmer (Qt)",
        "frame_source": "1. Source Files (Drag & Drop WAVs here)",
        "btn_load": "Browse Files",
        "frame_params": "2. Parameters",
        "lbl_threshold": "Threshold (dB):",
        "lbl_fade_in": "Fade In (ms):",
        "lbl_fade_out": "Fade Out (ms):",
        "frame_dest": "3. Destination",
        "btn_select_folder": "Select Folder",
        "btn_trim": "TRIM FILES",
        "chk_overwrite": "Overwrite existing files",  # NEW
        "status_ready": "Ready",
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
        "title": "バッチWAVトリマー (Qt)",
        "frame_source": "1. ソースファイル (ここにWAVをドロップ)",
        "btn_load": "ファイルを参照",
        "frame_params": "2. パラメータ",
        "lbl_threshold": "しきい値 (dB):",
        "lbl_fade_in": "フェードイン (ms):",
        "lbl_fade_out": "フェードアウト (ms):",
        "frame_dest": "3. 保存先",
        "btn_select_folder": "フォルダを選択",
        "btn_trim": "トリミング実行",
        "chk_overwrite": "既存のファイルを上書きする",  # NEW
        "status_ready": "準備完了",
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

class ProcessingThread(QThread):
    finished_signal = Signal(int, int) # success, errors
    
    def __init__(self, wav_paths, dest_folder, threshold, fade_in, fade_out, overwrite):
        super().__init__()
        self.wav_paths = wav_paths
        self.dest_folder = dest_folder
        self.threshold = threshold
        self.fade_in = fade_in
        self.fade_out = fade_out
        self.overwrite = overwrite # NEW: Store overwrite flag

    def trim_dsp(self, audio_array, samplerate):
        threshold_linear = 10 ** (self.threshold / 20)
        
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
        
        fade_in_samples = int((self.fade_in / 1000.0) * samplerate)
        fade_out_samples = int((self.fade_out / 1000.0) * samplerate)
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

    def run(self):
        success_count = 0
        error_count = 0
        for path in self.wav_paths:
            out_path = os.path.join(self.dest_folder, os.path.basename(path))
            
            # OPTIMIZATION: Skip processing entirely if file exists and overwrite is False
            if not self.overwrite and os.path.exists(out_path):
                print(f"Skipped {path}: File already exists.")
                error_count += 1
                continue

            try:
                data, samplerate = sf.read(path)
                orig_info = sf.info(path)
                trimmed_data = self.trim_dsp(data, samplerate)
                
                if trimmed_data is not None:
                    sf.write(out_path, trimmed_data, samplerate, format=orig_info.format, subtype=orig_info.subtype)
                    success_count += 1
                else:
                    error_count += 1
            except Exception as e:
                print(f"Error processing {path}: {e}")
                error_count += 1
                
        self.finished_signal.emit(success_count, error_count)


class DroppableListWidget(QListWidget):
    """Custom QListWidget that accepts drag-and-dropped files and allows item removal."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.wav_paths = set()
        
        # Enable Right-Click Context Menu
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_context_menu)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dragMoveEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            super().dragMoveEvent(event)

    def dropEvent(self, event):
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            for url in urls:
                path = url.toLocalFile()
                if path.lower().endswith('.wav') and path not in self.wav_paths:
                    self.wav_paths.add(path)
                    self.addItem(path)
            event.acceptProposedAction()
        else:
            super().dropEvent(event)

    def keyPressEvent(self, event):
        """Allows removal of selected items via Delete or Backspace key."""
        if event.key() in (Qt.Key_Delete, Qt.Key_Backspace):
            self.remove_selected_items()
        else:
            super().keyPressEvent(event)

    def show_context_menu(self, position):
        """Displays a context menu to remove items."""
        if not self.selectedItems():
            return
            
        menu = QMenu()
        remove_action = menu.addAction("Remove Selected")
        
        # Use .exec() instead of deprecated .exec_() in PySide6
        action = menu.exec(self.mapToGlobal(position))
        
        if action == remove_action:
            self.remove_selected_items()

    def remove_selected_items(self):
        """Safely removes items from both the UI and the underlying set."""
        for item in self.selectedItems():
            path = item.text()
            if path in self.wav_paths:
                self.wav_paths.remove(path)
            # Remove from the QListWidget
            self.takeItem(self.row(item))
            
    def get_paths(self):
        return list(self.wav_paths)


class BatchWavTrimmerQt(QMainWindow):
    CONFIG_FILE = "trimmer_config.json"

    def __init__(self):
        super().__init__()
        self.config = self.load_config()
        self.current_lang = self.config.get("language", "en")
        
        self.setup_ui()
        self.apply_config_state()
        self.update_language()

    def load_config(self):
        if os.path.exists(self.CONFIG_FILE):
            try:
                with open(self.CONFIG_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {}

    def save_config(self):
        rect = self.geometry()
        config = {
            "language": self.current_lang,
            "threshold": self.ent_threshold.text(),
            "fade_in": self.ent_fade_in.text(),
            "fade_out": self.ent_fade_out.text(),
            "dest_folder": self.ent_dest.text(),
            "overwrite": self.chk_overwrite.isChecked(), # Save checkbox state
            "geometry": [rect.x(), rect.y(), rect.width(), rect.height()]
        # ...
        }
        try:
            with open(self.CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(config, f, indent=4)
        except Exception:
            pass

    def apply_config_state(self):
        geom = self.config.get("geometry", [100, 100, 600, 500])
        
        # Validation: Ensure it's a list of exactly 4 items (Qt format) and not a legacy Tkinter string
        if isinstance(geom, list) and len(geom) == 4:
            self.setGeometry(*geom)
        else:
            self.setGeometry(100, 100, 600, 500) # Fallback to default
        
        self.ent_threshold.setText(self.config.get("threshold", "-96.0"))
        self.ent_fade_in.setText(self.config.get("fade_in", "5.0"))
        self.ent_fade_out.setText(self.config.get("fade_out", "50.0"))
        self.ent_dest.setText(self.config.get("dest_folder", ""))
        self.chk_overwrite.setChecked(self.config.get("overwrite", True)) # Default to True
        
        if self.current_lang == "en":
            self.radio_en.setChecked(True)
        else:
            self.radio_jp.setChecked(True)

    def closeEvent(self, event):
        self.save_config()
        event.accept()

    def setup_ui(self):
        main_widget = QWidget()
        layout = QVBoxLayout(main_widget)
        
        # Language Toggle
        lang_layout = QHBoxLayout()
        lang_layout.addStretch()
        self.radio_en = QRadioButton("English")
        self.radio_jp = QRadioButton("日本語")
        self.radio_en.toggled.connect(self.on_lang_changed)
        lang_layout.addWidget(self.radio_en)
        lang_layout.addWidget(self.radio_jp)
        layout.addLayout(lang_layout)

        # 1. Source Files
        self.grp_source = QGroupBox()
        src_layout = QVBoxLayout(self.grp_source)
        self.list_files = DroppableListWidget()
        self.btn_load = QPushButton()
        self.btn_load.clicked.connect(self.load_wavs)
        src_layout.addWidget(self.list_files)
        src_layout.addWidget(self.btn_load)
        layout.addWidget(self.grp_source)

        # 2. Parameters
        self.grp_params = QGroupBox()
        param_layout = QHBoxLayout(self.grp_params)
        
        self.lbl_threshold = QLabel()
        self.ent_threshold = QLineEdit()
        self.ent_threshold.editingFinished.connect(self.save_config)
        param_layout.addWidget(self.lbl_threshold)
        param_layout.addWidget(self.ent_threshold)
        
        self.lbl_fade_in = QLabel()
        self.ent_fade_in = QLineEdit()
        self.ent_fade_in.editingFinished.connect(self.save_config)
        param_layout.addWidget(self.lbl_fade_in)
        param_layout.addWidget(self.ent_fade_in)
        
        self.lbl_fade_out = QLabel()
        self.ent_fade_out = QLineEdit()
        self.ent_fade_out.editingFinished.connect(self.save_config)
        param_layout.addWidget(self.lbl_fade_out)
        param_layout.addWidget(self.ent_fade_out)
        layout.addWidget(self.grp_params)

        # 3. Destination
        self.grp_dest = QGroupBox()
        dest_layout = QVBoxLayout(self.grp_dest) # Changed to QVBoxLayout
        
        path_layout = QHBoxLayout()
        self.ent_dest = QLineEdit()
        self.ent_dest.setReadOnly(True)
        self.btn_dest = QPushButton()
        self.btn_dest.clicked.connect(self.select_destination)
        path_layout.addWidget(self.ent_dest)
        path_layout.addWidget(self.btn_dest)
        
        self.chk_overwrite = QCheckBox()
        self.chk_overwrite.stateChanged.connect(self.save_config)
        
        dest_layout.addLayout(path_layout)
        dest_layout.addWidget(self.chk_overwrite)
        layout.addWidget(self.grp_dest)

        # Action & Status
        self.btn_process = QPushButton()
        self.btn_process.setMinimumHeight(50)
        self.btn_process.setStyleSheet("font-weight: bold; font-size: 14px;")
        self.btn_process.clicked.connect(self.start_processing)
        layout.addWidget(self.btn_process)
        
        self.lbl_status = QLabel()
        self.lbl_status.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.lbl_status)

        self.setCentralWidget(main_widget)

    def on_lang_changed(self):
        self.current_lang = "en" if self.radio_en.isChecked() else "jp"
        self.update_language()
        self.save_config()

    def update_language(self):
        t = STRINGS[self.current_lang]
        self.setWindowTitle(t["title"])
        self.grp_source.setTitle(t["frame_source"])
        self.btn_load.setText(t["btn_load"])
        self.grp_params.setTitle(t["frame_params"])
        self.lbl_threshold.setText(t["lbl_threshold"])
        self.lbl_fade_in.setText(t["lbl_fade_in"])
        self.lbl_fade_out.setText(t["lbl_fade_out"])
        self.grp_dest.setTitle(t["frame_dest"])
        self.btn_dest.setText(t["btn_select_folder"])
        self.chk_overwrite.setText(t["chk_overwrite"]) # Translate Checkbox
        self.btn_process.setText(t["btn_trim"])
        
        # FIXED: Use worker_thread to avoid QObject.thread() conflict
        if not hasattr(self, 'worker_thread') or not self.worker_thread.isRunning():
            self.lbl_status.setText(t["status_ready"])

    def load_wavs(self):
        paths, _ = QFileDialog.getOpenFileNames(self, "Select WAV Files", "", "WAV Audio (*.wav)")
        for path in paths:
            if path not in self.list_files.wav_paths:
                self.list_files.wav_paths.add(path)
                self.list_files.addItem(path)

    def select_destination(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Destination Folder")
        if folder:
            self.ent_dest.setText(folder)
            self.save_config()

    def start_processing(self):
        t = STRINGS[self.current_lang]
        wav_paths = self.list_files.get_paths()
        dest_folder = self.ent_dest.text()

        if not wav_paths:
            QMessageBox.warning(self, t["msg_title_missing"], t["msg_no_files"])
            return
        if not dest_folder:
            QMessageBox.warning(self, t["msg_title_dest"], t["msg_no_dest"])
            return
            
        try:
            threshold = float(self.ent_threshold.text())
            fade_in = float(self.ent_fade_in.text())
            fade_out = float(self.ent_fade_out.text())
        except ValueError:
            QMessageBox.critical(self, t["msg_title_invalid"], t["msg_invalid_param"])
            return

        self.save_config()
        self.btn_process.setEnabled(False)
        self.lbl_status.setText(t["status_processing"])
        self.lbl_status.setStyleSheet("color: orange;")

        overwrite = self.chk_overwrite.isChecked()

        # Threading for GUI safety (Pass the overwrite flag)
        self.worker_thread = ProcessingThread(wav_paths, dest_folder, threshold, fade_in, fade_out, overwrite)
        self.worker_thread.finished_signal.connect(self.on_processing_complete)
        self.worker_thread.start()

    def on_processing_complete(self, success, errors):
        t = STRINGS[self.current_lang]
        self.btn_process.setEnabled(True)
        self.lbl_status.setText(t["status_complete"].format(success, errors))
        self.lbl_status.setStyleSheet("color: green;" if errors == 0 else "color: red;")
        self.list_files.clear()
        self.list_files.wav_paths.clear()

def apply_dark_theme(app):
    """Applies a native dark palette using the Fusion style."""
    app.setStyle("Fusion")
    dark_palette = QPalette()
    
    # Base UI Colors
    dark_palette.setColor(QPalette.Window, QColor(45, 45, 45))
    dark_palette.setColor(QPalette.WindowText, Qt.white)
    dark_palette.setColor(QPalette.Base, QColor(25, 25, 25))
    dark_palette.setColor(QPalette.AlternateBase, QColor(45, 45, 45))
    dark_palette.setColor(QPalette.ToolTipBase, Qt.white)
    dark_palette.setColor(QPalette.ToolTipText, Qt.white)
    dark_palette.setColor(QPalette.Text, Qt.white)
    
    # Button & Interaction Colors
    dark_palette.setColor(QPalette.Button, QColor(45, 45, 45))
    dark_palette.setColor(QPalette.ButtonText, Qt.white)
    dark_palette.setColor(QPalette.BrightText, Qt.red)
    dark_palette.setColor(QPalette.Link, QColor(42, 130, 218))
    dark_palette.setColor(QPalette.Highlight, QColor(42, 130, 218))
    dark_palette.setColor(QPalette.HighlightedText, Qt.black)
    
    # Disabled State Colors (for grayed-out buttons/text)
    dark_palette.setColor(QPalette.Disabled, QPalette.Text, QColor(127, 127, 127))
    dark_palette.setColor(QPalette.Disabled, QPalette.ButtonText, QColor(127, 127, 127))
    dark_palette.setColor(QPalette.Disabled, QPalette.WindowText, QColor(127, 127, 127))

    app.setPalette(dark_palette)
    
    # Optional stylesheet overrides for specific widget borders and padding
    app.setStyleSheet("""
        QGroupBox {
            border: 1px solid #555555;
            border-radius: 6px;
            margin-top: 5px; /* Space above the group box */
            padding-top: 5px; /* Space between title and inner widgets */
            padding-bottom: 5px;
        }
        QGroupBox::title {
            subcontrol-origin: margin;
            padding: 0 8px;
        }
        QPushButton {
            border: 1px solid #555555;
            border-radius: 4px;
            padding: 8px 16px; /* Taller, wider buttons */
            background-color: #353535;
        }
        QPushButton:hover {
            background-color: #454545;
        }
        QPushButton:disabled {
            background-color: #252525;
            border: 1px solid #353535;
        }
        QLineEdit, QListWidget {
            padding: 6px; /* Internal text padding */
            border: 1px solid #555555;
            border-radius: 4px;
            background-color: #1e1e1e; /* Darker inset look */
        }
    """)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    apply_dark_theme(app)
    
    window = BatchWavTrimmerQt()
    window.show()
    sys.exit(app.exec())