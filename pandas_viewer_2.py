from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *

import pandas as pd
import numpy as np

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

        # header
        self.head_view = TableView(self, pd.DataFrame(data=[dataframe.columns, dataframe.dtypes], index=['name', 'type']))

        # data
        self.data_view = TableView(self, dataframe)
        self.data_view.horizontalHeader().hide()
        self.data_view.set_index_resizable(False)

        # connect data and header
        # ...header adjustment
        self.head_view.horizontalHeader().sectionResized.connect(self.align_data_columns)
        self.head_view.verticalHeader().geometriesChanged.connect(self.align_data_columns)
        # ...scroll
        self.data_view.horizontalScrollBar().valueChanged.connect(self.head_view.horizontalScrollBar().setValue)
        self.head_view.horizontalScrollBar().valueChanged.connect(self.data_view.horizontalScrollBar().setValue)

        # transfer context menu
        self.transfer_menu = TransferRowMenu(self)
        self.transfer_menu.to_data.triggered.connect(self.transfer_to_data)
        self.transfer_menu.to_header.triggered.connect(self.transfer_to_header)

        # splitter
        splitter = QSplitter(Qt.Vertical)
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
    # Transfer context menu
    # ------------------------------------------------

    def contextMenuEvent(self, event: QContextMenuEvent):
        self.transfer_menu.last_position = event.globalPos()   # this needs to come before executing the menu !!!!
        self.transfer_menu.exec(event.globalPos())

    def transfer_to_data(self):
        pos = self.transfer_menu.last_position
        if self.head_view.rect().contains(self.head_view.mapFromGlobal(pos)):
            indexes = self.head_view.selectedIndexes()
            for i in indexes:
                print('row = ', i.row())

    def transfer_to_header(self):
        pos = self.transfer_menu.last_position
        if self.data_view.rect().contains(self.data_view.mapFromGlobal(pos)):
            indexes = self.data_view.selectedIndexes()
            for i in indexes:
                print('row = ', i.row())


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

class TableView(QTableWidget):

    def __init__(self, parent: QWidget, dataframe: pd.DataFrame):
        # QTableWidget constructor
        super().__init__(dataframe.shape[0], dataframe.shape[1], parent)

        # data
        for j in range(dataframe.shape[1]):
            self.setVerticalHeaderItem(j, QTableWidgetItem(str(dataframe.index.values[j])))
            for i in range(dataframe.shape[0]):
                self.setItem(i, j, QTableWidgetItem(str(dataframe.iloc[i, j])))

        # vertical header
        self.set_index_resizable(True)


    # ------------------------------------------------
    # Indexes (a.k.a. vertical header)
    # ------------------------------------------------

    def set_index_resizable(self, doset: bool):
        if doset:
            self.verticalHeader().sectionDoubleClicked.connect(self.set_index)
        else:
            self.verticalHeader().sectionDoubleClicked.disconnect(self.set_index)

    def set_index(self, logicalIndex: int):
        mystr, ok = QInputDialog.getText(self, 'Header', 'The header type:', text=self.verticalHeaderItem(logicalIndex).text())
        if ok:
            self.setVerticalHeaderItem(logicalIndex, QTableWidgetItem(mystr))
            self.verticalHeader().geometriesChanged.emit()


# main program
if __name__ == '__main__':
    app = QApplication([])

    mydata = pd.DataFrame(data={'name':['George', 'Sarah', 'Khalid', 'Bob', 'Xavier', 'Alice', 'Phil'],
                                'age':[56, 5, 8, 22, 34, 67, 98]})

    mytable = DatumViewer(mydata)
    mytable.show()

    app.exec_()
