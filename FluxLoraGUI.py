import os
import time
from urllib.request import urlretrieve
from PyQt6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QLabel,
    QScrollArea,
    QGridLayout,
    QMessageBox,
    QComboBox,
    QSpinBox,
    QDoubleSpinBox,
    QCheckBox,
    QFormLayout,
    QSizePolicy,
    QTextEdit,
    QProgressBar,
    QFileDialog,
    QDialog,
    QStatusBar,
)
from PyQt6.QtGui import QPixmap, QGuiApplication, QResizeEvent
from PyQt6.QtCore import (
    Qt,
    QThread,
    pyqtSignal,
    QSettings,
    QTimer,
    QRunnable,
    QThreadPool,
    QObject,
)
import replicate
from dotenv import load_dotenv
from token_count import TokenCount

load_dotenv()

class ImageLoaderSignals(QObject):
    finished = pyqtSignal(list)

class ImageLoader(QRunnable):
    def __init__(self, folder_path):
        super().__init__()
        self.folder_path = folder_path
        self.signals = ImageLoaderSignals()

    def run(self):
        images = []
        for filename in os.listdir(self.folder_path):
            if filename.lower().endswith((".png", ".jpg", ".jpeg", ".webp")):
                file_path = os.path.join(self.folder_path, filename)
                mod_time = os.path.getmtime(file_path)
                images.append((file_path, mod_time))
        images.sort(key=lambda x: x[1], reverse=True)
        self.signals.finished.emit([img[0] for img in images])

class ImageGeneratorThread(QThread):
    finished = pyqtSignal(list)
    error = pyqtSignal(str)

    def __init__(self, params):
        super().__init__()
        self.params = params

    def run(self):
        try:
            output = replicate.run(
                "lucataco/flux-dev-lora:a22c463f11808638ad5e2ebd582e07a469031f48dd567366fb4c6fdab91d614d",
                input=self.params,
            )
            self.finished.emit(output)
        except Exception as e:
            self.error.emit(str(e))

