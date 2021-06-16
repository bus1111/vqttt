from qtpy.QtCore import Qt
from qtpy.QtWidgets import (QInputDialog, QMainWindow, QMenuBar,
                            QStatusBar, QTabWidget)

from .connection_tab import ConnectionTab
from .utils import center_widget_on_screen


class MainWindow(QMainWindow):

    def __init__(self, log, app):
        self.log = log
        self.app = app
        super().__init__()

        self.server_running = False
        self.shutting_down = False
        self.conns_by_name = {}

        self.setupUi()
        self.create_conn_tab()

    def setupUi(self):
        self.resize(1000, 600)
        self.setWindowTitle('vqttt')

        self.connTabWidget = QTabWidget(self)
        self.connTabWidget.setTabsClosable(True)
        self.connTabWidget.setMovable(True)
        self.connTabWidget.setTabBarAutoHide(True)
        self.connTabWidget.tabCloseRequested.connect(self.close_tab)
        self.setCentralWidget(self.connTabWidget)

        self.statusbar = QStatusBar(self)
        self.setStatusBar(self.statusbar)

        self.setup_menubar()
        self.setup_action_triggers()
        self.show()

    def setup_menubar(self):
        self.menubar = QMenuBar(self)
        self.setMenuBar(self.menubar)

        self.menuFile = self.menubar.addMenu("Меню")
        self.actionQuit = self.menuFile.addAction('Выйти')

        self.menuTab = self.menubar.addMenu("Вкладка")
        self.actionOpenTab = self.menuTab.addAction('Создать')
        self.actionCloseTab = self.menuTab.addAction('Закрыть')
        self.menuTab.addSeparator()
        self.actionPopOut = self.menuTab.addAction('Открепить')
        self.actionRenameTab = self.menuTab.addAction('Переименовать')
        self.actionSetMaxCapacity = self.menuTab.addAction('Лимит сообщений')

    def setup_action_triggers(self):
        self.actionOpenTab.triggered.connect(self.create_conn_tab)
        self.actionOpenTab.setShortcut('Ctrl+T')
        self.actionCloseTab.triggered.connect(self.close_current_tab)
        self.actionCloseTab.setShortcut('Ctrl+W')
        self.actionPopOut.triggered.connect(self.pop_out_tab)
        self.actionRenameTab.triggered.connect(self.rename_tab_dialog)
        self.actionSetMaxCapacity.triggered.connect(self.max_capacity_dialog)
        self.actionQuit.triggered.connect(self.shutdown)
        self.actionQuit.setShortcut('Ctrl+Q')

    def create_conn_tab(self):
        name = self.make_conn_name_unique("Соединение")
        new_conn_tab = ConnectionTab(self.connTabWidget, self.log, name, self)
        self.conns_by_name[name] = new_conn_tab
        index = self.connTabWidget.addTab(new_conn_tab, name)
        self.connTabWidget.setCurrentIndex(index)
        return new_conn_tab, index

    def make_conn_name_unique(self, name):
        name_f = "{} {{}}".format(name)
        c = 1
        while name in self.conns_by_name:
            name = name_f.format(c)
            c += 1
        return name

    def pop_out_tab(self):
        index, tab = self.get_current_conn_tab()
        self.log.debug("Tab pop out requested: {}".format(int(index)))

        tab.destroyed.connect(tab.closeEvent)
        tab.setAttribute(Qt.WA_DeleteOnClose, True)
        tab.setWindowFlags(Qt.Window)
        tab.setWindowTitle('vqttt: "{}"'.format(self.connTabWidget.tabText(index)))
        tab.popped_out = True
        self.connTabWidget.removeTab(index)
        tab.show()
        center_widget_on_screen(tab)

    def rename_tab_dialog(self):
        index, tab = self.get_current_conn_tab()
        d = QInputDialog(self)
        d.setLabelText('Введите новое имя для вкладки "{}":'.format(tab.name))
        d.setWindowTitle('Переименовать вкладку "{}"'.format(tab.name))
        d.textValueSelected.connect(self.rename_current_tab)
        d.open()

    def rename_current_tab(self, new_name):
        index, tab = self.get_current_conn_tab()
        if new_name in self.conns_by_name and new_name != tab.name:
            new_name = self.make_conn_name_unique(new_name)
        self.log.debug('Renaming tab "{}" to "{}"'.format(tab.name, new_name))
        del self.conns_by_name[tab.name]
        tab.name = new_name
        self.conns_by_name[new_name] = tab
        tab.log.name = '.'.join(tab.log.name.split('.')[:-1]) + '.{}'.format(new_name)
        self.connTabWidget.setTabText(index, new_name)

    def max_capacity_dialog(self):
        index, tab = self.get_current_conn_tab()
        d = QInputDialog(self)
        d.setInputMode(QInputDialog.IntInput)
        d.setIntRange(0, 100000000)
        max_now = tab.message_model.max_capacity
        max_now = "0" if max_now is None else max_now
        label_str = 'Установить лимит сообщений для "{}".\nСейчас {}. Убрать лимит — 0:'
        d.setLabelText(label_str.format(tab.name, max_now))
        d.setWindowTitle('Установить лимит сообщений')
        d.intValueSelected.connect(self.set_max_capacity)
        d.open()

    def set_max_capacity(self, n):
        index = self.connTabWidget.currentIndex()
        tab = self.connTabWidget.widget(index)
        tab.set_max_capacity(n)

    def close_current_tab(self):
        index = self.connTabWidget.currentIndex()
        if index == -1:
            return
        self.close_tab(index)

    def close_tab(self, index):
        self.log.debug("Tab close requested: {}".format(index))
        if self.connTabWidget.count() <= 1:
            return
        conn = self.connTabWidget.widget(index)
        self.connTabWidget.removeTab(index)
        self.destroy_conn(conn)

    def get_current_conn_tab(self):
        index = self.connTabWidget.currentIndex()
        if index == -1:
            return None, None
        tab = self.connTabWidget.widget(index)
        return index, tab

    def destroy_conn(self, conn):
        del self.conns_by_name[conn.name]
        conn.setParent(None)
        conn.destroy()
        del conn

    def closeEvent(self, event):
        self.log.info('Close event on main window')
        self.shutdown()
        event.ignore()  # prevents errors due to closing the program before server has stopped

    def close_popped_out_conn(self, conn):
        del self.conns_by_name[conn.name]
        del conn

    def shutdown(self):
        self.log.info('Shutting down')
        if self.shutting_down:
            self.log.error('Exiting forcefully')
            raise SystemExit
        for conn in self.conns_by_name.values():
            conn.destroy()
        self.shutting_down = True
        self.app.quit()

    def signal_handler(self, *args):
        self.shutdown()
