from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *

import pandas as pd
import numpy as np



# Table Viewer
class DatumViewer(QWidget):

    def __init__(self, dataframe : pd.DataFrame):

        # QWidget constructor
        super().__init__()

        # data frame
        self.xydataframe = dataframe

        # header
        self.head_model = PandasModel(pd.DataFrame(data=[self.xydataframe.columns, self.xydataframe.dtypes], index=['name', 'type']))
        self.head_view = QTableView()
        self.head_view.setModel(self.head_model)

        # data
        self.data_model = PandasModel(self.xydataframe)
        self.data_view = QTableView()
        self.data_view.setModel(self.data_model)
        self.data_view.horizontalHeader().hide()

        # transfer context menu
        self.transfer_menu = TransferRowMenu(self)
        self.transfer_menu.to_data.triggered.connect(self.transfer_to_data)
        self.transfer_menu.to_header.triggered.connect(self.transfer_to_header)

        # connect data and header
        # ...header adjustment
        self.head_view.horizontalHeader().sectionResized.connect(self.adjust_data_column)
        self.data_view.verticalHeader().setMinimumWidth(self.head_view.verticalHeader().width())
        self.head_view.verticalHeader().sectionDoubleClicked.connect(self.change_header_name)
        # ...scroll
        self.data_view.horizontalScrollBar().valueChanged.connect(self.head_view.horizontalScrollBar().setValue)
        self.head_view.horizontalScrollBar().valueChanged.connect(self.data_view.horizontalScrollBar().setValue)

        # splitter
        splitter = QSplitter(Qt.Vertical)
        splitter.addWidget(self.head_view)
        splitter.addWidget(self.data_view)

        # layout
        layout = QVBoxLayout()
        layout.addWidget(splitter)
        self.setLayout(layout)

    # ------------------------------------------------
    # TableView event slots
    # ------------------------------------------------

    # adjust data view column width when header view is adjusted
    def adjust_data_column(self, logicalIndex: int, oldSize: int, newSize: int):
        self.data_view.setColumnWidth(logicalIndex, newSize)

    # change header name with double click
    def change_header_name(self, logicalIndex):
        # get string from dialog
        mystr, ok = QInputDialog.getText(self, 'Enter a value', 'Enter a value')
        #  change name
        self.head_model.setHeaderData(logicalIndex, Qt.Vertical, mystr)
        # reset widths
        wid = self.head_view.verticalHeader().fontMetrics().width(mystr)
        self.head_view.verticalHeader().setMinimumWidth(wid)
        self.data_view.verticalHeader().setMinimumWidth(wid)

    # ------------------------------------------------
    # Transfer context menu
    # ------------------------------------------------

    def contextMenuEvent(self, event: QContextMenuEvent):
        self.transfer_menu.last_position = event.globalPos()   # this needs to come before executing the menu !!!!
        self.transfer_menu.exec(event.globalPos())

    def transfer_to_data(self):

        #if self.data_view.rect().contains(self.data_view.mapFromGlobal(self.transfer_menu.last_position)):


        # cursor position
        pos = self.data_view.mapFromGlobal(self.transfer_menu.last_position)
        if self.data_view.rect().contains(pos):
            print('in data!')
        print('to data', pos.x(), pos.y())

    def transfer_to_header(self):
        print('to header')

# ------------------------------------------------
# ------------------------------------------------

# transfer row context menu
class TransferRowMenu(QMenu):

    def __init__(self, parent: QWidget):

        super().__init__('Transfer to:', parent)

        # menu actions
        self.to_description = QAction('Description', parent)
        self.addAction(self.to_description)
        self.to_header = QAction('Header', parent)
        self.addAction(self.to_header)
        self.to_data = QAction('Data', parent)
        self.addAction(self.to_data)

        # position of cursor when menu was executed
        self.last_position = QPoint(0, 0)

# ------------------------------------------------
# ------------------------------------------------

# Pandas Data-frame model
class PandasModel(QAbstractTableModel):

    def __init__(self, dataframe: pd.DataFrame):
        super().__init__()

        # data
        self.xydataframe = dataframe

    # ------------------------------------------------
    # Qt overrides
    # ------------------------------------------------

    def rowCount(self, parent=None, *args, **kwargs):
        return self.xydataframe.shape[0]

    def columnCount(self, parent=None, *args, **kwargs):
        return self.xydataframe.shape[1]

    def data(self, index: QModelIndex, role=None):
        if role != Qt.DisplayRole:
            return QVariant()
        return str(self.xydataframe.iloc[index.row(), index.column()])

    def setData(self, index, value: str, role=None):
        if role != Qt.EditRole:
            return False
        typ = self.xydataframe.dtypes[index.column()]
        if typ == np.object:
            self.xydataframe.iloc[index.row(), index.column()] = str(value)
            return True
        elif typ == np.int64:
            try:
                self.xydataframe.iloc[index.row(), index.column()] = int(value)
                return True
            except ValueError:
                return False
        elif typ == np.float64:
            try:
                self.xydataframe.iloc[index.row(), index.column()] = float(value)
                return True
            except ValueError:
                return False

        return False

    def flags(self, index):
        return Qt.ItemIsSelectable | Qt.ItemIsEditable | Qt.ItemIsEnabled

    def headerData(self, index, orientation, role=None):
        if role != Qt.DisplayRole:
            return QVariant()
        if orientation == Qt.Vertical:
            return str(self.xydataframe.index[index])
        if orientation == Qt.Horizontal:
            return str(self.xydataframe.columns[index])

    def setHeaderData(self, index, orientation, value, role=None):
        if orientation == Qt.Vertical:
            ivals = self.xydataframe.index.values
            ivals[index] = value
            return True
        return False



# main program
if __name__ == '__main__':
    app = QApplication([])

    mydata = pd.DataFrame(data={'name':['George', 'Sarah', 'Khalid', 'Bob', 'Xavier', 'Alice', 'Phil'],
                                'age':[56, 5, 8, 22, 34, 67, 98]})

    mytable = DatumViewer(mydata)
    mytable.show()

    app.exec_()
