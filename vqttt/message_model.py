from collections import deque
from paho.mqtt.client import topic_matches_sub
from qtpy.QtCore import Qt, QSortFilterProxyModel, QAbstractTableModel, QModelIndex

from .utils import get_random_color

INVALID_INDEX = QModelIndex()
SearchRole = 256


class MessageModel(QAbstractTableModel):

    def __init__(self, parent, max_capacity=10000):
        super().__init__(parent)
        self.parent_widget = parent
        self.max_capacity = max_capacity
        self.messages = deque()
        self.topic_colors = {}
        self.table_header = [('color', ''), ('time', 'Время'),
                             ('topic', 'Топик'), ('msg', 'Сообщение')]

    def columnCount(self, index):
        return len(self.table_header)

    def rowCount(self, index=INVALID_INDEX):
        return len(self.messages)

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None

        result = None
        msg = self.messages[index.row()]
        column = self.table_header[index.column()]

        if role == Qt.DisplayRole:
            # print(index.row())
            column = column[0]
            if column == 'time':
                result = msg.time
            elif column == 'topic':
                result = msg.topic
            elif column == 'msg':
                result = msg.payload
        elif role == Qt.BackgroundRole:
            if column[0] != 'color':
                return None
            if msg.topic in self.topic_colors:
                return self.topic_colors[msg.topic]
            else:
                color = get_random_color(len(self.topic_colors))
                self.topic_colors[msg.topic] = color
                return color
        elif role == SearchRole:
            result = msg.payload
        return result

    def headerData(self, section, orientation=Qt.Horizontal, role=Qt.DisplayRole):
        result = None
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            result = self.table_header[section][1]
        return result

    def add_message(self, msg, internal=False):
        if not internal:
            self.trim_if_needed()
        row = len(self.messages)

        self.beginInsertRows(INVALID_INDEX, row, row)
        self.messages.append(msg)
        self.endInsertRows()

    # @TODO: It deletes one more row than needed because it expects an insertion next
    def trim_if_needed(self):
        if self.max_capacity == 0 or len(self.messages) == 0:
            return
        diff = len(self.messages) - self.max_capacity
        if len(self.messages) >= self.max_capacity:
            self.beginRemoveRows(INVALID_INDEX, 0, diff)
            while len(self.messages) >= self.max_capacity:
                self.messages.popleft()
            self.endRemoveRows()

    def clear(self):
        self.messages.clear()

    def get_message(self, pos):
        if type(pos) is QModelIndex:
            pos = pos.row()
        return self.messages[pos]


class MessageFilter(QSortFilterProxyModel):
    def __init__(self, parent, topics):
        super().__init__(parent)
        self.topics = topics
        self.clear_filter()

    def filterAcceptsRow(self, sourceRow, sourceParent):
        msg = self.sourceModel().get_message(sourceRow)
        result = True
        subs = list(filter(lambda sub: topic_matches_sub(sub, msg.topic), self.topics))
        if not subs:
            return True
        elif all(map(lambda s: not self.topics[s]['show'], subs)):
            return False
        if self.search_filter:
            msg = msg.payload
            if msg is None:
                return False
            regexp = self.filterRegExp()
            if not regexp.isEmpty():
                return regexp.exactMatch(msg)
            else:
                if self.filterCaseSensitivity() == Qt.CaseInsensitive:
                    msg = msg.lower()
                return self.filter_string in msg
        else:
            return result
        return False

    def set_filter(self, string, regexp, casesensitive):
        if regexp:
            self.setFilterRegExp(string)
        else:
            if not casesensitive:
                string = string.lower()
            self.filter_string = string
            self.setFilterRegExp("")

        self.search_filter = True
        self.setFilterCaseSensitivity(casesensitive)
        self.invalidateFilter()

    def clear_filter(self):
        self.search_filter = False
        self.filter_string = ""
        self.setFilterRegExp("")
        self.invalidateFilter()
