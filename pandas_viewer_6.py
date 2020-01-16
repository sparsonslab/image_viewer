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
import numpy as np

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
    QImage,
    QColor,
    QPixmap
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

    def load_numpy_tensor(self, input_tensor: np.ndarray, input_sequence: str):
        self.spread_sheet.load_tensor(input_tensor, input_sequence)


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

        # row type list (see description below)
        self.row_type_list = [RowType.OTHER for i in range(n_row)]

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
        self.row_type_list = [RowType.OTHER for i in range(n_row)]
        self.set_row_colors()

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
            # insert row and set its items to empty strings
            self.insertRow(selection_row_start)
            for j in range(self.columnCount()):
                self.setItem(selection_row_start, j, QTableWidgetItem(""))
            # insert row type list with default type
            if selection_row_start <= len(self.row_type_list):
                self.row_type_list.insert(selection_row_start, RowType.OTHER)
            # set colors
            self.set_row_colors()
        else:
            # insert column and set its items to empty strings
            self.insertColumn(selection_col_start)
            for i in range(self.rowCount()):
                self.setItem(i, selection_col_start, QTableWidgetItem(""))
            # set colors
            self.set_row_colors()

    def delete_segment(self, dimension: TableDimension):
        """ Respond to selection of "Delete" item in row-menu
        """
        [selection_row_start, selection_row_end, selection_col_start, selection_col_end] = self.get_selected_range()
        if dimension == TableDimension.ROW:
            for i in range(1 + selection_row_end - selection_row_start):
                self.removeRow(selection_row_start)
                if selection_row_start < len(self.row_type_list):
                    self.row_type_list.pop(selection_row_start)
            self.set_row_colors()
        else:
            for i in range(1 + selection_col_end - selection_col_start):
                self.removeColumn(selection_col_start)

    # ------------------------------------------------
    # Row Types
    #
    # Each row has a type (DATA, HEADER or OTHER) and corresponding text/foreground color.
    # The DATA rows are a contiguous segment to the end of the table.
    # The types up to the last row before the DATA segment are held in the list row_type_list:
    # each element of the list corresponds to a row index.
    #
    # ------------------------------------------------

    def set_row_colors(self):
        """ Set the foreground color of each cell according to its row type.
        """
        for i in range(self.rowCount()):
            # color is DATA unless row index is less then length of row type list.
            color = RowType.DATA.value
            if i < len(self.row_type_list):
                color = self.row_type_list[i].value
            # set colors across row
            for j in range(self.columnCount()):
                if self.item(i, j) is not None:
                    self.item(i, j).setForeground(color)

    def set_selected_row_type(self, rtype: RowType) -> None:
        """ Set the row-type (HEADER | DATA | OTHER) of the selected rows.

        @param rtype: row type.
        """

        # selected rows
        [selection_row_start, selection_row_end, selection_col_start, selection_col_end] = self.get_selected_range()
        if (selection_row_start < 0) or (selection_row_end < 0):
            return None

        # modify types
        if rtype == RowType.DATA:
            if selection_row_start > len(self.row_type_list):
                # extend row type list with default
                for i in range(selection_row_start - len(self.row_type_list)):
                    self.row_type_list.append(RowType.OTHER)
            elif selection_row_start < len(self.row_type_list):
                # delete data elements from row type list
                self.row_type_list = self.row_type_list[:selection_row_start]
        else:
            # set to header or other
            for i in range(selection_row_start, selection_row_end + 1):
                if i < len(self.row_type_list):
                    self.row_type_list[i] = rtype

        # update colors
        self.set_row_colors()

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
    # Image scaling
    # ------------------------------------------------

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
                SheetView.set_image_pixel_ratio(cell_data, self.horizontalHeader().sectionSize(column),
                                           self.verticalHeader().sectionSize(row))
                # reset item to newly scaled image
                # cannot seem to do this with a cell update or repaint - have to setItem() again
                new_item = QTableWidgetItem(item.type())
                new_item.setData(Qt.DecorationRole, cell_data)
                new_item.setText(item.text())
                self.setItem(row, column, new_item)

    @staticmethod
    def set_image_pixel_ratio(image: QImage, target_width: int, target_height: int):
        """ Set the pixel ratio of an image so that it has a display size of [target_width, target_height]

        @param image: image to be scaled
        @param target_width: target display width
        @param target_height: target display height
        """

        dots_per_meter = 300.0 * 39.37

        # pixel ratios
        ratio_width = image.width() / target_width
        ratio_height = image.height() / target_height
        ratio_factor = ratio_width if ratio_width > ratio_height else ratio_height
        print(target_width, target_height, ratio_factor)
        if ratio_factor > 1.0:
            # reset cell pixel ratio (scaling of image)
            image.setDevicePixelRatio(ratio_factor)
            image.setDotsPerMeterX(dots_per_meter)
            image.setDotsPerMeterY(dots_per_meter)
        else:
            image.setDevicePixelRatio(1.0)
            image.setDotsPerMeterX(int(dots_per_meter * ratio_factor))
            image.setDotsPerMeterY(int(dots_per_meter * ratio_factor))

    # ------------------------------------------------
    # Numpy array displayed as images
    # ------------------------------------------------

    def load_tensor(self, input_tensor: np.ndarray, input_sequence: str):
        """ Load a tensor into the table as a sequence of images

        @param input_tensor: numpy array
        @param input_sequence: a string of characters describing the consecutive dimensions of the numpy array:
                R  = row, C = column W = width, H = height, D = depth (channel), otherwise = some 'other' dimension
                e.g. 'RxHDW' for rank-6 tensor
                If R/C/W/H/D are not in the sequence they are assumed to be an extra dimension of size of 1.
                For 'Other' dimensions the 0-index slice is extracted.
                See reform_tensor().
        @raise: ValueError if input sequence is bad or there is no QImage type appropriate for array.
        """

        # reform tensor
        try:
            # first two dimensions must be row and column (any order), then height:width:depth
            target_sequence = 'RCHWD'
            reformed_tensor = SheetView.reform_tensor(input_tensor, input_sequence, target_sequence)
        except ValueError as e:
            print(str(e))

        # image properties
        image_width = reformed_tensor.shape[target_sequence.find('W')]
        image_height = reformed_tensor.shape[target_sequence.find('H')]
        image_depth = reformed_tensor.shape[target_sequence.find('D')]
        bytes_per_depth = reformed_tensor.dtype.itemsize
        bytes_per_line = bytes_per_depth * image_depth * image_width
        try:
            image_format = SheetView.find_image_format(image_depth, bytes_per_depth)
        except ValueError as e:
            print(str(e))

        # set cell data
        self.setRowCount(reformed_tensor.shape[0])
        self.setColumnCount(reformed_tensor.shape[1])
        for i in range(self.rowCount()):
            for j in range(self.columnCount()):
                try:
                    # create image
                    image = QImage(reformed_tensor[i, j, ...].tobytes(),
                                   image_width, image_height, bytes_per_line, image_format)
                    # set scale
                    SheetView.set_image_pixel_ratio(image, self.horizontalHeader().sectionSize(j),
                                                     self.verticalHeader().sectionSize(i))
                    # set item data to image
                    self.setItem(i, j, QTableWidgetItem())
                    self.item(i, j).setData(Qt.DecorationRole, image)
                except Exception as e:
                    print('Error on image for cell ', i, ', ', j, ': ', str(e))

        # reset designations
        self.row_type_list = [RowType.OTHER for i in range(self.rowCount())]
        self.set_row_colors()

        # resize row heights
        self.resizeRowsToContents()

    @staticmethod
    def find_image_format(n_channels: int, bytes_per_channel: int) -> int:
        """ Return an appropriate QImage format given the number of channels and bytes per channel.
            The support for different formats depends on the PyQt version.

        @param n_channels: number of channels
        @param bytes_per_channel: bytes per channel
        @return: QImage format (enum QImage::Format)
        """

        image_format = None
        if n_channels == 1:
            if bytes_per_channel == 1:
                image_format = QImage.Format_Grayscale8  # "(added in Qt 5.5)"
            elif bytes_per_channel == 2:
                # image_format = QImage.Format_Grayscale16   # only in PyQt5.4 ???  "(added in Qt 5.13)"
                pass
            elif bytes_per_channel == 3:
                # ???? no 32-bit grayscale format
                pass
        elif n_channels == 3:
            # collapse width and depth?
            if bytes_per_channel == 1:
                image_format = QImage.Format_RGB888
        elif n_channels == 4:
            if bytes_per_channel == 1:
                image_format = QImage.Format_RGBA8888
            elif bytes_per_channel == 2:
                pass
        if image_format is None:
            raise ValueError('No valid QImage format.')

        return image_format

    @staticmethod
    def reform_tensor(input_tensor: np.ndarray, input_sequence: str, target_sequence: str) -> np.ndarray:
        """ Reform the input tensor (slice, transpose and insert) so that it matches
            the target dimension sequence.

        @param input_tensor: input tensor
        @param input_sequence: sequence of input tensor dimensions
        @param target_sequence: sequence of reformed tensor dimensions
        @return: reformed tensor
        @raise: ValueError
        """

        # target sequence has no duplicates
        for i in range(1, len(target_sequence)):
            if target_sequence[i] in target_sequence[:i]:
                raise ValueError('Duplicates in target sequence.')

        # input sequence has no duplicates of those elements in the target sequence
        for x in target_sequence:
            if input_sequence.count(x) > 1:
                raise ValueError('Duplicates of target sequence in input sequence.')

        # input sequence matches rank of input tensor
        if len(input_sequence) != len(input_tensor.shape):
            raise ValueError('Input sequence length does not match input tensor rank.')

        # sequences are matching
        if input_sequence == target_sequence:
            return input_tensor

        # slice tensor to get rid of dimensions other than those in the target sequence
        sliced_sequence = ''.join([x for x in input_sequence if x in target_sequence])
        slice_syntax = tuple([slice(None, None) if x in target_sequence else 0 for x in input_sequence])
        sliced_tensor = input_tensor[slice_syntax]
        if sliced_sequence == target_sequence:
            return sliced_tensor

        # transpose to target sequence ordering
        transposed_sequence = ''.join([x for x in target_sequence if x in sliced_sequence])
        transpose_syntax = tuple([sliced_sequence.find(x) for x in transposed_sequence])
        transposed_tensor = np.transpose(sliced_tensor, transpose_syntax)
        if transposed_sequence == target_sequence:
            return transposed_tensor

        # insert trailing dimensions (missing in input)
        trailing_syntax = tuple([slice(None, None) if x in transposed_sequence else None for x in target_sequence])
        trailed_tensor = transposed_tensor[trailing_syntax]
        return trailed_tensor

    # ------------------------------------------------
    # Image loading from cell path.
    # ------------------------------------------------

    def load_selected_images(self):
        """  Slot for responding to "Cell to Image" action on context-menu
            Try to load images from url or local paths in the text of the selected cells.
        """

        # set up and run thread to load images from selected cells
        loader = ImageLoader(self)
        loader.run()


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
            SheetView.set_image_pixel_ratio(image, self.table.horizontalHeader().sectionSize(index.column()),
                                            self.table.verticalHeader().sectionSize(index.row()))
            # set item data to image
            item.setData(Qt.DecorationRole, image)
            #item.setText('')


# main program
if __name__ == '__main__':
    app = QApplication([])

    #mydata = pd.DataFrame(data={'name':['George', 'Sarah', 'Khalid', 'Bob', 'Xavier', 'Alice', 'Phil'], 'age':[56, 5, 8, 22, 34, 67, 98]})

    mydata = "A table of names and ages.\nname\tage\nGeorge\t56\nF:\\maxtor_backup\\data\\hrv\\reports\\170301_jan\\puri1_baseline.jpg\t5\nKhalid\t32\nBob\t67\nXavier\t14\nAlice\t30"

    mytable = DatumViewer(mydata)
    mytable.show()

    tensor = np.random.randint(0, 255, size=(4, 3, 30, 50, 3), dtype=np.uint8)
    for i in range(tensor.shape[0]):
        for j in range(tensor.shape[1]):
            tensor[i, j, :, :, 0] = tensor[i, j, :, :, 0] / (0.5 * (j + 1))  # j = row: red should decrease
            tensor[i, j, :, :, 1] = tensor[i, j, :, :, 1] / (0.5 * (i + 1))  # i = column: green should decrease
    mytable.load_numpy_tensor(tensor, 'CRHWD')

    app.exec_()
