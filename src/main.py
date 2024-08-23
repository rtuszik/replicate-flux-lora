from gui import ImageGeneratorGUI
from image_generator import ImageGenerator
from PyQt6.QtWidgets import QApplication


def main():
    app = QApplication([])
    generator = ImageGenerator()
    window = ImageGeneratorGUI(generator)
    window.show()
    app.exec()


if __name__ == "__main__":
    main()
