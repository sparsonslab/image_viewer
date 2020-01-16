

from enum import Enum
from typing import Tuple
import copy

from abc import ABCMeta, abstractmethod

from PyQt5.QtWidgets import (
    QWidget,
    QGraphicsView,
    QGraphicsScene,
    QGraphicsPathItem,
    QGraphicsLineItem,
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
    QPixmap,
    QPainterPath
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
        self.scene.addItem(LineRoi(10, 10, 60, 50))
        self.scene.addItem(PathRoi([60, 65, 75], [60, 76, 50], is_closed=True, is_anchored=True))

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
        self.roi = parent_roi
        self.setPos(0, 0)
        # position
        self.position = anchor_position
        # enable selection (for adjusting the ROI)
        self.setEnabled(True)
        self.setFlag(QGraphicsItem.ItemIsSelectable)

    def mouseMoveEvent(self, event: QGraphicsSceneMouseEvent):
        """ Adjust the parent ROI in response to a mouse drag on the anchor.
        """
        self.roi.adjust_roi(self, event.pos())
        event.ignore()


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

    @abstractmethod
    def get_anchor_types(self) -> list:
        """ Get list of the anchor type of this ROI.

        @return: list of anchor types
        """
        pass

    @abstractmethod
    def adjust_roi(self, point: Anchor, mouse: QPointF):
        """ Adjust the ROI size/position/etc in response to a change in an anchor position to mouse.

        @param point: anchor dragged
        @param mouse: point where mouse has been dragged to.
        """
        pass

    @abstractmethod
    def adjust_anchors(self):
        """ Adjust the anchor positions to the ROI.
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

        return rect.normalized()  # normalised() causes width/height to go to zero when dragging to negative

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


class PathRoi(QGraphicsPathItem, SelectionRoi):
    """ Path ROI
    """

    def __init__(self, x: list, y: list, is_closed: bool = False, is_anchored: bool = True):

        self.n_points = min(len(x), len(y))
        self.is_closed = is_closed
        self.is_anchored = is_anchored

        # super - make sure constructors for both QGraphicsPathItem and SelectionRoi are called.
        super(PathRoi, self).__init__()

        # set path
        path = QPainterPath(QPointF(x[0], y[0]))
        for i in range(1, self.n_points):
            path.lineTo(x[i], y[i])
        if self.is_closed:
            path.closeSubpath()
        self.setPath(path)
        # set anchors
        self.adjust_anchors()

    # ------------------------------------------------
    # Implement SelectionRoi methods
    # ------------------------------------------------

    def get_anchor_types(self) -> list:
        path = self.path()
        anchors = [AnchorPosition.START]
        if self.is_anchored:
            for i in range(self.n_points - 2):
                anchors.append(AnchorPosition.MIDDLE)
            anchors.append(AnchorPosition.END)
        return anchors

    def adjust_roi(self, point: Anchor, mouse: QPointF):
        # non-anchored: translate
        if not self.is_anchored:
            self.moveBy(mouse.x(), mouse.y())
            return None
        # anchored: move point
        path = self.path()
        for i in range(len(self.anchors)):
            if self.anchors[i] == point:
                path_element = path.elementAt(i)
                path.setElementPositionAt(i, path_element.x + mouse.x() , path_element.y + mouse.y())
                if i == 0 and self.is_closed:
                    path.setElementPositionAt(path.elementCount() - 1, path_element.x + mouse.x(), path_element.y + mouse.y())
                break
        self.setPath(path)
        self.adjust_anchors()

    def adjust_anchors(self):
        path = self.path()
        for i in range(len(self.anchors)):
            point = self.anchors[i]
            path_element = path.elementAt(i)
            off = point.boundingRect().width() / 2
            point.setPos(path_element.x - off, path_element.y - off)


class LineRoi(QGraphicsLineItem, SelectionRoi):
    """ Line ROI.
    """

    def __init__(self, x0: int, y0: int, x1: int, y1: int):
        # super - make sure constructors for both QGraphicsRectItem and SelectionRoi are called.
        super(LineRoi, self).__init__()
        # set ROI and anchors
        self.setLine(x0, y0, x1, y1)
        self.adjust_anchors()

    # ------------------------------------------------
    # Implement SelectionRoi methods
    # ------------------------------------------------

    def get_anchor_types(self) -> list:
        return [AnchorPosition.START,
                AnchorPosition.MIDDLE,
                AnchorPosition.END]

    def adjust_roi(self, point: Anchor, mouse: QPointF):

        line = self.line()
        if point.position == AnchorPosition.START:
            self.setLine(line.x1() + mouse.x(), line.y1() + mouse.y(), line.x2(), line.y2())
        elif point.position == AnchorPosition.MIDDLE:
            self.moveBy(mouse.x(), mouse.y())
        elif point.position == AnchorPosition.END:
            self.setLine(line.x1(), line.y1(), line.x2() + mouse.x(), line.y2() + mouse.y())
        self.adjust_anchors()

    def adjust_anchors(self):

        line = self.line()
        for point in self.anchors:
            off = point.boundingRect().width() / 2
            if point.position == AnchorPosition.START:
                point.setPos(line.x1() - off, line.y1() - off)
            elif point.position == AnchorPosition.MIDDLE:
                point.setPos(line.x1() + (line.x2() - line.x1())/2 - off, line.y1() + (line.y2() - line.y1())/2 - off)
            elif point.position == AnchorPosition.END:
                point.setPos(line.x2() - off, line.y2() - off)


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
