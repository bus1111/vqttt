import qtpy
import random
from qtpy.QtGui import QColor
from qtpy.QtCore import QMetaObject
from qtpy.QtWidgets import QDesktopWidget


def center_widget_on_screen(widget):
    rect = widget.frameGeometry()
    center = QDesktopWidget().availableGeometry().center()
    rect.moveCenter(center)
    widget.move(rect.topLeft())


def get_random_color(seed=None):
    if seed is None:
        seed = random.randint(0, 1000000)
    color = QColor()
    color.setHsl(((seed + 6) * 33 + random.random() * 6) % 360, 100, 98)
    return color


if qtpy.PYSIDE2:
    from qtpy.uic import UiLoader

    def loadUi(uifile, baseinstance=None):
        loader = UiLoader(baseinstance, None)
        widget = loader.load(uifile)
        QMetaObject.connectSlotsByName(widget)
        return widget
else:
    from qtpy.uic import loadUi
