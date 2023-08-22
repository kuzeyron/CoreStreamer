import logging
from datetime import datetime
from os.path import abspath, dirname, join
from socket import AF_INET, SO_REUSEADDR, SOCK_STREAM, SOL_SOCKET, socket
from struct import pack
from threading import Thread
from time import perf_counter, sleep

from cv2 import (CAP_PROP_POS_FRAMES, IMWRITE_JPEG_QUALITY, INTER_AREA,
                 VideoCapture, imencode, resize)


def log(text=None, prompt_user=None, has_arg=None, *largs):
    time = datetime.now().strftime("%d.%m.%Y %H:%M:%S")
    has_arg = f': {has_arg}' if has_arg else ''
    logging.info(f"[ {prompt_user} ][ {time} ] {text}{has_arg}.")


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
                self.sent_arguments += f'{key}={value}, '

        self.isrunning = True
        target = getattr(self, self.device_type, None)

        if callable(target):
            Thread(target=target, daemon=True).start()

    def video(self, *largs):
        " Video is a dummy stream that plays a video instead of camera "
        cap = VideoCapture(self.source)
        self._fps = cap.get(CAP_PROP_POS_FRAMES) or (1. / self.fps)
        quality = [int(IMWRITE_JPEG_QUALITY), self.quality]
        log('Is now running with arguments', self.device_type.upper(),
            f'"{self.sent_arguments[:-2]}"')

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
    ipv4_allowed: tuple = ('192.168.0.', )
    quality: int = 100
    prompt_user: str = 'SERVER'
    source: str = 'test.mp4'

    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            if getattr(self, key, None):
                setattr(self, key, value)

        self.device = Device()
        self.server = socket(AF_INET, SOCK_STREAM)
        self.server.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)
        self.server.bind(self.host)
        self.server.listen(10)
        log('Initialized the socket protocol', self.prompt_user)
        self.first_listener = True
        self.listen()

    @property
    def active_sessions(self):
        return self._active_sessions

    @active_sessions.setter
    def active_sessions(self, value):
        self._active_sessions = max(0, value)
        self.device.listeners = self._active_sessions

        if self._active_sessions == 1 and self.first_listener:
            self.device.run(fps=self.fps, quality=self.quality,
                            device_type=self.device_type,
                            source=self.source)
            self.first_listener = False

        if self._active_sessions == 0:
            self.device.isrunning = False
            self.first_listener = True
            sleep(.1)
            self.device.frame_buffer = b''

        log('List of active users', self.prompt_user,
            f"({', '.join(self.active_addresses) or 'None'})")

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
        log('Is now connected and ready to stream',
            self.prompt_user, f'"{user}"')

        while self.active_sessions > 0:
            try:
                t1 = perf_counter()

                if self.device.frame:
                    data = self.device.frame
                    message_size = pack("Q", len(data))
                    client.sendall(message_size + data)

                sleep(max(self.device._fps - (t1 - perf_counter()), 0))

            except Exception:
                break

        if user in self.active_addresses:
            self.active_addresses.pop(self.active_addresses.index(user))

        log('Disconnecting user', self.prompt_user, f'"{user}"')
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
