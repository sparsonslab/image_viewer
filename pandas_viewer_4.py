from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *

from enum import Enum
import pandas as pd
import numpy as np

# Table Viewer
class DatumViewer(QWidget):

    def __init__(self, text: str):

        # QWidget constructor
        super().__init__()

        # text
        self.text_view = TableTextView(self, text)

        # header
        self.head_view = TableView(self, 5, 1)

        # data
        self.data_view = TableView(self, 5, 1)
        self.data_view.horizontalHeader().hide()
        self.data_view.set_index_resizable(False)

        # connect data and header
        # ...header adjustment
        self.head_view.horizontalHeader().sectionResized.connect(self.align_data_columns)
        self.head_view.verticalHeader().geometriesChanged.connect(self.align_data_columns)
        # ...scroll
        self.data_view.horizontalScrollBar().valueChanged.connect(self.head_view.horizontalScrollBar().setValue)
        self.head_view.horizontalScrollBar().valueChanged.connect(self.data_view.horizontalScrollBar().setValue)

        # splitter
        splitter = QSplitter(Qt.Vertical)
        splitter.addWidget(self.text_view)
        splitter.addWidget(self.head_view)
        splitter.addWidget(self.data_view)

        # layout
        layout = QVBoxLayout()
        layout.addWidget(splitter)
        self.setLayout(layout)

    # ------------------------------------------------
    # Alignment of data and header
    # ------------------------------------------------

    def align_data_columns(self):
        self.data_view.verticalHeader().setMinimumWidth(self.head_view.verticalHeader().width())
        for i in range(self.head_view.colorCount()):
            self.data_view.setColumnWidth(i, self.head_view.columnWidth(i))
        self.data_view.updateGeometries()

    # ------------------------------------------------
    # Set data/header
    # ------------------------------------------------

    def set_views(self, head_text: list, data_text: list):
        n_data_col = self.data_view.set_items(data_text, -1)
        n_head_col = self.head_view.set_items(head_text, n_data_col)


class RowType(Enum):
    DATA = Qt.lightGray
    HEADER = Qt.red
    OTHER = Qt.black


class RowMenu(QMenu):

    def __init__(self, parent: QWidget):
        super().__init__('Transfer to:', parent)
        # menu actions
        self.to_header = QAction('Header', parent)
        self.addAction(self.to_header)
        self.to_data = QAction('Data', parent)
        self.addAction(self.to_data)
        self.to_other = QAction('Other', parent)
        self.addAction(self.to_other)
        self.addSeparator()
        self.set_view = QAction('Set Views', parent)
        self.addAction(self.set_view)


