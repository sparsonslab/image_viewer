# -----------------------------------------------------------------------
#
# Author: Sean Parsons
# Date: September 2019
# -----------------------------------------------------------------------

""" A Qt GUI for displaying tabular data and assigning row designations (header, data or other).
"""

from enum import Enum
from typing import Tuple
import os
import re
import types
from urllib import (
    request,
    parse,
    error
)
from http import client

from PyQt5.QtWidgets import (
    QWidget,
    QSplitter,
    QVBoxLayout,
    QTableWidgetItem,
    QPlainTextEdit,
    QMenu,
    QTableWidget,
    QAbstractItemView,
    QAction,
    QInputDialog,
    QApplication
)
from PyQt5.QtCore import (
    Qt,
    QEvent,
    QObject,
    QPoint,
    QThread
)
from PyQt5.QtGui import (
    QImage
)

# ------------------------------------------------
# Class definitions
# ------------------------------------------------


class DatumViewer(QWidget):
    """ The main window of the GUI.
    """

    def __init__(self, text: str):
        """ Initiate the GUI with some text-format data.

        @param text: data text (comma or tab delimited string)
        """

        # GUI constructor
        super().__init__()

        # window title
        self.setWindowTitle('Data Viewer')

        # spread-sheet view of data
        self.spread_sheet = SheetView(self, 5, 1)
        self.spread_sheet.set_text(text)

        # "detail" view of the selected cell.
        # Useful when the cell contents are large (e.g. a long comment.)
        self.cell_view = CellView(self, '')
        self.spread_sheet.itemClicked.connect(self.item_selected)

        # vertical split layout
        splitter = QSplitter(Qt.Vertical)
        splitter.addWidget(self.spread_sheet)
        splitter.addWidget(self.cell_view)
        layout = QVBoxLayout()
        layout.addWidget(splitter)
        self.setLayout(layout)

    def item_selected(self, item: QTableWidgetItem):
        """ "Slot" that responds when a table cell is clicked.
            Causes that cell's contents to be displayed in the "cell" view.

        @param item: cell item from QTableWidget::itemClicked signal
        """
        # if item is text:
        self.cell_view.setPlainText(item.text())


class CellView(QPlainTextEdit):
    """ Just a plain text editor to show the contents of a  particular cell.
        Useful when the cell contents are large (e.g. a long comment).
    """

    def __init__(self, parent: DatumViewer, text: str):
        super().__init__(text, parent)
        self.parent_widget = parent


class RowType(Enum):
    """ The "types" that a table row can have, designated by their text color.
    """

    DATA = Qt.lightGray
    HEADER = Qt.red
    OTHER = Qt.black


class TableDimension(Enum):
    """ Row or column.
    """
    ROW = 0
    COLUMN = 1


class SimpleContextMenu(QMenu):
    """ A generic context menu.
    """

    def __init__(self, parent: QWidget, menu_name: str):
        super().__init__(menu_name, parent)
        self.parent = parent

    def set_activating_widget(self, activating_widget: QWidget):
        """ Set the widget that will activate this context menu.

        @param activating_widget:
        """
        activating_widget.setContextMenuPolicy(Qt.CustomContextMenu)
        activating_widget.customContextMenuRequested.connect(self.show_menu)

    def show_menu(self, point: QPoint):
        """ Slot that responds to customContextMenuRequested signal from parent widget.
            Activates menu.

        @param point: point of right-click by user
        """
        self.exec(self.parent.mapToGlobal(point))

    def add_action_and_slot(self, action_name: str, action_slot: types.FunctionType):
        """ Add menu items and connect these to slots.

        @param action_name: name of action in menu
        @param action_slot: slot that will respond to the item
        """
        self.addAction(QAction(action_name, self.parent))
        acts = self.actions()
        acts[-1].triggered.connect(action_slot)

    def add_separator(self):
        self.addSeparator()


