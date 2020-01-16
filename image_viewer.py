from PyQt5.QtWidgets import (
    QWidget,
    QGraphicsView,
    QGraphicsScene,
    QGraphicsRectItem,
    QGraphicsEllipseItem,
    QGraphicsItem,
    QAbstractGraphicsShapeItem,
    QSplitter,
    QVBoxLayout,
    QTableWidgetItem,
    QPlainTextEdit,
    QMenu,
    QTableWidget,
    QAbstractItemView,
    QAction,
    QInputDialog,
    QApplication,
    QGraphicsSceneMouseEvent,
    QGraphicsSceneDragDropEvent
)
from PyQt5.QtCore import (
    Qt,
    QEvent,
    QObject,
    QPoint,
    QThread
)
from PyQt5.QtGui import (
    QImage,
    QColor,
    QPixmap
)

class ImageViewer(QWidget):
    """ The main window of the GUI.
    """

    def __init__(self):
        """ Initiate the GUI with some text-format data.

        @param text: data text (comma or tab delimited string)
        """

        # GUI constructor
        super().__init__()

        # graphics scene
        #self.scene = RoiScene(500, 200)
        #self.scene.add_roi(QGraphicsEllipseItem(0, 0, 60, 30), 20, 30)
        #self.scene.add_roi(QGraphicsRectItem(0, 0, 60, 20), 300, 40)
        #self.scene.add_roi(RoiSelection(400, 150), 400, 150)

        self.scene = QGraphicsScene(0, 0, 500, 200)
        self.scene.addItem(RoiSelection(100, 100))
        self.scene.addItem(RoiSelection(400, 150))

        #self.scene.addItem(RoiSelection(20, 50))
        #self.scene.addItem(RoiSelection(200, 50))
        #self.scene.focusItemChanged.connect(lambda: self.scene_focus_item_changed())
        #self.scene.changed.connect(lambda: self.scene_changed())

        # graphics view
        self.viewer = QGraphicsView(self.scene)
        self.viewer.setSceneRect(0, 0, self.scene.width(), self.scene.height())
        self.viewer.setInteractive(True)
        self.viewer.show()

        # layout
        layout = QVBoxLayout()
        layout.addWidget(self.viewer)
        self.setLayout(layout)
        self.resize(self.scene.width(), self.scene.height())


class RoiSelection(QGraphicsRectItem):

    def __init__(self, x0: int, y0: int):
        super().__init__(0, 0, 50, 40)
        self.setPos(x0, y0)
        self.setEnabled(True)

        self.setActive(True)
        self.setFlag(QGraphicsItem.ItemIsSelectable)
        self.setFlag(QGraphicsItem.ItemIsMovable)
        self.setAcceptDrops(True)

    def mouseDoubleClickEvent(self, event: QGraphicsSceneMouseEvent):
        print('helo', self.pos().x())
        event.acceptProposedAction()

    def dragMoveEvent(self, event: QGraphicsSceneDragDropEvent):
       print('dragged')
       event.acceptProposedAction()

    def dropEvent(self, event: QGraphicsSceneDragDropEvent):
        print('dropped')
        event.acceptProposedAction()

    def dragEnterEvent(self, event: QGraphicsSceneDragDropEvent):
        print('drag enter')
        event.acceptProposedAction()

    def dragLeaveEvent(self, event: QGraphicsSceneDragDropEvent):
        print('drag leave')
        event.acceptProposedAction()



class RoiScene(QGraphicsScene):

    def __init__(self, width: int, height: int):
        super().__init__(0, 0, width, height)


    def add_roi(self, roi: QAbstractGraphicsShapeItem, x0: int, y0: int):

        roi.setPos(x0, y0)
        roi.setEnabled(True)
        roi.setAcceptDrops(True)
        roi.setFlag(QGraphicsItem.ItemIsSelectable)
        roi.setFlag(QGraphicsItem.ItemIsMovable)
        self.addItem(roi)

    def focusItemChanged(self, event: QGraphicsSceneDragDropEvent):
        print('helo')

    def dragMoveEvent(self, event: QGraphicsSceneDragDropEvent):
        print('drag move')

    def dragEnterEvent(event: QGraphicsSceneDragDropEvent):
        print('drag enter')

    def mouseDoubleClickEvent(self, event: QGraphicsSceneMouseEvent):
        print('clicked')







# main program
if __name__ == '__main__':
    app = QApplication([])

    myviewer = ImageViewer()
    myviewer.show()

    app.exec_()
