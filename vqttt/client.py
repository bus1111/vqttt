import binascii
import hashlib
import paho.mqtt.client as mqtt
from datetime import datetime
from qtpy.QtCore import Signal, QThread, QTimer


class Message:
    def __init__(self, msg):
        self.raw_msg = msg

        self.qos = msg.qos
        self.retain = msg.retain
        self.topic = msg.topic
        self.time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        try:
            self.payload = msg.payload.decode('utf-8', 'backslashreplace')
        except Exception:
            self.payload = binascii.hexlify(msg.payload, ' ', 2)

    def __repr__(self):
        return "{}(topic={}, payload={})".format(self.__class__.__name__, self.topic, self.payload)


class MqttClient(QThread):
    Disconnected = 1
    Connecting = 2
    Connected = 3

    new_message = Signal(Message)
    connected = Signal()
    disconnected = Signal(str)

    def __init__(self, ip, port=1883, username=None, password=None, client_id=None, parent=None):
        super().__init__(parent)
        self.host_ip, self.host_port = ip, port
        self.username, self.password = username, password
        self.client_id = client_id
        self.state = MqttClient.Disconnected

        self.client = mqtt.Client(client_id)
        self.client.on_message = self.on_message
        self.client.on_disconnect = self.on_disconnect
        self.client.on_connect = self.on_connect
        self.client.username_pw_set(username, password)
        self.conn_timer = None

    def connect(self):
        if self.state != MqttClient.Disconnected:
            return
        self.state = MqttClient.Connecting

        # Таймер для остановки зависшего client.connect
        self.conn_timer = QTimer(None)
        self.conn_timer.setSingleShot(True)
        self.conn_timer.setInterval(2000)
        self.conn_timer.timeout.connect(self.conn_success_check)
        self.conn_timer.start()
        self.start()

    def disconnect(self):
        if self.state == MqttClient.Disconnected:
            return
        self.client.disconnect()

    # Нужен запуск в своём треде чтобы .connect не остановил всю программу.
    # loop_forever нужен чтобы self.terminate останавливал переподключение
    # при неверном пароле или иной ошибке.
    # connect_async+loop_start не помогут так как loop_stop может зависнуть.
    # Но self.terminate тоже может зависнуть??? Ад.
    def run(self):
        rc = 0
        try:
            rc = self.client.connect(self.host_ip, self.host_port)
            self.client.loop_start()
        except Exception as e:
            print(e)
            self.disconnected.emit("Ошибки подключения {}: {}".format(rc, e))
            self.state = MqttClient.Disconnected

    def publish(self, topic, payload, qos=0, retain=False):
        self.client.publish(topic, payload, qos, retain)

    def on_message(self, client, userdata, msg):
        try:
            msg = Message(msg)
        except Exception as e:
            print('Ошибка обработки сообщения:', e)
        # print(msg)
        self.new_message.emit(msg)

    def subscribe(self, topic, qos=0):
        self.client.subscribe(topic, qos)

    def unsubscribe(self, topic):
        self.client.unsubscribe(topic)

    def on_connect(self, client, userdata, flags, rc):
        self.state = MqttClient.Connected
        if rc == 0:
            self.conn_timer = None
            self.connected.emit()

    def on_disconnect(self, client, userdata, rc):
        self.state = MqttClient.Disconnected
        if rc != 0:
            self.client.loop_stop()
            if self.isRunning():
                self.terminate()
        if rc == 1:
            self.disconnected.emit('Соединение закрыто')
        elif rc == 5:
            self.disconnected.emit('Ошибка авторизации')
        else:
            self.disconnected.emit('')

    def conn_success_check(self):
        if self.state != self.Connected:
            self.state = MqttClient.Disconnected
            self.client.loop_stop()
            if self.isRunning():
                self.disconnected.emit("Вышло время попытки подключения")
                self.terminate()
