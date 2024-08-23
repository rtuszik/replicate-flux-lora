import os

from PyQt6.QtCore import QObject, QRunnable, QThread, pyqtSignal
from PyQt6.QtWidgets import QLabel, QVBoxLayout, QWidget


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

    def __init__(self, image_generator, params):
        super().__init__()
        self.image_generator = image_generator
        self.params = params

    def run(self):
        try:
            output = self.image_generator.generate_images(self.params)
            self.finished.emit(output)
        except Exception as e:
            self.error.emit(str(e))


class TokenCount:
    def __init__(self, model_name):
        self.model_name = model_name

    def num_tokens_from_string(self, string: str) -> int:
        # This is a simplified implementation. You might want to use a proper tokenizer here.
        return len(string.split())


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
