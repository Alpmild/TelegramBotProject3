from sys import argv, exit
from PyQt5.QtWidgets import QApplication

from data.AdminWindow import AdminWindow


if __name__ == '__main__':
    App = QApplication(argv)
    App.setStyle('Fusion')
    StWin = AdminWindow()
    StWin.show()
    exit(App.exec_())
