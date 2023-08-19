from io import BytesIO
from socket import AF_INET, SOCK_STREAM, socket
from socket import timeout as TimeoutException
from struct import calcsize, unpack
from threading import Thread

from kivy.app import App
from kivy.clock import Clock, mainthread
from kivy.core.image import Image as CoreImage
from kivy.properties import BooleanProperty, ListProperty, NumericProperty
from kivy.uix.image import Image


class Stream(Image):
    allow_stretch = BooleanProperty(True)
    nocache = BooleanProperty(True)
    fps = NumericProperty(60)
    host = ListProperty()
    payload_size = NumericProperty()

    def on_kv_post(self, *largs):
        self.payload_size = calcsize("i")
        self.data = b''
        self._bytesio = BytesIO()
        self.server = socket(AF_INET, SOCK_STREAM)
        self.server.connect(tuple(x for x in self.host))
        Thread(target=self.update, daemon=True).start()

    @mainthread
    def update(self, dt=None):
        try:
            payload_size = self.payload_size
            data = self.data

            while len(data) < payload_size:
                data += self.server.recv(128)

            packed_msg_size = data[:payload_size]
            data = data[payload_size:]
            msg_size = unpack("i", packed_msg_size)[0]

            while len(data) < msg_size:
                data += self.server.recv(128)

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
