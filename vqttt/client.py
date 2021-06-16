import binascii
import paho.mqtt.client as mqtt
from datetime import datetime
from qtpy.QtCore import Signal, QThread, QTimer, QDeadlineTimer


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

    def __init__(self, ip, log, port=1883, username=None, password=None, client_id=None, parent=None):
        super().__init__(parent)
        self.host_ip, self.host_port = ip, port
        self.username, self.password = username, password
        self.client_id = client_id
        self.state = MqttClient.Disconnected
        self.log = log.getChild('Mqtt')

        self.client = mqtt.Client(client_id)
        self.client.on_message = self.on_message
        self.client.on_disconnect = self.on_disconnect
        self.client.on_connect = self.on_connect
        self.client.username_pw_set(username, password)
        self.conn_timer = None

    # Название `connect` создаёт проблемы с QObject.connect в PySide2
    def connect_to_broker(self):
        if self.state != MqttClient.Disconnected:
            self.log.warn("Already connected")
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
    # connect_async+loop_start не помогут так как loop_stop может зависнуть.
    # Но self.terminate тоже может зависнуть??? Ад.
    def run(self):
        self.log.debug("Starting client thread")
        rc = 0
        try:
            self.client.connect(self.host_ip, self.host_port)
            self.client.loop_start()
            self.log.debug("Client loop started, thread finished")
        except Exception as e:
            self.log.error("Excepting during connection: {}".format(e), exc_info=True)
            self.disconnected.emit("Ошибка подключения (код {}): {}".format(rc, e))
            self.state = MqttClient.Disconnected

    def publish(self, topic, payload, qos=0, retain=False):
        self.client.publish(topic, payload, qos, retain)

    def on_message(self, client, userdata, msg):
        try:
            msg = Message(msg)
        except Exception as e:
            print('Ошибка обработки сообщения:', e)
        self.new_message.emit(msg)

    def subscribe(self, topic, qos=0):
        self.client.subscribe(topic, qos)

    def unsubscribe(self, topic):
        self.client.unsubscribe(topic)

    def on_connect(self, client, userdata, flags, rc):
        self.state = MqttClient.Connected
        if rc == 0:
            self.connected.emit()
        else:
            self.log.warn("Connection with non-zero rc: {}".format(rc))

    def on_disconnect(self, client, userdata, rc):
        self.state = MqttClient.Disconnected
        if rc != 0:
            self.stop_connection()
        if rc == 1:
            self.disconnected.emit('Соединение закрыто')
        elif rc == 5:
            self.disconnected.emit('Ошибка авторизации')
        else:
            self.disconnected.emit('')

    # Возвращает True если было что остановить
    def stop_connection(self):
        self.log.debug("Stopping the connection")
        self.client.loop_stop()
        if self.isRunning():
            self.log.debug("Asking thread to quit")
            self.quit()
            t = QDeadlineTimer()
            t.setRemainingTime(1000)
            if not self.wait(t):
                self.log.warn("Thread didn't stop, terminating")
                self.terminate()
                self.log.debug("Thread terminated")
            return True
        return False

    def conn_success_check(self):
        self.log.debug("Checking connection success")
        self.conn_timer = None
        if self.state != self.Connected:
            self.log.debug("Connection didn't succeed, stopping")
            if self.stop_connection():
                self.disconnected.emit("Вышло время попытки подключения")