class SheetView(QTableWidget):
    """ Spread-sheet view of data.
    """

    def __init__(self, parent: DatumViewer, n_col: int = 5, n_row: int = 1):
        """ Construct.

        @param parent: GUI parent widget.
        @param n_col: number of columns
        @param n_row: number of rows
        """
        super().__init__(n_row, n_col, parent)
        self.parent = parent

        # change row index with double click
        self.verticalHeader().sectionDoubleClicked.connect(self.set_row_index)

        # row/column resize
        self.verticalHeader().sectionResized.connect(self.row_resized)
        self.horizontalHeader().sectionResized.connect(self.column_resized)

        # drag-and-drop text file (tab or comma delimited)
        self.installEventFilter(self)
        self.setAcceptDrops(True)
        self.setDragDropMode(QAbstractItemView.DragDrop)

        # cell context menu
        self.assign_menu = SimpleContextMenu(self, "Cell Menu")
        self.assign_menu.set_activating_widget(self)
        self.assign_menu.add_action_and_slot('Cell to Image', lambda: self.load_selected_images())

        # row context menu
        self.row_menu = SimpleContextMenu(self, "Row Menu")
        self.row_menu.set_activating_widget(self.verticalHeader())
        self.row_menu.add_action_and_slot('Insert Row', lambda: self.insert_segment(TableDimension.ROW))
        self.row_menu.add_action_and_slot('Delete Row', lambda: self.delete_segment(TableDimension.ROW))
        self.row_menu.add_separator()
        self.row_menu.add_action_and_slot('Rows to Data', lambda: self.set_selected_row_type(RowType.DATA))
        self.row_menu.add_action_and_slot('Row to Header', lambda: self.set_selected_row_type(RowType.HEADER))
        self.row_menu.add_action_and_slot('Row to Other', lambda: self.set_selected_row_type(RowType.OTHER))

        # column context menu
        self.column_menu = SimpleContextMenu(self, "Column Menu")
        self.column_menu.set_activating_widget(self.horizontalHeader())
        self.column_menu.add_action_and_slot('Insert Column', lambda: self.insert_segment(TableDimension.COLUMN))
        self.column_menu.add_action_and_slot('Delete Column', lambda: self.delete_segment(TableDimension.COLUMN))

    # ------------------------------------------------
    # Set data
    # ------------------------------------------------

    def set_text(self, text: str):
        """ Set the displayed data from an unparsed string.

        @param text: unparsed string.
        """
        rows = text.split('\n')
        self.set_row_data(rows)

    def set_row_data(self, rows: list, min_cols: int = -1, max_search_index: int = 2000) -> bool:
        """ Set the displayed data from a list of strings, each string a row.

        @param rows: list of row strings.
        @param min_cols: minimum no. of columns.
        @param max_search_index: max row index to search when determining delimiter type and column number.
        @return False if the row list was empty.
        """

        # empty row list
        if not rows:
            self.setRowCount(1)
            self.setColumnCount(5)
            if min_cols > 0:
                self.setColumnCount(min_cols)
            return False
        n_row = len(rows)

        # detect delimiter (comma or tab): just compare the number of tabs and commas
        delimiter = '\t'
        n_tab = 0
        n_comma = 0
        for i in range(min(max_search_index, n_row)):
            n_tab += rows[i].count('\t')
            n_comma += rows[i].count(',')
        if n_comma > n_tab:
            delimiter = ','

        # determine number of columns
        n_col = 0
        for i in range(min(max_search_index, n_row)):
            n = len(rows[i].split(delimiter))
            if n > n_col:
                n_col = n
        if n_col < min_cols:
            n_col = min_cols

        # set cell data
        self.setRowCount(n_row)
        self.setColumnCount(n_col)
        rgx = re.compile('[\n\r]')   # for removing line end delimiters
        for i in range(n_row):
            # remove any line-end delimiters still present
            rows[i] = rgx.sub('', rows[i])
            # split row into items
            cols = rows[i].split(delimiter)
            # set items
            for j in range(n_col):
                if j < len(cols):
                    self.setItem(i, j, QTableWidgetItem(cols[j]))
                else:
                    self.setItem(i, j, QTableWidgetItem(""))

        # reset designations
        self.reset_row_types()

        # resize row heights
        self.resizeRowsToContents()

        return True

    # ------------------------------------------------
    # Row indexes
    # ------------------------------------------------

    def set_row_index(self, index: int):
        """ A "slot" that responds to double-click signals on the vertical-header of the spread-sheet.
            The vertical-header of the spread-sheet contains the "row indices".
            This function opens a dialog for editing the text of a row-index.

        @param index: index clicked from signal QHeaderView::sectionDoubleClicked
        """

        # initial row index text
        current_index_name = ''
        try:
            current_index_name = self.verticalHeaderItem(index).text()
        except:   # cannot find out what exception is thrown - poor documentation!
            pass

        # create dialog
        input_string, pressed_ok = QInputDialog.getText(self, '', 'Row index:', text=current_index_name)
        if pressed_ok:
            # ... if "okay" button pressed, set row index
            self.setVerticalHeaderItem(index, QTableWidgetItem(input_string))
            # adjust width of vertical header to new text
            self.verticalHeader().geometriesChanged.emit()

    # ------------------------------------------------
    # Drag-and-drop text file
    # ------------------------------------------------

    def eventFilter(self, obj: QObject, event: QEvent):
        """ Implementation of QObject::eventFilter()
            Intercept drag-and-drop events before they are passed to the QTableWidget.
            In response to the drop of a text (.txt or .csv) file, opens that file.

        @param obj: the "watched object" that events are intercepted from (self in our case)
        @param event: the event
        @return: whether the event is accepted or rejected for further processing.
        """

        if event.type() == QEvent.Drop:
            event.accept()
            mime = event.mimeData()
            if mime.hasText():
                file_path = mime.text()
                if file_path.endswith('.txt') or file_path.endswith('.csv'):
                    file_path = file_path.replace('file:///', '')
                    with open(file_path) as reader:
                        rows = reader.readlines()
                        if rows:
                            self.set_row_data(rows)
                            self.parent.setWindowTitle(os.path.basename(file_path))

            return True
        elif event.type() == QEvent.DragEnter:
            event.accept()
            return True
        return False

    # ------------------------------------------------
    # Insert and Delete
    # ------------------------------------------------

    def insert_segment(self, dimension: TableDimension):
        """ Respond to selection of "Insert" item in row-menu
        """
        [selection_row_start, selection_row_end, selection_col_start, selection_col_end] = self.get_selected_range()
        if dimension == TableDimension.ROW:
            self.insertRow(selection_row_start)
        else:
            self.insertColumn(selection_col_start)

    def delete_segment(self, dimension: TableDimension):
        """ Respond to selection of "Delete" item in row-menu
        """
        [selection_row_start, selection_row_end, selection_col_start, selection_col_end] = self.get_selected_range()
        if dimension == TableDimension.ROW:
            for i in range(1 + selection_row_end - selection_row_start):
                self.removeRow(selection_row_start)
        else:
            for i in range(1 + selection_col_end - selection_col_start):
                self.removeColumn(selection_col_start)

    # ------------------------------------------------
    # Row designations
    # ------------------------------------------------

    def set_selected_row_type(self, rtype: RowType) -> bool:
        """ Set the row-type (HEADER | DATA | OTHER) of the selected rows.

        @param rtype: row type.
        @return: True if type has been set successfully.
        """

        # selected rows
        [selection_row_start, selection_row_end, selection_col_start, selection_col_end] = self.get_selected_range()
        if (selection_row_start < 0) or (selection_row_end < 0):
            return False

        # current row types
        [head_rows, data_row_start] = self.get_row_types()

        # modify types
        if rtype == RowType.DATA:
            # set start of data
            data_row_start = selection_row_start
            # remove any overlapping headers
            head_rows = [row for row in head_rows if row < data_row_start]
        elif rtype == RowType.HEADER:
            # append header with selected rows before data
            for i in range(selection_row_start, selection_row_end + 1):
                if (data_row_start == -1) or (i < data_row_start):
                    head_rows.append(i)
            # remove duplicates
            head_rows = list(set(head_rows))
        elif rtype == RowType.OTHER:
            # filter out headers
            head_rows = [row for row in head_rows if (row < selection_row_start) or (row > selection_row_end)]

        # update types (i.e. actual block/row colors)
        for i in range(self.rowCount()):
            if i in head_rows:
                for j in range(self.columnCount()):
                    self.item(i, j).setForeground(RowType.HEADER.value)
            elif (data_row_start > 0) and (i >= data_row_start):
                for j in range(self.columnCount()):
                    self.item(i, j).setForeground(RowType.DATA.value)
            else:
                for j in range(self.columnCount()):
                    self.item(i, j).setForeground(RowType.OTHER.value)

    def reset_row_types(self):
        """ Set all row types to OTHER
        """
        for i in range(self.rowCount()):
            for j in range(self.columnCount()):
                self.item(i, j).setForeground(RowType.OTHER.value)

    def get_row_types(self) -> Tuple[list, int]:
        """ Get the current row types.

        @return: head_rows - a list of the indices of HEADER rows
                 data_first_row - the index of the first DATA row or -1 if there are no DATA rows
        """
        head_rows = []       # list of header row indices
        data_first_row = -1  # first data row index
        for i in range(self.rowCount()):
            print(i, '...')
            text_color = self.item(i, 0).foreground().color()
            print(i, text_color)
            if text_color == RowType.HEADER.value:
                head_rows.append(i)
            elif text_color == RowType.DATA.value:
                data_first_row = i
                break

        return head_rows, data_first_row

    # ------------------------------------------------
    # Selections
    # ------------------------------------------------

    def get_selected_range(self) -> Tuple[int, int, int, int]:
        """ Get the selected range of rows and columns.

        @return: list of [first row index, last row index, first column index, last column index]
                 or [-1, -1, -1, -1] if no selection has been made
        """

        selected_indexes = self.selectedIndexes()
        if selected_indexes:
            row_start = selected_indexes[0].row()
            row_end = selected_indexes[0].row()
            col_start = selected_indexes[0].column()
            col_end = selected_indexes[0].column()
            for x in selected_indexes:
                if x.row() < row_start:
                    row_start = x.row()
                elif x.row() > row_end:
                    row_end = x.row()
                if x.column() < col_start:
                    col_start = x.column()
                elif x.column() > col_end:
                    col_end = x.column()
            return row_start, row_end, col_start, col_end
        return -1, -1, -1, -1

    # ------------------------------------------------
    # Images
    # ------------------------------------------------

    def load_selected_images(self):
        """  Slot for responding to "Cell to Image" action on context-menu
            Try to load images from url or local paths in the text of the selected cells.
        """

        # set up and run thread to load images from selected cells
        loader = ImageLoader(self)
        loader.run()

    def row_resized(self, index: int, old_size: int, new_size: int):
        """ Slot for responding to vertical header resize.
            Rescale all images in resized row.
        """
        self.rescale_images(TableDimension.ROW, index)

    def column_resized(self, index: int, old_size: int, new_size: int):
        """ Slot for responding to horizontal header resize.
            Rescale all images in resized column.
        """
        self.rescale_images(TableDimension.COLUMN, index)

    def rescale_images(self, dimension: TableDimension, index: int):
        """ Rescale all images in a column or row according to the cell sizes

        @param dimension: column or row
        @param index: row/column index
        """

        # run through all cells in column or row
        if dimension == TableDimension.ROW:
            for i in range(self.columnCount()):
                self.rescale_image(index, i)
        elif dimension == TableDimension.COLUMN:
            for i in range(self.rowCount()):
                self.rescale_image(i, index)

    def rescale_image(self, row: int, column: int):
        """ Rescale cell image.

        @param row: row index
        @param column: column index
        """

        # cell item
        item = self.item(row, column)
        if item is not None:
            # cell image
            cell_data = item.data(Qt.DecorationRole)
            if cell_data is not None and isinstance(cell_data, QImage):
                # reset image pixel ratio
                self.set_image_pixel_ratio(cell_data, self.horizontalHeader().sectionSize(column),
                                           self.verticalHeader().sectionSize(row))
                # reset item to newly scaled image
                # cannot seem to do this with a cell update or repaint - have to setItem() again
                new_item = QTableWidgetItem(item.type())
                new_item.setData(Qt.DecorationRole, cell_data)
                self.setItem(row, column, new_item)

    def set_image_pixel_ratio(self, image: QImage, target_width: int, target_height: int):
        """ Set the pixel ratio of an image so that it has a display size of [target_width, target_height]

        @param image: image to be scaled
        @param target_width: target display width
        @param target_height: target display height
        """
        # pixel ratios
        ratio_width = image.width() / target_width
        ratio_height = image.height() / target_height
        ratio_factor = ratio_width if ratio_width > ratio_height else ratio_height

        # reset cell pixel ratio (scaling of image)
        image.setDevicePixelRatio(ratio_factor)


