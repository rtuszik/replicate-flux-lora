from PyQt6.QtWidgets import QApplication

from gui import ImageGeneratorGUI
from image_generator import ImageGenerator


def main():
    app = QApplication([])
    generator = ImageGenerator()
    window = ImageGeneratorGUI(generator)
    window.show()
    app.exec()


if __name__ == "__main__":
    main()
