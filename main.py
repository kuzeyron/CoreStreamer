from io import BytesIO
from socket import AF_INET, IPPROTO_TCP, SOCK_STREAM, TCP_NODELAY, socket
from struct import calcsize, unpack
from threading import Thread

from kivy.app import App
from kivy.clock import Clock
from kivy.core.image import Image as CoreImage
from kivy.properties import (BooleanProperty, ListProperty, NumericProperty,
                             ObjectProperty, StringProperty)
from kivy.uix.image import Image


class Stream(Image):
    fit_mode = StringProperty('contain')
    fps = NumericProperty(60)
    host = ListProperty()
    nocache = BooleanProperty(True)
    payload_size = NumericProperty()
    server = ObjectProperty(None, allownone=True)

    def on_kv_post(self, *largs):
        self.server = socket(AF_INET, SOCK_STREAM)
        self.server.setsockopt(IPPROTO_TCP, TCP_NODELAY, 1)
        self.payload_size = calcsize("i")
        self.data = b''
        self._bytesio = BytesIO()

    def on_server(self, *largs):
        try:
            self.server.connect(tuple(x for x in self.host))
        except Exception:
            Clock.schedule_once(self.on_server, 1)
        finally:
            Thread(target=self.update, daemon=True).start()

    def update(self, dt=None):
        try:
            payload_size = self.payload_size
            data = self.data

            while len(data) < payload_size:
                data += self.server.recv(256**2)

            packed_msg_size = data[:payload_size]
            data = data[payload_size:]
            msg_size = unpack("i", packed_msg_size)[0]

            while len(data) < msg_size:
                data += self.server.recv(256**2)

            start = data.find(b'\xff\xd8')
            end = data.find(b'\xff\xd9')

            if start != -1 and end != -1:
                self._bytesio.write(data[:msg_size])
                self._bytesio.seek(0)
                self.texture = CoreImage(self._bytesio,
                                         ext='jpeg').texture
                self._bytesio.seek(0)

            self.data = data[msg_size:]

        except Exception:
            pass

        Clock.schedule_once(self.update, 1. / self.fps)


class CamApp(App):
    def build(self):
        return Stream(host=('192.168.0.2', 6666), fps=60)


if __name__ == "__main__":
    CamApp().run()