class TokenCounter(QWidget):
    def __init__(self, text_edit, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.text_edit = text_edit
        self.tc = TokenCount(model_name="gpt-3.5-turbo")

        layout = QVBoxLayout(self)
        self.token_count_label = QLabel("Tokens: 0")
        self.warning_label = QLabel()
        self.warning_label.setStyleSheet("color: orange;")
        self.warning_label.hide()

        layout.addWidget(self.token_count_label)
        layout.addWidget(self.warning_label)

        self.text_edit.textChanged.connect(self.update_count)

    def update_count(self):
        text = self.text_edit.toPlainText()
        token_count = self.tc.num_tokens_from_string(text)
        self.token_count_label.setText(f"Tokens: {token_count}")

        if token_count > 77:
            self.warning_label.setText("Warning: Tokens beyond 77 will be ignored")
            self.warning_label.show()
        else:
            self.warning_label.hide()

class ImageViewer(QDialog):
    def __init__(self, pixmap, parent=None):
        super().__init__(parent)
        self.original_pixmap = pixmap
        self.initUI()

    def initUI(self):
        self.setWindowTitle("Image Viewer")
        self.setGeometry(100, 100, 1920, 1080)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.image_label = QLabel(self)
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.image_label)

        self.save_button = QPushButton("Save Image", self)
        self.save_button.clicked.connect(self.saveImage)
        layout.addWidget(self.save_button)

        self.updateImage()

    def updateImage(self):
        if self.save_button:
            button_height = self.save_button.height()
        else:
            button_height = 0

        scaled_pixmap = self.original_pixmap.scaled(
            self.width(),
            self.height() - button_height,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.image_label.setPixmap(scaled_pixmap)

    def resizeEvent(self, event: QResizeEvent):
        self.updateImage()
        super().resizeEvent(event)

    def saveImage(self):
        file_name, _ = QFileDialog.getSaveFileName(
            self, "Save Image", "", "Images (*.png *.jpg *.bmp)"
        )
        if file_name:
            self.original_pixmap.save(file_name)

class ImagePreviewWidget(QLabel):
    def __init__(self, pixmap, file_path, parent=None):
        super().__init__(parent)
        self.original_pixmap = pixmap
        self.file_path = file_path
        self.setPixmap(
            pixmap.scaled(
                300,
                300,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setStyleSheet("""
            QLabel {
                border: 2px solid
                border-radius: 10px;
                padding: 5px;
                margin: 5px;
            }
            QLabel:hover {
                border-color:
            }
        """)
        self.setMinimumSize(310, 310)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            viewer = ImageViewer(self.original_pixmap, self.parent())
            viewer.exec()

class ImageGeneratorGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.settings = QSettings("rtuszik", "Flux-Dev-Lora-GUI")
        self.threadpool = QThreadPool()
        self.current_thread = None
        self.is_grid_view = True
        self.save_metadata_checkbox = None
        self.initUI()
        self.loadSettings()
        if self.save_metadata_checkbox is None:
            print(
                "Warning: save_metadata_checkbox is still None after initUI and loadSettings"
            )
        QTimer.singleShot(100, self.loadImagesAsync)

    def initUI(self):
        self.setStyleSheet(self.getStyleSheet())
        self.setupMainWidget()
        self.setupLeftPanel()
        self.setupRightPanel()
        self.setupBottomPanel()
        self.setupStatusBar()
        self.setWindowTitle("Image Generator")
        self.resize(1900, 800)
        self.setMinimumWidth(1600)

    def getStyleSheet(self):
        return """
            QMainWindow, QWidget {
                background-color:
                color:
                font-family: 'Arial', 'Sans-Serif';
                font-size: 13px;
            }
            QLineEdit, QTextEdit, QComboBox, QSpinBox, QDoubleSpinBox {
                background-color:
                border: 1px solid
                borderradius: 5px;
                padding: 5px;
                color:
                width: 100%;
            }
            QPushButton {
                background-color:
                color: white;
                border: none;
                borderradius: 5px;
                padding: 8px 16px;
                font-weight: 500;
                min-height: 30px;
                width: 100%;
            }
            QPushButton:hover {
                background-color:
            }
            QPushButton:pressed {
                background-color:
                border: 1px solid
            }
            QLabel {
                color:
            }
            QScrollArea {
                border: none;
                background-color:
            }
            QCheckBox {
                spacin: 5px;
                color:
            }
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
            }
            QCheckBox::indicator:unchecked {
                border 2px solid
                background-color:
            }
            QCheckBox::indicator:checked {
                border: 2px solid
                background-color:
            }
        """

    def setupMainWidget(self):
        main_widget = QWidget()
        main_layout = QVBoxLayout(main_widget)  # Corrected line
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(20)
        self.setCentralWidget(main_widget)

        top_layout = QHBoxLayout()
        main_layout.addLayout(top_layout, 1)

        self.left_layout = QVBoxLayout()
        top_layout.addLayout(self.left_layout, 1)

        self.right_layout = QVBoxLayout()
        top_layout.addLayout(self.right_layout, 2)

        self.bottom_layout = QVBoxLayout()
        main_layout.addLayout(self.bottom_layout)

    def setupLeftPanel(self):
        self.setupFormInputs()
        self.setupSaveSettings()

    def setupFormInputs(self):
        form_layout = QFormLayout()
        form_layout.setSpacing(10)
        form_layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        form_layout.setFormAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop
        )

        self.aspect_ratio_input = self.createComboBox(
            [
                "1:1",
                "16:9",
                "21:9",
                "3:2",
                "2:3",
                "4:5",
                "5:4",
                "3:4",
                "4:3",
                "9:16",
                "9:21",
            ]
        )
        self.num_outputs_input = self.createSpinBox(1, 4)
        self.num_inference_steps_input = self.createSpinBox(1, 50)
        self.guidance_scale_input = self.createDoubleSpinBox(0, 10, 0.1)
        self.seed_input = self.createSpinBox(-2147483648, 2147483647, "Random")
        self.output_format_input = self.createComboBox(["png", "jpg", "webp"])
        self.output_quality_input = self.createSpinBox(0, 100)
        self.hf_lora_input = QLineEdit()
        self.lora_scale_input = self.createDoubleSpinBox(0, 1, 0.1)
        self.disable_safety_checker_input = QCheckBox("Disable Safety")
        self.disable_safety_checker_input.setChecked(True)

        self.addFormRow(form_layout, "Aspect Ratio:", self.aspect_ratio_input)
        self.addFormRow(form_layout, "Outputs:", self.num_outputs_input)
        self.addFormRow(form_layout, "Inference Steps:", self.num_inference_steps_input)
        self.addFormRow(form_layout, "Guidance Scale:", self.guidance_scale_input)
        self.addFormRow(form_layout, "Seed:", self.seed_input)
        self.addFormRow(form_layout, "Output Format:", self.output_format_input)
        self.addFormRow(form_layout, "Quality:", self.output_quality_input)
        self.addFormRow(form_layout, "HF LoRA:", self.hf_lora_input)
        self.addFormRow(form_layout, "LoRA Scale:", self.lora_scale_input)
        self.addFormRow(form_layout, "", self.disable_safety_checker_input)

        self.left_layout.addLayout(form_layout)

    def setupSaveSettings(self):
        self.auto_save_checkbox = QCheckBox("Auto-save")
        self.save_metadata_checkbox = QCheckBox("Save prompt as metadata")
        self.save_dir_input = QLineEdit()
        self.save_dir_input.setReadOnly(True)
        self.choose_dir_button = QPushButton("Choose Directory")
        self.choose_dir_button.clicked.connect(self.choose_save_directory)

        save_settings_layout = QVBoxLayout()
        checkbox_layout = QHBoxLayout()
        checkbox_layout.addWidget(self.auto_save_checkbox)
        checkbox_layout.addWidget(self.save_metadata_checkbox)
        save_settings_layout.addLayout(checkbox_layout)

        dir_layout = QHBoxLayout()
        dir_layout.addWidget(self.save_dir_input)
        dir_layout.addWidget(self.choose_dir_button)
        save_settings_layout.addLayout(dir_layout)

        self.left_layout.addLayout(save_settings_layout)

    def setupRightPanel(self):
        self.gallery_scroll = QScrollArea()
        self.gallery_scroll.setWidgetResizable(True)
        self.gallery_widget = QWidget()
        self.gallery_layout = QGridLayout(self.gallery_widget)
        self.gallery_layout.setSpacing(10)
        self.gallery_scroll.setWidget(self.gallery_widget)

        self.right_layout.addWidget(self.gallery_scroll)

        self.view_toggle = QPushButton("Toggle View")
        self.view_toggle.clicked.connect(self.toggle_view)
        self.right_layout.addWidget(self.view_toggle)

    def setupBottomPanel(self):
        self.prompt_input = QTextEdit()
        self.prompt_input.setFixedHeight(100)
        self.prompt_input.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        self.bottom_layout.addWidget(QLabel("Prompt:"))
        self.bottom_layout.addWidget(self.prompt_input)

        self.token_counter = TokenCounter(self.prompt_input)
        self.bottom_layout.addWidget(self.token_counter)

        self.generate_button = QPushButton("Generate Images")
        self.generate_button.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        self.generate_button.setFixedHeight(50)
        self.generate_button.clicked.connect(self.generate_images)
        self.bottom_layout.addWidget(self.generate_button)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.hide()
        self.bottom_layout.addWidget(self.progress_bar)

        self.interrupt_button = QPushButton("Interrupt Generation")
        self.interrupt_button.clicked.connect(self.interrupt_generation)
        self.interrupt_button.setEnabled(False)
        self.bottom_layout

        self.bottom_layout.addWidget(self.interrupt_button)

    def setupStatusBar(self):
        status_bar = QStatusBar()
        self.setStatusBar(status_bar)
        status_bar.showMessage("Ready")

    def createComboBox(self, items):
        combo_box = QComboBox()
        combo_box.addItems(items)
        return combo_box

    def createSpinBox(self, min_value, max_value, special_value_text=None):
        spin_box = QSpinBox()
        spin_box.setRange(min_value, max_value)
        if special_value_text:
            spin_box.setSpecialValueText(special_value_text)
        return spin_box

    def createDoubleSpinBox(self, min_value, max_value, step):
        double_spin_box = QDoubleSpinBox()
        double_spin_box.setRange(min_value, max_value)
        double_spin_box.setSingleStep(step)
        return double_spin_box

    def addFormRow(self, form_layout, label, widget):
        form_layout.addRow(label, widget)

    def loadImagesAsync(self):
        folder_path = self.save_dir_input.text()
        loader = ImageLoader(folder_path)
        loader.signals.finished.connect(self.updateGallery)
        self.threadpool.start(loader)

    def toggle_view(self):
        self.is_grid_view = not self.is_grid_view
        self.clearGallery()
        self.updateGallery()

    def updateGallery(self, image_paths=None):
        if image_paths is None:
            image_paths = [
                self.gallery_layout.itemAt(i).widget().file_path
                for i in range(self.gallery_layout.count())
            ]

        sorted_images = sorted(
            image_paths, key=lambda x: os.path.getctime(x), reverse=True
        )

        existing_images = {
            self.gallery_layout.itemAt(i).widget().file_path
            for i in range(self.gallery_layout.count())
        }

        images_to_add = [path for path in sorted_images if path not in existing_images]

        for path in images_to_add:
            pixmap = QPixmap(path)
            preview = ImagePreviewWidget(pixmap, path)
            if self.is_grid_view:
                row = self.gallery_layout.count() // 3
                col = self.gallery_layout.count() % 3
            else:
                row = self.gallery_layout.count()
                col = 0
            self.gallery_layout.addWidget(preview, row, col)

        for i in range(self.gallery_layout.count()):
            self.gallery_layout.itemAt(i).widget().show()

        self.gallery_scroll.verticalScrollBar().setValue(
            self.gallery_scroll.verticalScrollBar().minimum()
        )

    def clearGallery(self):
        for i in reversed(range(self.gallery_layout.count())):
            widget = self.gallery_layout.itemAt(i).widget()
            if widget is not None:
                widget.hide()
                self.gallery_layout.removeWidget(widget)

    def center(self):
        primary_screen = QGuiApplication.primaryScreen()
        if primary_screen:
            screen_geometry = primary_screen.geometry()
            center_point = screen_geometry.center()
            frame_geometry = self.frameGeometry()
            frame_geometry.moveCenter(center_point)
            self.move(frame_geometry.topLeft())

    def display_images(self, image_urls):
        self.progress_bar.hide()
        self.generate_button.setEnabled(True)
        self.interrupt_button.setEnabled(False)

        timestamp = time.strftime("%Y%m%d_%H%M%S")
        new_image_paths = []
        for i, image_url in enumerate(image_urls):
            if self.auto_save_checkbox.isChecked():
                base_name = f"generated_image_{timestamp}_{i+1}.{self.output_format_input.currentText()}"
                image_path = os.path.join(self.save_dir_input.text(), base_name)
                counter = 1
                while os.path.exists(image_path):
                    new_name = f"generated_image_{timestamp}_{i+1}_{counter}.{self.output_format_input.currentText()}"
                    image_path = os.path.join(self.save_dir_input.text(), new_name)
                    counter += 1
                urlretrieve(image_url, image_path)

                if (
                    self.save_metadata_checkbox is not None
                    and self.save_metadata_checkbox.isChecked()
                ):
                    self.add_metadata_to_image(
                        image_path, self.prompt_input.toPlainText()
                    )
                else:
                    print("Warning: save_metadata_checkbox is None or not checked")

                new_image_paths.append(image_path)
            else:
                image_path = f"temp_image_{i}.{self.output_format_input.currentText()}"
                urlretrieve(image_url, image_path)
                new_image_paths.append(image_path)

        self.updateGallery(new_image_paths)

        if not self.auto_save_checkbox.isChecked():
            for path in new_image_paths:
                os.remove(path)

    def add_metadata_to_image(self, image_path, prompt):
        try:
            with Image.open(image_path) as img:
                if img.format == "PNG":
                    metadata = PngInfo()
                    metadata.add_text("prompt", prompt)
                    img.save(image_path, pnginfo=metadata)
                elif img.format in ["JPEG", "WEBP"]:
                    exif = img.getexif()
                    exif[0x9286] = prompt
                    img.save(image_path, exif=exif)
        except Exception as e:
            print(f"Error adding metadata to {image_path}: {str(e)}")

    def loadSettings(self):
        self.prompt_input.setPlainText(self.settings.value("prompt", ""))
        self.aspect_ratio_input.setCurrentText(
            self.settings.value("aspect_ratio", "1:1")
        )
        self.num_outputs_input.setValue(int(self.settings.value("num_outputs", 1)))
        self.num_inference_steps_input.setValue(
            int(self.settings.value("num_inference_steps", 28))
        )
        self.guidance_scale_input.setValue(
            float(self.settings.value("guidance_scale", 3.5))
        )
        self.seed_input.setValue(int(self.settings.value("seed", -2147483648)))
        self.output_format_input.setCurrentText(
            self.settings.value("output_format", "webp")
        )
        self.output_quality_input.setValue(
            int(self.settings.value("output_quality", 80))
        )
        self.hf_lora_input.setText(self.settings.value("hf_lora", ""))
        self.lora_scale_input.setValue(float(self.settings.value("lora_scale", 0.8)))
        self.disable_safety_checker_input.setChecked(
            self.settings.value("disable_safety_checker", True, type=bool)
        )
        self.auto_save_checkbox.setChecked(
            self.settings.value("auto_save", True, type=bool)
        )
        self.save_dir_input.setText(
            self.settings.value(
                "save_directory", os.path.expanduser("~/Downloads/replicate")
            )
        )
        self.save_metadata_checkbox.setChecked(
            self.settings.value("save_metadata", False, type=bool)
        )
        self.loadImagesAsync()

    def saveSettings(self):
        self.settings.setValue("prompt", self.prompt_input.toPlainText())
        self.settings.setValue("aspect_ratio", self.aspect_ratio_input.currentText())
        self.settings.setValue("num_outputs", self.num_outputs_input.value())
        self.settings.setValue(
            "num_inference_steps", self.num_inference_steps_input.value()
        )
        self.settings.setValue("guidance_scale", self.guidance_scale_input.value())
        self.settings.setValue("seed", self.seed_input.value())
        self.settings.setValue("output_format", self.output_format_input.currentText())
        self.settings.setValue("output_quality", self.output_quality_input.value())
        self.settings.setValue("hf_lora", self.hf_lora_input.text())
        self.settings.setValue("lora_scale", self.lora_scale_input.value())
        self.settings.setValue(
            "disable_safety_checker", self.disable_safety_checker_input.isChecked()
        )
        self.settings.setValue("auto_save", self.auto_save_checkbox.isChecked())
        self.settings.setValue("save_directory", self.save_dir_input.text())

        if self.save_metadata_checkbox is not None:
            self.settings.setValue(
                "save_metadata", self.save_metadata_checkbox.isChecked()
            )
        else:
            print("Warning: save_metadata_checkbox is None")

    def choose_save_directory(self):
        dir_path = QFileDialog.getExistingDirectory(self, "Choose Save Directory")
        if dir_path:
            self.save_dir_input.setText(dir_path)
            self.saveSettings()
            self.loadImagesAsync()

    def generate_images(self):
        params = {
            "prompt": self.prompt_input.toPlainText(),
            "aspect_ratio": self.aspect_ratio_input.currentText(),
            "num_outputs": self.num_outputs_input.value(),
            "num_inference_steps": self.num_inference_steps_input.value(),
            "guidance_scale": self.guidance_scale_input.value(),
            "output_format": self.output_format_input.currentText(),
            "output_quality": self.output_quality_input.value(),
            "hf_lora": self.hf_lora_input.text(),
            "lora_scale": self.lora_scale_input.value(),
            "disable_safety_checker": self.disable_safety_checker_input.isChecked(),
        }

        if self.seed_input.value() != self.seed_input.minimum():
            params["seed"] = self.seed_input.value()

        if not params["prompt"]:
            QMessageBox.warning(self, "Error", "Please enter a prompt.")
            return

        self.saveSettings()
        self.clear_images()
        self.progress_bar.show()
        self.generate_button.setEnabled(False)

        self.current_thread = ImageGeneratorThread(params)
        self.current_thread.finished.connect(self.display_images)
        self.current_thread.error.connect(self.show_error)
        self.current_thread.start()

        self.interrupt_button.setEnabled(True)

    def interrupt_generation(self):
        if self.current_thread and self.current_thread.isRunning():
            self.current_thread.terminate()
            self.current_thread.wait()
            self.show_error("Image generation interrupted by user.")
        self.interrupt_button.setEnabled(False)

    def show_error(self, error_message):
        self.progress_bar.hide()
        self.generate_button.setEnabled(True)
        QMessageBox.critical(self, "Error", f"An error occurred: {error_message}")
        self.interrupt_button.setEnabled(False)

    def clear_images(self):
        for i in reversed(range(self.gallery_layout.count())):
            self.gallery_layout.itemAt(i).widget().setParent(None)

    def closeEvent(self, event):
        self.saveSettings()
        super().closeEvent(event)

if __name__ == "__main__":
    app = QApplication([])
    ex = ImageGeneratorGUI()
    ex.show()
    app.exec()
