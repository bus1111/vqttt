# vqttt - GUI MQTT клиент
## Функционал
* Поиск и фильтрация в сообщениях (F3 или Ctrl+F)
* Вкладки (Ctrl+T)
* Двойной клик на топик чтобы отписаться

## Установка
### Пересобрать ресурсы
```
python setup.py build
```

### Через pip (запуск командой `vqttt`)
```
pip install git+https://github.com/bus1111/vqttt.git
```

### .exe для Windows (нужно добавить исключение в Windows Defender)
```
pyinstaller --icon=vqttt\resources\vqttt_icon.ico -n vqttt -F --noconsole .\vqttt\__main__.py
```
