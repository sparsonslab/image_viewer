

from SelectionRoi import (
    SelectionRoi,
    PointRoi,
    PathRoi,
    RectangleRoi,
    EllipseRoi,
    RoiSelectionButton
)

from PyQt5.QtWidgets import (
    QWidget,
    QGraphicsView,
    QGraphicsScene,
    QBoxLayout,
    QApplication,
    QHBoxLayout,
    QPushButton
)

from PyQt5.QtCore import (
    Qt,
    QRectF
)
from PyQt5.QtGui import (
    QImage,
    QPainter,
    QKeyEvent
)

# ------------------------------------------------
# Image scene and viewer
# ------------------------------------------------


class ImageScene(QGraphicsScene):
    """ Graphics scene with image background and possibly ROIs.
    """

    def __init__(self, image: QImage):
        """
        @param image: image to draw on scene.
        """
        super().__init__(0, 0, image.width(), image.height())
        # image
        self.image = image
        # ROIs
        self.rois = []
        # hide/show anchors according to ROI focus
        self.selectionChanged.connect(self.change_selected_item)

    def drawBackground(self, painter: QPainter, rect: QRectF):
        """ Overrides QGraphicsScene::drawBackground, so image will be drawn on scene.
        """
        bounds = QRectF(0, 0, self.image.width(), self.image.height())
        painter.drawImage(bounds, image)

    def add_roi(self, roi: SelectionRoi):
        """ Add an ROI
        """
        self.rois.append(roi)
        self.addItem(roi)

    def adjust_roi_scale(self, scale: float):
        for roi in self.rois:
            roi.set_to_scale(scale)

    def change_selected_item(self):
        """ Slot for item selection: ROI anchors only visible upon selection.
        """
        selected_items = self.selectedItems()
        for x in self.rois:
            x.hide_anchors()
            for y in selected_items:
                if x.has_item(y):
                    x.show_anchors()
                    break


class ImageMenu(QWidget):
    """ Menu for ROIs/etc
    """

    def __init__(self, parent: QWidget):

        super().__init__(parent)

        # roi selection
        self.roi_button = RoiSelectionButton(self)

        # layout
        layout = QBoxLayout(QBoxLayout.LeftToRight)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.roi_button)
        layout.setAlignment(self.roi_button, Qt.AlignLeft)
        self.setLayout(layout)
        self.adjustSize()
        self.setStyleSheet("border: 1px solid red")


class ImageViewer(QWidget):
    """ Image with graphics scene to allow drawing of ROIs
    """

    def __init__(self, image: QImage):
        """
        @param image: image to show
        """

        # GUI constructor
        super().__init__()

        # graphics scene
        self.scene = ImageScene(image)

        # ROIs
        self.scene.add_roi(RectangleRoi(50, 10, 50, 40))
        self.scene.add_roi(RectangleRoi(100, 50, 100, 20))
        self.scene.add_roi(EllipseRoi(75, 20, 60, 20))
        self.scene.rois[-1].set_properties(color_rgb=[255, 0, 0], line_width=6.0)
        self.scene.add_roi(EllipseRoi(120, 70, 8, 8))
        self.scene.add_roi(PathRoi([10, 60], [10, 50], is_closed=False, is_anchored=True))
        self.scene.rois[-1].set_properties(color_rgb=[30, 255, 0], line_width=6.0)
        self.scene.add_roi(PathRoi([60, 65, 75], [60, 76, 50], is_closed=True, is_anchored=True))
        self.scene.add_roi(PointRoi(120, 50, size=6))

        # graphics view
        self.viewer = QGraphicsView(self.scene)
        self.viewer.setSceneRect(0, 0, self.scene.width(), self.scene.height())
        self.viewer.setInteractive(True)
        self.viewer.show()
        self.scale = 1.0

        # menu
        self.menu = ImageMenu(self)

        # layout
        layout = QBoxLayout(QBoxLayout.TopToBottom)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.menu)
        layout.addWidget(self.viewer)
        self.setLayout(layout)

        #self.resize(self.scene.width(), self.scene.height())

    def keyPressEvent(self, event: QKeyEvent):
        """ Zoom in and out (+ and - keys).
            Overrides QGraphicsView::keyPressEvent
        """
        if event.key() == Qt.Key_Plus or event.key() == Qt.Key_Minus:
            if event.key() == Qt.Key_Plus:
                self.scale *= 1.2
            else:
                self.scale /= 1.2
            self.viewer.resetTransform()
            self.viewer.scale(self.scale, self.scale)
            self.scene.adjust_roi_scale(self.scale)

        event.accept()


# main program
if __name__ == '__main__':

    app = QApplication([])

    image = QImage('C:\\Users\\spars\\Pictures\\niagara.jpg')
    print(image.height(), image.height())

    myviewer = ImageViewer(image)
    myviewer.show()

    app.exec_()
