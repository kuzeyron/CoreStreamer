import logging
from datetime import datetime
from os.path import abspath, dirname, join
from socket import AF_INET, SO_REUSEADDR, SOCK_STREAM, SOL_SOCKET, socket
from struct import pack
from threading import Thread
from time import perf_counter, sleep

from cv2 import (CAP_PROP_POS_FRAMES, IMWRITE_JPEG_QUALITY, INTER_AREA,
                 VideoCapture, imencode, resize)


def get_time():
    return datetime.now().strftime("%d.%m.%Y %H:%M:%S")


class Device:
    fps: int = 60
    _fps: float = 1. / fps
    device_type: str = 'video'
    frame = b''
    isrunning: bool = False
    listeners: int = 0
    quality: int = 100
    sent_arguments: str = ""
    source: str = 'test.mp4'
    videosize: tuple = (1280, 720)

    def run(self, **kwargs):
        " Starts the feed of chosen device (camera or video) "
        self.sent_arguments = ''

        for key, value in kwargs.items():
            if getattr(self, key, None):
                setattr(self, key, value)
                self.sent_arguments += f"{key}={value}, "

        self.isrunning = True
        target = getattr(self, self.device_type, None)

        if callable(target):
            Thread(target=target, daemon=True).start()

    def video(self, *largs):
        " Video is a dummy stream that plays a video instead of camera "
        cap = VideoCapture(self.source)
        self._fps = cap.get(CAP_PROP_POS_FRAMES) or (1. / self.fps)
        quality = [int(IMWRITE_JPEG_QUALITY), self.quality]
        logging.info('[ %s ][ %s ] is now running with arguments: "%s."',
                     self.device_type.upper(),
                     get_time(),
                     self.sent_arguments[:-2])

        while cap.isOpened() and self.isrunning:
            ret, image = cap.read()

            if ret:
                image = resize(image, self.videosize, interpolation=INTER_AREA)
                compressed_img = imencode('.jpg', image, quality)[1]
                self.frame = compressed_img.tobytes()
            else:
                cap.set(CAP_PROP_POS_FRAMES, 0)


class FeedStream:
    _active_sessions: int = 0
    active_addresses: list = []
    device_type = 'video'
    fps: int = 60
    host: tuple = ('0.0.0.0', 6666)
    ipv4_allowed: list = ['192.168.0.']
    quality: int = 100

    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            if getattr(self, key, None):
                setattr(self, key, value)

        self.device = Device()
        self.server = socket(AF_INET, SOCK_STREAM)
        self.server.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)
        self.server.bind(self.host)
        self.server.listen(10)
        logging.info("[ SERVER ][ %s ] Initialized the socket protocol.",
                     get_time())
        self.listen()

    @property
    def active_sessions(self):
        return self._active_sessions

    @active_sessions.setter
    def active_sessions(self, value):
        self._active_sessions = max(0, value)
        self.device.listeners = self._active_sessions

        if self._active_sessions == 1:
            self.device.run(fps=self.fps, quality=self.quality,
                            device_type=self.device_type)

        if self._active_sessions == 0:
            self.device.isrunning = False
            sleep(.1)
            self.device.frame_buffer = b''

        logging.info("[ SERVER ][ %s ] List of active users: (%s).",
                     get_time(), ', '.join(self.active_addresses) or 'None')

    @active_sessions.getter
    def active_sessions(self):
        return self._active_sessions

    def listen(self):
        " Waiting for new users to connect "
        while True:
            delivery, address = self.server.accept()
            delivery.settimeout(10)

            if address[0][:10] in self.ipv4_allowed:
                Thread(
                    target=self.transmit_data,
                    args=(delivery, f"{address[0]}:{address[1]}"),
                    daemon=True
                ).start()

    def transmit_data(self, client, user):
        " Streams the cached frames to chosen listener "
        self.active_addresses.append(user)
        self.active_sessions += 1
        data = b''
        logging.info(("[ SERVER ][ %s ] %s is now connected and "
                      "ready to stream."), get_time(), user)

        while self.active_sessions > 0:
            try:
                t1 = perf_counter()

                if self.device.frame:
                    data = self.device.frame
                    message_size = pack("i", len(data))
                    client.sendall(message_size + data)

                sleep(max(self.device._fps - (t1 - perf_counter()), .05))

            except Exception:
                break

        if user in self.active_addresses:
            self.active_addresses.pop(self.active_addresses.index(user))

        logging.info("[ SERVER ][ %s ] Disconnecting user: %s.",
                     get_time(), user)
        self.active_sessions -= 1


if __name__ == '__main__':
    logging.basicConfig(
        filename=join(dirname(abspath(__file__)), 'logs.txt'),
        filemode='a',
        format='%(asctime)s %(levelname)s %(message)s',
        datefmt='%H:%M:%S',
        level=logging.INFO
    )
    logging.getLogger().addHandler(logging.StreamHandler())
    FeedStream(quality=50, fps=30, device_type='video')
