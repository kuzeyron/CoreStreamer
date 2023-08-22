from io import BytesIO
from socket import AF_INET, SOCK_STREAM, socket
from socket import timeout as TimeoutException
from struct import calcsize, unpack
from threading import Thread
from time import sleep

from kivy.app import App
from kivy.clock import Clock, mainthread
from kivy.core.image import Image as CoreImage
from kivy.properties import (BooleanProperty, ListProperty, NumericProperty,
                             ObjectProperty)
from kivy.uix.image import Image


class Stream(Image):
    allow_stretch = BooleanProperty(True)
    nocache = BooleanProperty(True)
    fps = NumericProperty(60)
    host = ListProperty()
    payload_size = NumericProperty()
    server = ObjectProperty(None, allownone=True)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.server = socket(AF_INET, SOCK_STREAM)
        self.payload_size = calcsize("Q")
        self.data = b''
        self._bytesio = BytesIO()

    def on_server(self, *largs):
        try:
            self.server.connect(tuple(x for x in self.host))
        except Exception:
            sleep(1)
            Clock.schedule_once(self.on_server, 1)
        finally:
            Thread(target=self.update, daemon=True).start()

    @mainthread
    def update(self, dt=None):
        try:
            payload_size = self.payload_size
            data = self.data

            while len(data) < payload_size:
                data += self.server.recv(1024)

            packed_msg_size = data[:payload_size]
            data = data[payload_size:]
            msg_size = unpack("Q", packed_msg_size)[0]

            while len(data) < msg_size:
                data += self.server.recv(1024)

            self._bytesio.write(data[:msg_size])
            self.data = data[msg_size:]

            self._bytesio.seek(0)
            self.texture = CoreImage(self._bytesio,
                                     ext='jpeg').texture
            self._bytesio.seek(0)

        except TimeoutException:
            pass

        except Exception:
            pass

        finally:
            Clock.schedule_once(self.update, 1. / self.fps)


class CamApp(App):
    def build(self):
        return Stream(host=('192.168.0.2', 6666), fps=60)


if __name__ == "__main__":
    CamApp().run()