class TableTextView(QPlainTextEdit):

    def __init__(self, parent: DatumViewer, text: str):

        super().__init__(text, parent)

        # parent viewer
        self.parent_widget = parent

        # head row indexes and first data row
        self.head_rows = []
        self.first_data_row = -1

        # row transfer context menu
        self.row_menu = RowMenu(self)
        self.row_menu.to_data.triggered.connect(self.row_to_data)
        self.row_menu.to_header.triggered.connect(self.row_to_header)
        self.row_menu.to_other.triggered.connect(self.row_to_other)
        self.row_menu.set_view.triggered.connect(self.set_views)

    # ------------------------------------------------
    # Drag-and-drop text file
    # ------------------------------------------------
    def dropEvent(self, event: QDropEvent):
        mime = event.mimeData()
        if mime.hasText():
            file_path = mime.text()
            if file_path.endswith('.txt'):
                file_path = file_path.replace('file:///', '')
                with open(file_path) as reader:
                    rows = reader.readlines()
                    if rows:
                        file_text = ''.join(rows)
                        self.setPlainText(file_text)

    # required so that cursor returns unfrozen after drag-and-drop
    def dragMoveEvent(self, event: QDragMoveEvent):
        event.acceptProposedAction()

    # ------------------------------------------------
    # Row setting
    # ------------------------------------------------

    def contextMenuEvent(self, event: QContextMenuEvent):
        self.row_menu.exec(event.globalPos())

    def row_to_data(self):
        self.set_row(RowType.DATA)

    def row_to_header(self):
        self.set_row(RowType.HEADER)

    def row_to_other(self):
        self.set_row(RowType.OTHER)

    def set_views(self):
        [head_text, data_text] = self.get_block_text()
        self.parent_widget.set_views(head_text, data_text)

    def get_block_designations(self):
        # cursor
        curs = self.textCursor()
        # total number of blocks/rows
        curs.movePosition(QTextCursor.End, QTextCursor.MoveAnchor)
        n_blocks = curs.blockNumber()
        # current designations of blocks (a.k.a. rows)
        head_blocks = []                # list of header block indices
        data_block_start = -1           # first data block index
        curs.movePosition(QTextCursor.Start, QTextCursor.MoveAnchor)
        for i in range(n_blocks + 1):
            curs.movePosition(QTextCursor.EndOfBlock, QTextCursor.KeepAnchor)
            if curs.charFormat().foreground().color() == RowType.HEADER.value:
                head_blocks.append(curs.blockNumber())
            elif curs.charFormat().foreground().color() == RowType.DATA.value:
                data_block_start = curs.blockNumber()
                break
            elif i == n_blocks:
                break
            curs.movePosition(QTextCursor.NextBlock, QTextCursor.MoveAnchor)
        # return
        return n_blocks, head_blocks, data_block_start

    def get_selected_blocks(self):
        # cursor
        curs = self.textCursor()
        # selection
        selection_position_start = curs.anchor()
        selection_position_end = curs.position()
        curs.setPosition(selection_position_start, QTextCursor.MoveAnchor)
        curs.movePosition(QTextCursor.StartOfBlock, QTextCursor.MoveAnchor)
        selection_block_start = curs.blockNumber()
        curs.setPosition(selection_position_end, QTextCursor.KeepAnchor)
        curs.movePosition(QTextCursor.EndOfBlock, QTextCursor.KeepAnchor)
        selection_block_end = curs.blockNumber()
        return selection_block_start, selection_block_end

    def set_row(self, rtype: RowType):

        # selected blocks/rows
        [selection_block_start, selection_block_end] = self.get_selected_blocks()

        # block/row designations
        [n_blocks, head_blocks, data_block_start] = self.get_block_designations()

        # modify designations
        if rtype == RowType.DATA:
            # set start of data
            data_block_start = selection_block_start
            # remove any overlapping headers
            head_blocks = [row for row in head_blocks if row < data_block_start]
        elif rtype == RowType.HEADER:
            # append header with selected rows before data
            for i in range(selection_block_start, selection_block_end + 1):
                if (data_block_start == -1) or (i < data_block_start):
                    head_blocks.append(i)
            # remove duplicates
            head_blocks = list(set(head_blocks))
        elif rtype == RowType.OTHER:
            # filter out headers
            head_blocks = [row for row in head_blocks if (row < selection_block_start) or (row > selection_block_end)]

        # update designations (i.e. actual block/row colors)
        curs = self.textCursor()
        form = curs.blockCharFormat()
        curs.movePosition(QTextCursor.Start, QTextCursor.MoveAnchor)
        for i in range(n_blocks):
            curs.movePosition(QTextCursor.EndOfBlock, QTextCursor.KeepAnchor)
            if i in head_blocks:
                form.setForeground(RowType.HEADER.value)
                curs.setCharFormat(form)
            elif i == data_block_start:
                curs.movePosition(QTextCursor.End, QTextCursor.KeepAnchor)
                form.setForeground(RowType.DATA.value)
                curs.setCharFormat(form)
                break
            else:
                form.setForeground(RowType.OTHER.value)
                curs.setCharFormat(form)
            curs.movePosition(QTextCursor.NextBlock, QTextCursor.MoveAnchor)

    def get_block_text(self):
        # block/row designations
        [n_blocks, head_blocks, data_block_start] = self.get_block_designations()
        # for headers and data, list of block/row text
        head_text = []
        data_text = []
        curs = self.textCursor()
        curs.movePosition(QTextCursor.Start, QTextCursor.MoveAnchor)
        for i in range(n_blocks):
            curs.movePosition(QTextCursor.EndOfBlock, QTextCursor.KeepAnchor)
            if i in head_blocks:
                head_text.append(curs.selectedText())
            elif i == data_block_start:
                curs.movePosition(QTextCursor.End, QTextCursor.KeepAnchor)
                # QString QTextCursor::selectedText() const
                # Note: If the selection obtained from an editor spans a line break, the text will contain a
                # Unicode U+2029 paragraph separator character instead of a newline \n character.
                data_text = curs.selectedText().split(u"\u2029")
                break
            curs.movePosition(QTextCursor.NextBlock, QTextCursor.MoveAnchor)
        # return lists
        return head_text, data_text

# ------------------------------------------------
# ------------------------------------------------

class TableView(QTableWidget):

    def __init__(self, parent: QWidget, ncol: int, nrow: int):
        super().__init__(nrow, ncol, parent)
        self.set_index_resizable(True)

    def set_items(self, rows: list, default_col: int):

        # empty list
        if not rows:
            self.setRowCount(1)
            self.setColumnCount(5)
            if default_col > 0:
                self.setColumnCount(default_col)
            return -1

        # delimiter (comma or tab)
        delimiter = '\t'
        n_tab = rows[0].count('\t')
        n_comma = rows[0].count(',')
        if n_comma > n_tab:
            delimiter = ','

        # number of columns
        n_col = len(rows[0].split(delimiter))
        if (default_col > 0) and (n_col < default_col):
            n_col = default_col

        # set items
        n_row = len(rows)
        self.setRowCount(n_row)
        self.setColumnCount(n_col)
        for i in range(n_row):
            cols = rows[i].split(delimiter)
            for j in range(n_col):
                if j < len(cols):
                    self.setItem(i, j, QTableWidgetItem(cols[j]))
                else:
                    self.setItem(i, j, QTableWidgetItem(""))

        return n_col

    # ------------------------------------------------
    # Indexes (a.k.a. vertical header)
    # ------------------------------------------------

    def set_index_resizable(self, doset: bool):
        if doset:
            self.verticalHeader().sectionDoubleClicked.connect(self.set_index)
        else:
            self.verticalHeader().sectionDoubleClicked.disconnect(self.set_index)

    def set_index(self, logicalIndex: int):

        instr = ''
        try:
            instr = self.verticalHeaderItem(logicalIndex).text()
        except:
            instr = ''

        mystr, ok = QInputDialog.getText(self, 'Header', 'The header type:', text=instr)
        if ok:
            self.setVerticalHeaderItem(logicalIndex, QTableWidgetItem(mystr))
            self.verticalHeader().geometriesChanged.emit()


# main program
if __name__ == '__main__':
    app = QApplication([])

    #mydata = pd.DataFrame(data={'name':['George', 'Sarah', 'Khalid', 'Bob', 'Xavier', 'Alice', 'Phil'], 'age':[56, 5, 8, 22, 34, 67, 98]})

    mydata = "A table of names and ages.\nname\tage\nGeorge\t56\nSarah\t5\nKhalid\t32\nBob\t67\nXavier\t14\nAlice\t30"

    mytable = DatumViewer(mydata)
    mytable.show()

    app.exec_()
