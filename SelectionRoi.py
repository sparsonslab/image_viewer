# ----------------------------------------------------------------------------------------------------
######################################################################################################
# Selectable ROIs that can be added to a QGraphicsScene.

# Sean Parsons, September 2019
######################################################################################################
# ----------------------------------------------------------------------------------------------------


import numpy as np
from enum import Enum
from abc import abstractmethod

from PyQt5.QtWidgets import (

    QGraphicsPathItem,
    QGraphicsRectItem,
    QGraphicsEllipseItem,
    QGraphicsItem,
    QAbstractGraphicsShapeItem,
    QGraphicsSceneMouseEvent,
    QPushButton,
    QWidget,
    QStyleOptionGraphicsItem
)
from PyQt5.QtCore import (
    Qt,
    QPointF
)
from PyQt5.QtGui import (
    QColor,
    QPainterPath,
    QPen,
    QIcon,
    QPixmap,
    QPainter
)

# ------------------------------------------------
# Button for ROI type selection
# ------------------------------------------------

class RoiSelectionButton(QPushButton):

    def __init__(self, parent: QWidget):

        # roi icons
        icon_size = 50
        self.roi_names, self.roi_icons = RoiSelectionButton.get_icons(size=icon_size - 8, border=4)

        super().__init__(self.roi_icons[2], '', parent)

        # style
        #self.setFixedSize(icon_size, icon_size)
        self.setStyleSheet("border: 1px black solid")

        # make it toggle
        self.setCheckable(True)
        self.toggled.connect(self.was_toggled)

    def was_toggled(self, checked: bool):
        if checked:
            self.setStyleSheet("border: 1px black dashed")
        else:
            self.setStyleSheet("border: 1px red solid")
        print(checked)

    @staticmethod
    def get_icons(size: int, border: int = 2):

        # names and example items
        roi_names = []
        roi_items = []
        extent = border + size
        roi_names.append('point')
        roi_items.append(PointRoi(border, border, size=size/4))
        roi_names.append('path')
        roi_items.append(PathRoi([border, border], [extent, extent], is_anchored=False))
        roi_names.append('rectangle')
        roi_items.append(RectangleRoi(border, border, size, size))
        roi_names.append('ellipse')
        roi_items.append(EllipseRoi(border, border, size, size))
        # icons
        roi_icons = []
        pix_map = QPixmap(size + border*2, size + border*2)
        pix_map.fill(Qt.transparent)
        pix_painter = QPainter(pix_map)
        pix_painter.setRenderHint(QPainter.Antialiasing)
        opt = QStyleOptionGraphicsItem()
        for roi in roi_items:
            #roi.setPos(border, border)
            pix_map.fill(Qt.transparent)
            roi.paint(pix_painter, opt)
            roi_icons.append(QIcon(pix_map))

        pix_painter.end()
        return roi_names, roi_icons



# ------------------------------------------------
# Anchor for ROI resizing.
# ------------------------------------------------


