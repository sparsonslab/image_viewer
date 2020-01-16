

from enum import Enum
from typing import Tuple
import copy

from abc import ABCMeta, abstractmethod

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
    QThread,
    QVariant,
    QPointF,
    QRectF
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
        self.scene = QGraphicsScene(0, 0, 400, 200)
        self.scene.addItem(RectangleRoi(50, 10, 50, 40))
        self.scene.addItem(RectangleRoi(100, 50, 100, 20))
        self.scene.addItem(EllipseRoi(75, 20, 60, 20))
        self.scene.addItem(EllipseRoi(120, 70, 8, 8))

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


class AnchorPosition(Enum):
    """ ROI anchor positions
    """
    LEFT = 0
    RIGHT = 1
    TOP = 2
    TOP_LEFT = 3
    TOP_RIGHT = 4
    BOTTOM = 5
    BOTTOM_LEFT = 6
    BOTTOM_RIGHT = 7
    START = 8
    MIDDLE = 9
    END = 10


class Anchor(QGraphicsRectItem):
    """ Anchor for adjusting the size/shape of an ROI.
    """

    def __init__(self, anchor_position: AnchorPosition, parent_roi: QGraphicsItem, anchor_size: int = 4):
        # create a rectangular graphics item as a child of the parent ROI
        super().__init__(0, 0, anchor_size, anchor_size, parent_roi)
        self.setPos(0, 0)
        # position
        self.position = anchor_position
        # enable selection (for adjusting the ROI)
        self.setEnabled(True)
        self.setFlag(QGraphicsItem.ItemIsSelectable)


class SelectionRoi(QGraphicsItem):
    """ Base class for all ROIs.
    """

    def __init__(self):
        # create graphics item
        super(SelectionRoi, self).__init__()
        # enable selection and dragging
        self.setEnabled(True)
        self.setFlag(QGraphicsItem.ItemIsSelectable)
        self.setFlag(QGraphicsItem.ItemIsMovable)
        # create anchors as graphics children to this ROI
        self.anchors = [Anchor(x, self) for x in self.get_anchor_types()]
        # make sure anchor events are filtered by this ROI - SelectionRoi::sceneEventFilter()
        self.setFiltersChildEvents(True)

    def sceneEventFilter(self, watched: QGraphicsItem, event: QEvent) -> bool:
        """ Override of QGraphicsItem::sceneEventFilter
            Responds to events initiated by anchors (graphics children).
            Adjusts the ROI and anchors in response to a mouse drag on the anchors.

        @param watched: anchor (graphics child)
        @param event: graphics scene event
        @return: should always be False to allow the event to propagate further.
        """

        # check event is a mouse drag of an anchor
        if isinstance(watched, Anchor) and isinstance(event, QGraphicsSceneMouseEvent):
            self.adjust_roi(watched, event.pos())

        # continue processing
        return False

    @abstractmethod
    def get_anchor_types(self) -> list:
        """ Get list of the anchor type of this ROI.

        @return: list of anchor types
        """
        pass

    @abstractmethod
    def adjust_roi(self, point: Anchor, mouse: QPointF):
        """ Adjust the ROI.

        @param point: anchor dragged
        @param mouse: point where mouse has been dragged to.
        """
        pass

    @abstractmethod
    def adjust_anchors(self):
        """ Adjust the anchor positions, after the ROI been adjusted
        """
        pass

    @staticmethod
    def adjust_regular_roi_bounds(rect: QRectF, point: Anchor, mouse: QPointF) -> QRectF:
        """ Get the new bounding rectangle of a "regular" ROI (rectangle or ellipse) after dragging of anchor.

        @param rect: original bounding rectangle.
        @param point: anchor that has been dragged.
        @param mouse: point that mouse has been dragged to.
        @return: new bounding rectangle.
        """
        if point.position == AnchorPosition.LEFT:
            rect.setLeft(rect.left() + mouse.x())
        elif point.position == AnchorPosition.RIGHT:
            rect.setRight(rect.right() + mouse.x())
        elif point.position == AnchorPosition.TOP:
            rect.setTop(rect.top() + mouse.y())
        elif point.position == AnchorPosition.TOP_LEFT:
            rect.setLeft(rect.left() + mouse.x())
            rect.setTop(rect.top() + mouse.y())
        elif point.position == AnchorPosition.TOP_RIGHT:
            rect.setRight(rect.right() + mouse.x())
            rect.setTop(rect.top() + mouse.y())
        elif point.position == AnchorPosition.BOTTOM:
            rect.setBottom(rect.bottom() + mouse.y())
        elif point.position == AnchorPosition.BOTTOM_LEFT:
            rect.setLeft(rect.left() + mouse.x())
            rect.setBottom(rect.bottom() + mouse.y())
        elif point.position == AnchorPosition.BOTTOM_RIGHT:
            rect.setRight(rect.right() + mouse.x())
            rect.setBottom(rect.bottom() + mouse.y())
        return rect

    @staticmethod
    def adjust_regular_roi_anchors(bounds: QRectF, anchors: list):
        """ Adjust the anchors of a "regular" ROI (rectangle or ellipse)

        @param bounds: bounding rectangle of ROI
        @param anchors: list of anchors
        """
        for point in anchors:
            off = point.boundingRect().width() / 2
            if point.position == AnchorPosition.LEFT:
                point.setPos(bounds.left() - off, bounds.top() - off + bounds.height() / 2)
            elif point.position == AnchorPosition.RIGHT:
                point.setPos(bounds.right() - off, bounds.top() - off + bounds.height() / 2)
            elif point.position == AnchorPosition.TOP:
                point.setPos(bounds.left() - off + bounds.width() / 2, bounds.top() - off)
            elif point.position == AnchorPosition.TOP_LEFT:
                point.setPos(bounds.left() - off, bounds.top() - off)
            elif point.position == AnchorPosition.TOP_RIGHT:
                point.setPos(bounds.right() - off, bounds.top() - off)
            elif point.position == AnchorPosition.BOTTOM:
                point.setPos(bounds.left() - off + bounds.width() / 2, bounds.bottom() - off)
            elif point.position == AnchorPosition.BOTTOM_LEFT:
                point.setPos(bounds.left() - off, bounds.bottom() - off)
            elif point.position == AnchorPosition.BOTTOM_RIGHT:
                point.setPos(bounds.right() - off, bounds.bottom() - off)


