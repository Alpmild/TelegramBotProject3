from datetime import date, time

from PyQt5.QtWidgets import QDialog
from PyQt5.QtCore import QTime
from PyQt5 import uic

from data.Consts import SSD_INTERFACE


class SessionSetupDialog(QDialog):
    """
    Окно настройки сеанса.
    """

    def __init__(self, parent, tab: int, date_: date, time_=time(8, 0, 0), hall=1, index=-1, session_id=-1):
        super(SessionSetupDialog, self).__init__(parent)
        self.parent, self.tab = parent, tab
        self.date_ = date_
        self.hall, self.time_ = hall, time_
        self.index, self.session_id = index, session_id

        uic.loadUi(SSD_INTERFACE, self)
        self.init_ui()

    def init_ui(self):
        self.setFixedSize(self.size())
        self.setModal(True)

        self.TimeEdit.setTime(QTime(self.time_.hour, self.time_.minute))
        self.TimeEdit.timeChanged.connect(self.set_time)

        self.SpinBox.setValue(self.hall)
        self.SpinBox.valueChanged.connect(self.set_hall)

        self.ConfirmSessionBtn.clicked.connect(self.set_session)

    def set_hall(self, hall):
        """Изменение номера зала"""
        self.hall = hall

    def set_time(self, time_):
        """Изменение времени сеанса"""
        self.time_ = time(time_.hour(), time_.minute())

    def set_session(self):
        """Запись сеанса"""
        self.parent.set_session(self.tab, self.date_, self.time_, self.hall, self.index, self.session_id)
        self.close()