class ImageLoader(QThread):
    """ Thread for loading images from url and local paths in selected cells.
    """

    def __init__(self, table: SheetView):
        """ Constructor.

        @param table: The table.
        """
        super().__init__(table)
        self.table = table

    def run(self):
        """ Overrides QThread::run().
            Load images from url and local paths in selected cells of the table.
        """

        # selected indexes
        selected_indexes = self.table.selectedIndexes()
        if not selected_indexes:
            return False

        for index in selected_indexes:
            # selected item
            item = self.table.item(index.row(), index.column())
            if not item:
                continue
            # item url or path
            path = item.text()
            if not path or len(path) < 1:
                continue
            # image
            image = QImage()
            # try as a local path
            if os.path.exists(path):
                image.load(path)
            # try as a url
            else:
                path_parsed = parse.urlparse(path)
                if not all([path_parsed.scheme, path_parsed.netloc, path_parsed.path]):
                    continue
                try:
                    url_stream = request.urlopen(path)
                    url_data = url_stream.read()
                    image.loadFromData(url_data)
                except (error.URLError, client.InvalidURL):
                    continue
            # set image scale
            self.table.set_image_pixel_ratio(image, self.table.horizontalHeader().sectionSize(index.column()),
                                            self.table.verticalHeader().sectionSize(index.row()))
            # set item data to image
            item.setData(Qt.DecorationRole, image)
            item.setText('')


# main program
if __name__ == '__main__':
    app = QApplication([])

    #mydata = pd.DataFrame(data={'name':['George', 'Sarah', 'Khalid', 'Bob', 'Xavier', 'Alice', 'Phil'], 'age':[56, 5, 8, 22, 34, 67, 98]})

    mydata = "A table of names and ages.\nname\tage\nGeorge\t56\nF:\\maxtor_backup\\data\\hrv\\reports\\170301_jan\\puri1_baseline.jpg\t5\nKhalid\t32\nBob\t67\nXavier\t14\nAlice\t30"

    mytable = DatumViewer(mydata)
    mytable.show()

    app.exec_()