class RectangleRoi(QGraphicsRectItem, SelectionRoi):
    """ Rectangle ROI.
    """

    def __init__(self, x0: int, y0: int, width: int, height: int):
        # super - make sure constructors for both QGraphicsRectItem and SelectionRoi and called.
        super(RectangleRoi, self).__init__()
        # set positions of ROI and anchors
        self.setRect(x0, y0, width, height)
        self.setPos(x0, y0)
        self.adjust_anchors()

    # ------------------------------------------------
    # Implement SelectionRoi methods
    # ------------------------------------------------

    def get_anchor_types(self) -> list:
        return [AnchorPosition.LEFT,
                AnchorPosition.RIGHT,
                AnchorPosition.TOP,
                AnchorPosition.TOP_LEFT,
                AnchorPosition.TOP_RIGHT,
                AnchorPosition.BOTTOM,
                AnchorPosition.BOTTOM_LEFT,
                AnchorPosition.BOTTOM_RIGHT]

    def adjust_roi(self, point: Anchor, mouse: QPointF):
        self.setRect(SelectionRoi.adjust_regular_roi_bounds(self.rect(), point, mouse))
        self.adjust_anchors()

    def adjust_anchors(self):
        SelectionRoi.adjust_regular_roi_anchors(self.boundingRect(), self.anchors)


class EllipseRoi(QGraphicsEllipseItem, SelectionRoi):
    """ Rectangle ROI.
    """

    def __init__(self, x0: int, y0: int, width: int, height: int):
        # super - make sure constructors for both QGraphicsRectItem and SelectionRoi and called.
        super(EllipseRoi, self).__init__()
        # set positions of ROI and anchors
        self.setRect(x0, y0, width, height)
        self.setPos(x0, y0)
        self.adjust_anchors()

    # ------------------------------------------------
    # Implement SelectionRoi methods
    # ------------------------------------------------

    def get_anchor_types(self) -> list:
        return [AnchorPosition.LEFT,
                AnchorPosition.RIGHT,
                AnchorPosition.TOP,
                AnchorPosition.BOTTOM]

    def adjust_roi(self, point: Anchor, mouse: QPointF):
        self.setRect(SelectionRoi.adjust_regular_roi_bounds(self.rect(), point, mouse))
        self.adjust_anchors()

    def adjust_anchors(self):
        SelectionRoi.adjust_regular_roi_anchors(self.boundingRect(), self.anchors)

# main program
if __name__ == '__main__':

    app = QApplication([])

    myviewer = ImageViewer()
    myviewer.show()

    app.exec_()
