from functools import partial
from qtpy.QtCore import Qt, QFile
from qtpy.QtWidgets import QWidget, QShortcut, QMenu, QHeaderView, QCheckBox, \
                           QHBoxLayout, QTableWidgetItem, QLineEdit
from qtpy.QtGui import QIntValidator

from .utils import loadUi
from .client import MqttClient
from .message_model import MessageModel, MessageFilter, INVALID_INDEX, SearchRole


class ConnectionTab(QWidget):
    def __init__(self, parent, log, name, main_window):
        super().__init__(parent)
        self.client = None
        self.name = name
        self.main_window = main_window
        self.log = log.getChild('Tab')
        self.message_model = MessageModel(self)
        self.topics = {}

        self.autoscroll = True
        self.scroll_max = 0
        self.search_bar_visible = False
        self.search_regex = False
        self.search_casesensitive = False
        self.search_start = 0  # для search_down
        self.popped_out = False
        self.setupUi()

    def setupUi(self):
        file = QFile(':/ui/connection')
        file.open(QFile.ReadOnly)
        self.ui = loadUi(file, baseinstance=self)
        self.disable_when_no_conn = [self.publishButton, self.subscribeButton, self.retainCheckbox,
                                     self.subTopicLine, self.subQosSelector, self.pubTopicLine,
                                     self.payloadLine]
        self.connectButton.clicked.connect(self.connect_toggle)
        self.subscribeButton.clicked.connect(self.subscribe)
        self.subTopicLine.returnPressed.connect(self.subscribe)
        self.publishButton.clicked.connect(self.publish)
        self.portValidatior = QIntValidator(1, 65535, self)
        self.hostPortLine.setValidator(self.portValidatior)

        for widget in self.connInfoWrapper.children():
            if type(widget) == QLineEdit:
                widget.returnPressed.connect(self.connect_toggle)

        self.filter_model = MessageFilter(self, self.topics)
        self.filter_model.setSourceModel(self.message_model)
        self.messageTable.setModel(self.filter_model)

        self.messageTable.verticalScrollBar().rangeChanged.connect(self.on_range_changed)
        self.messageTable.verticalScrollBar().valueChanged.connect(self.on_scroll)
        self.messageTable.setContextMenuPolicy(Qt.CustomContextMenu)
        self.messageTable.setStyleSheet("QTableView { border: 0px;}")
        self.messageTable.selectionModel().selectionChanged.connect(self.update_detail)
        self.messageTable.horizontalHeader().setMinimumSectionSize(7)
        self.messageDetailText.setText("")

        self.topicsTable.doubleClicked.connect(self.topic_double_clicked)
        self.topicsTable.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)

        self.searchWidget.setHidden(True)
        self.searchSC = QShortcut('Ctrl+F', self)
        self.searchSC.activated.connect(self.toggle_search)
        self.searchSC.setAutoRepeat(False)

        self.searchSC_F3 = QShortcut('F3', self)
        self.searchSC_F3.activated.connect(self.search_down_or_close)
        self.searchSC_F3.setAutoRepeat(True)

        self.searchSC_Home = QShortcut('Home', self)
        self.searchSC_Home.activated.connect(partial(self.messageTable.selectRow, 0))
        self.searchSC_Home.setAutoRepeat(False)

        self.searchSC_End = QShortcut('End', self)
        self.searchSC_End.activated.connect(self.select_last_row)
        self.searchSC_End.setAutoRepeat(False)

        self.setup_search_button_menu()

        self.searchLine.returnPressed.connect(self.search_down)
        self.searchDownButton.clicked.connect(self.search_down)
        self.searchDownButton.setMenu(self.setup_search_button_menu())

        self.searchWidget.setVisible(self.search_bar_visible)
        self.filterButton.clicked.connect(self.filter_or_clear)

        for widget in self.disable_when_no_conn:
            widget.setEnabled(False)

    def setup_search_button_menu(self):
        smenu = QMenu(self.searchDownButton)
        action_regex = smenu.addAction('Регулярные выражения')
        action_regex.setCheckable(True)
        action_regex.setChecked(self.search_regex)
        action_regex.triggered.connect(self.set_search_regex)
        action_case = smenu.addAction('Учитывать регистр')
        action_case.setCheckable(True)
        action_case.setChecked(self.search_casesensitive)
        action_case.triggered.connect(self.set_search_casesensitive)
        return smenu

    def set_search_regex(self, enabled):
        self.search_regex = enabled

    def set_search_casesensitive(self, enabled):
        self.search_casesensitive = enabled

    def on_scroll(self, pos):
        if pos < self.scroll_max:
            self.autoscroll = False
        else:
            self.autoscroll = True

    def on_range_changed(self, min, max):
        self.scroll_max = max

    def connect_toggle(self):
        if self.client and self.client.state == MqttClient.Connecting:
            return
        if self.client and self.client.state == MqttClient.Connected:
            self.client.disconnect()
            return
        ip = self.hostIpLine.text()
        if self.portValidatior.validate(self.hostPortLine.text(), 0)[0] == QIntValidator.Acceptable:
            port = int(self.hostPortLine.text())
        else:
            self.log.warn('Invalid port')
            return
        username = self.usernameLine.text()
        password = self.passwordLine.text()
        client_id = self.clientIdLine.text()
        self.client = MqttClient(ip, port, username, password, client_id, self)
        self.client.new_message.connect(self.on_message)
        self.client.connected.connect(self.connected)
        self.client.disconnected.connect(self.disconnected)
        self.connectButton.setText("Подключение...")
        self.connectButton.setEnabled(False)
        self.client.connect()

    def publish(self):
        if self.client is None:
            return
        qos = int(self.pubQosSelector.currentText().replace('QoS', ''))
        retain = self.retainCheckbox.isChecked()
        topic = self.pubTopicLine.text()
        payload = self.payloadLine.toPlainText()
        self.client.publish(topic, payload, qos, retain)

    def subscribe(self, topic=None):
        if type(topic) is not str:
            topic = self.subTopicLine.text()
        if len(topic) == 0 or topic in self.topics or self.client is None:
            return
        qos = int(self.subQosSelector.currentText().replace('QoS', ''))
        try:
            self.client.subscribe(topic, qos)
        except Exception as e:
            self.log.error("Ошибка при подписке", e, exc_info=True)
            return
        self.topics[topic] = {'show': True, 'qos': qos}
        self.add_topic_to_table(topic)

    def add_topic_to_table(self, topic):
        row_count = self.topicsTable.rowCount()
        self.topicsTable.setRowCount(row_count + 1)

        checkbox_widget = QWidget(self.topicsTable)
        checkbox_widget.setStyleSheet("QWidget { background-color:none;}")

        checkbox = QCheckBox()
        checkbox.setStyleSheet("QCheckBox::indicator { width: 15px; height: 15px;}")
        checkbox.setChecked(True)
        checkbox.clicked.connect(partial(self.topic_show_changed, topic))

        checkbox_layout = QHBoxLayout()
        checkbox_layout.setAlignment(Qt.AlignCenter)
        checkbox_layout.setContentsMargins(0, 0, 0, 0)
        checkbox_layout.addWidget(checkbox)
        checkbox_widget.setLayout(checkbox_layout)

        self.topicsTable.setCellWidget(row_count, 0, checkbox_widget)
        item = QTableWidgetItem(topic)
        self.topicsTable.setItem(row_count, 1, item)
        self.topicsTable.resizeColumnToContents(1)

    def unsubscribe(self, topic):
        if topic not in self.topics:
            return
        if self.client is not None:
            try:
                self.client.unsubscribe(topic)
            except Exception as e:
                self.log.error("Ошибка при отписке", e, exc_info=True)
        del self.topics[topic]
        self.remove_topic_from_table(topic)

    def remove_topic_from_table(self, topic):
        for row in range(self.topicsTable.rowCount()):
            name = self.topicsTable.item(row, 1).text()
            if name == topic:
                self.topicsTable.removeRow(row)
                break
        else:
            self.log.warn('Row not found')

    def update_detail(self, sel, desel):
        indexes = sel.indexes()
        if len(indexes) <= 0:
            self.messageDetailText.setText("")
            return
        index = indexes[0]
        source_index = self.filter_model.mapToSource(index)
        message = self.message_model.get_message(source_index)
        self.messageDetailText.setText(message.payload)

    def topic_double_clicked(self, index):
        row, column = index.row(), index.column()
        if column == 0:
            checkbox = self.topicsTable.cellWidget(row, column).children()[1]
            checkbox.toggle()
        else:
            topic = self.topicsTable.item(row, column).text()
            self.unsubscribe(topic)

    def on_message(self, msg):
        self.message_model.add_message(msg)
        if self.autoscroll:
            self.messageTable.scrollToBottom()

        # Установить автоматическую ширину для некоторых столбцов после первого сообщения
        if self.message_model.rowCount() == 1:
            header = self.message_model.table_header
            resize_columns = [i for i, v in enumerate(header) if v[0] in ['color', 'time']]
            for col in resize_columns:
                self.messageTable.resizeColumnToContents(col)

    def search_down(self):
        start = self.filter_model.index(self.search_start, 0, INVALID_INDEX)
        s = self.searchLine.text()

        if not self.search_regex:
            search_flags = Qt.MatchContains
        else:
            search_flags = Qt.MatchRegExp
        if self.search_casesensitive:
            search_flags = search_flags | Qt.MatchCaseSensitive

        hits = self.filter_model.match(start, SearchRole, s, 1, Qt.MatchWrap | search_flags)
        print(hits)
        if not hits:
            self.main_window.statusbar.showMessage('Поиск дошел до конца', 4000)
            self.search_start = 0
        else:
            result = hits[0]
            self.search_start = result.row() + 1
            self.messageTable.scrollTo(result)
            self.messageTable.setCurrentIndex(result)

    def search_down_or_close(self):
        if self.search_bar_visible is False:
            self.set_search_visible(True)
        elif self.searchLine.text() == "":
            self.set_search_visible(False)
        else:
            self.search_down()

    def set_search_visible(self, visible):
        if not self.search_bar_visible and not visible:
            self.messageTable.clearSelection()

        self.search_bar_visible = visible
        self.searchWidget.setVisible(self.search_bar_visible)
        if self.search_bar_visible:
            self.searchLine.setFocus()
        else:
            self.searchLine.clear()

    def toggle_search(self):
        self.set_search_visible(not self.search_bar_visible)

    def filter_or_clear(self):
        if not self.filter_model.search_filter:
            self.filterButton.setText('Сбросить')
            self.filter_model.set_filter(self.searchLine.text(), self.search_regex,
                                         self.search_casesensitive)
        else:
            self.filterButton.setText('Фильтр')
            self.filter_model.clear_filter()
            self.invalidate_filter()

    def topic_show_changed(self, topic, value):
        self.topics[topic]['show'] = value
        self.invalidate_filter()

    def set_max_capacity(self, max_capacity):
        self.message_model.max_capacity = max_capacity
        self.message_model.trim_if_needed()

    def select_last_row(self):
        self.messageTable.selectRow(self.filter_model.rowCount() - 1)

    def invalidate_filter(self):
        self.filter_model.invalidateFilter()
        if self.autoscroll:
            self.messageTable.scrollToBottom()

    def connected(self):
        self.log.info('Connected')
        self.connInfoWrapper.setHidden(True)
        status = "Подключено к: {}:{}".format(self.client.host_ip, self.client.host_port)
        if self.client.username:
            status += ', username={}'.format(self.client.username)
        if self.client.client_id:
            status += ', id={}'.format(self.client.client_id)
        self.connInfoLabel.setText(status)
        self.connectButton.setText("Отключиться")
        self.connectButton.setEnabled(True)
        # self.main_window.statusbar.clearMessage()
        for widget in self.disable_when_no_conn:
            widget.setEnabled(True)
        if len(self.topics) > 0:
            self.client.subscribe([(t, v['qos']) for t, v in self.topics.items()])

    def disconnected(self, reason=None):
        self.log.info('Disconnected')
        self.connInfoLabel.setText("")
        self.connInfoWrapper.setHidden(False)
        for widget in self.disable_when_no_conn:
            widget.setEnabled(False)
        self.connectButton.setText("Подключиться")
        self.connectButton.setEnabled(True)
        if reason:
            self.main_window.statusbar.showMessage(reason, 5000)
            self.connInfoLabel.setText(reason)
        self.client = None

    def closeEvent(self, event=None):
        self.destroy()
        if self.popped_out:
            self.main_window.close_popped_out_conn(self)

    def destroy(self):
        try:
            if self.client:
                self.client.disconnect()
                self.client = None
            self.message_model.clear()
        except Exception:
            pass
