from PyQt5.QtWidgets import QDialog
from PyQt5 import uic

from data.Consts import ERROR_COLOR, DSD_INTERFACE, NORMAL_LINE_COLOR, NORMAL_WINDOW_COLOR


class DirectorSetupDialog(QDialog):
    """
    Окно для добавления режиссёра
    """

    def __init__(self, parent, tab: int, index=-1, name='', surname=''):
        super().__init__()
        print([index, name, surname])

        self.parent = parent
        self.tab = tab
        self.index = index
        self.director_info = (name, surname)

        self.error_messages = ['В имени должны быть только буквы',
                               'В фамилии должны быть только буквы',
                               'Корректно заполните данные']

        uic.loadUi(DSD_INTERFACE, self)
        self.lines = (self.NameLine, self.SurnameLine)

        self.init_ui()

    def init_ui(self):
        self.setFixedSize(self.size())
        self.setModal(True)

        if self.index != -1:
            self.setWindowTitle('Изменение режиссера')

        for i, line in enumerate(self.lines):
            line.setText(self.director_info[i])
            line.textChanged.connect(self.set_normal_status)

        self.NameLine.textChanged.connect(self.set_btn_status)
        self.SurnameLine.textChanged.connect(self.set_btn_status)

        self.set_btn_status()
        self.ConfirmDirectorBtn.clicked.connect(self.set_director)

    def set_btn_status(self):
        """Установка статуса кнопки: если заролнены оба поля, то кнопку возможно нажать, иначе - нет"""
        self.ConfirmDirectorBtn.setEnabled(all(line.text().strip() for line in self.lines))

    def set_normal_status(self):
        """Изменение цвета поля прия изменении текста в нем"""

        self.sender().setStyleSheet(f'background-color: {NORMAL_LINE_COLOR}')
        self.StatusBar.setStyleSheet(f'background-color: {NORMAL_WINDOW_COLOR}')
        self.StatusBar.setText('')

    def set_director(self):
        """
        При нажатии на кнопку происходит проверка введенных данных.
        Если не заполнены некоторые поля, то они подсвечиваются.
        Таже ситуация с неправильно заполненными полями.
        Если все "ок", то вызывается сигнал, чтоб передать данные в родительское окно.
        """
        mistakes = self.check_mistakes()
        if mistakes:
            self.set_incorrectly_lines(mistakes)
            self.StatusBar.setStyleSheet(f'background-color: {ERROR_COLOR}')

            if len(mistakes) == 2:
                self.StatusBar.setText(self.error_messages[2])
            else:
                self.StatusBar.setText(self.error_messages[mistakes[0]])
            return

        self.parent.set_director(self.tab, self.index, self.get_director())
        self.close()

    def check_mistakes(self) -> list:
        """Проверка праильности написания имени и фамилии"""

        mistakes = []
        for ind, line in enumerate(self.lines):
            text = line.text().strip()
            if not text:
                mistakes.append(ind)
            else:
                text = text.split()
                for i in text:
                    if not i.isalpha():
                        mistakes.append(ind)
                        break
        return mistakes

    def get_director(self):
        return tuple(map(lambda l: ' '.join(map(lambda t: t.capitalize(), l.text().strip().split())), self.lines))

    def set_incorrectly_lines(self, indexes: list):
        for i in indexes:
            self.lines[i].setStyleSheet(f'background-color: {ERROR_COLOR}')

    def clear(self):
        """
        Очистка всех полей и сообщениый при закрытии окна
        """
        pass