class AnchorPosition(Enum):
    """ ROI anchor positions relative to ROI
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

# ------------------------------------------------
# Base ROI class
# ------------------------------------------------


class SelectionRoi(QAbstractGraphicsShapeItem):
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
        self.hide_anchors()
        # "base" line width and anchor size (i.e. at scene scale = 1.0)
        self.base_line_width = 1.0
        self.base_anchor_size = 4.0
        self.color_rgb = [0, 0, 0]

    def set_properties(self, color_rgb: str = [0, 0, 0], line_width: float = 1.0, anchor_size: float = 4.0):
        """ Set properties: color, line width, anchor size
        """
        self.base_line_width = line_width
        self.base_anchor_size = anchor_size
        self.color_rgb = color_rgb
        self.set_to_scale()

    def set_to_scale(self, scene_scale: float = 1.0):
        """ Set line width and anchor size according to scale (zoom) of scene.
        """
        # pen color and width
        pen = QPen(QColor(self.color_rgb[0], self.color_rgb[1], self.color_rgb[2]))
        pen.setWidthF(self.base_line_width / scene_scale)
        # set ROI
        self.setPen(pen)
        # set anchors
        for anchor in self.anchors:
            anchor.setPen(pen)
            rect = anchor.rect()
            rect.setWidth(self.base_anchor_size / scene_scale)
            rect.setHeight(self.base_anchor_size / scene_scale)
            anchor.setRect(rect)
        self.adjust_anchors()

    # ------------------------------------------------
    # anchor visibility
    # ------------------------------------------------

    def has_item(self, item: QGraphicsItem) -> bool:
        """ Check whether an item is either the ROI or one of its anchors.
        @param item: item to check
        @return: whether the item is the ROI or one of it's anchors.
        """
        return item == self or item in self.anchors

    def show_anchors(self, do_show: bool = True):
        """ Show/hide anchors.
            Uses opacity rather than QGraphicsItem::setVisible(), as this maintains the
            mouse event handling of the anchor.
        @param do_show: show (True) or hide (False).
        """
        for x in self.anchors:
            x.setOpacity(float(do_show))

    def hide_anchors(self):
        """ Wrapper for self.show_anchors()
        """
        self.show_anchors(False)

    # ------------------------------------------------
    # selection
    # ------------------------------------------------

    def mousePressEvent(self, event: QGraphicsSceneMouseEvent):
        """ Only accept mouse press events (i.e. ROI selection) if the mouse is near to the boundary.
            Prevents selection based on larger bounding rectangle.
            Overrides QGraphicsItem::mousePressEvent.
        @param event: mouse press event
        """
        if self.distance_to_boundary(event.pos(), increment=0.005) < 4:
            event.accept()
        else:
            event.ignore()

    def distance_to_boundary(self, point: QPointF, increment: float = 0.005) -> float:
        """ Distance from point to boundary path of ROI
        @param point: point
        @param increment: increment along boundary path along which to calculate distances [0, 1)
        @return: minimum distance to boundary
        """
        boundary = self.shape()
        min_distance = SelectionRoi.distance_to_path(point, boundary)
        for p in np.arange(0.0, 1.0, increment):
            min_distance = min(min_distance, SelectionRoi.distance_to_path(point, boundary, percent=p))
        return min_distance

    @staticmethod
    def distance_to_path(point: QPointF, path: QPainterPath, percent: float = 0.0):
        bp = path.pointAtPercent(percent)
        return ((bp.x() - point.x())**2.0 + (bp.y() - point.y())**2.0)**0.5

    # ------------------------------------------------
    # ROI adjustment: methods to overridden by concrete classes.
    # ------------------------------------------------

    @abstractmethod
    def get_anchor_types(self) -> list:
        """ Get list of the anchor type of this ROI.
        @return: list of anchor types
        """
        pass

    @abstractmethod
    def adjust_roi(self, point: Anchor, mouse: QPointF):
        """ Adjust the ROI size/position/etc in response to drag from an anchor.
        @param point: anchor dragged
        @param mouse: point where mouse has been dragged to.
        """
        pass

    @abstractmethod
    def adjust_anchors(self):
        """ Adjust the anchor positions to the ROI.
        """
        pass


# ------------------------------------------------
# concrete ROI classes
# ------------------------------------------------


class PointRoi(QGraphicsEllipseItem, SelectionRoi):
    """ Point ROI
    """

    def __init__(self, x0: int, y0: int, size: int = 4):
        super(PointRoi, self).__init__()
        self.setRect(x0, y0, size, size)
        self.setPos(x0, y0)

    def get_anchor_types(self) -> list:
        return []

    def adjust_roi(self, point: Anchor, mouse: QPointF):
        pass

    def adjust_anchors(self):
        pass


class PathRoi(QGraphicsPathItem, SelectionRoi):
    """ Path ROI. Includes single line (two-element coordinate list) and polygons (is_close = True).
    """

    def __init__(self, x: list, y: list, is_closed: bool = False, is_anchored: bool = True):
        # options
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
        for i, anchor in enumerate(self.anchors):
            if anchor == point:
                path_element = path.elementAt(i)
                path.setElementPositionAt(i, path_element.x + mouse.x() , path_element.y + mouse.y())
                if i == 0 and self.is_closed:
                    path.setElementPositionAt(path.elementCount() - 1, path_element.x + mouse.x(), path_element.y + mouse.y())
                break

        self.setPath(path)
        self.adjust_anchors()

    def adjust_anchors(self):
        path = self.path()
        for i, point in enumerate(self.anchors):
            path_element = path.elementAt(i)
            off = point.boundingRect().width() / 2
            point.setPos(path_element.x - off, path_element.y - off)


class ShapeRoi(SelectionRoi):
    """  Base class for Rectangle and Ellipse ROI.
    """

    def __init__(self, x0: int, y0: int, width: int, height: int):
        super(ShapeRoi, self).__init__()
        # set positions of ROI and anchors
        self.setRect(x0, y0, width, height)
        self.setPos(x0, y0)
        self.adjust_anchors()

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
        rect = self.rect()
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
        self.setRect(rect.normalized())
        self.adjust_anchors()

    def adjust_anchors(self):
        bounds = self.boundingRect()
        for point in self.anchors:
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


class RectangleRoi(QGraphicsRectItem, ShapeRoi):
    """ Rectangle ROI.
    """

    def __init__(self, x0: int, y0: int, width: int, height: int):
        super(RectangleRoi, self).__init__(x0, y0, width, height)


class EllipseRoi(QGraphicsEllipseItem, ShapeRoi):
    """ Ellipse ROI.
    """

    def __init__(self, x0: int, y0: int, width: int, height: int):
        super(EllipseRoi, self).__init__(x0, y0, width, height)

