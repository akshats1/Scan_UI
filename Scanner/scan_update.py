import logging
import threading
import time
import typing
import pathlib
import serial
import cv2
import numpy as np
from PIL import Image
from datetime import datetime
from time import sleep
import subprocess

log_filename="/home/pi/Autoscope_Scan/logs/scan.log"
logging.basicConfig(
level=logging.INFO,
format='%(asctime)s %(levelname)s:%(message)s',
handlers=[logging.FileHandler(log_filename),
          logging.StreamHandler()
          ]
          )


board = serial.Serial('/dev/ttyUSB0', 9600)

global x, y, z, scan_count
x = 0
y = 0
z = 0
scan_count = 0

def movexclock(distance):
    global x
    _ = board.write("xclk,{}".format(distance).encode())
    while True:
        data = board.readline()
        if data == b'Done\r\n':
            break   
    x += distance

def movexanticlock(distance):
    global x
    _ = board.write("xcclk,{}".format(distance).encode())
    while True:
        data = board.readline()
        if data == b'Done\r\n':
            break
    x -= distance

def movey(steps):
    global y
    _ = board.write("ycclk,{}".format(steps).encode())
    while True:
        data = board.readline()
        if data == b'Done\r\n':
            break
    y += steps
    sleep(1)

def movezclock(distance):
    global z
    _ = board.write("zclk,{}".format(distance).encode())
    while True:
        data = board.readline()
        if data == b'Done\r\n':
            break
    z -= distance

def movezanticlock(distance):
    global z
    _ = board.write("zcclk,{}".format(distance).encode())
    while True:
        data = board.readline()
        if data == b'Done\r\n':
            break
    z += distance

def variance(image):
    bg = cv2.GaussianBlur(image, (11, 11), 0)
    v = cv2.Laplacian(bg, cv2.CV_64F).var()
    return v

def auto():
    global z
    var = []
    #_ = board.write("init".encode())
    z = 0
    while True:
        data = board.readline()
        if data == b'Done\r\n':
            break
    _ = board.write("zcclk,{}".format(14500).encode())
    z += 14500
    while True:
        data = board.readline()
        if data == b'Done\r\n':
            break
    for i in range(25):
        image = main.cam.capture('image')
        with open("/home/pi/scan/image.jpg", 'rb') as file:
            image = file.read()
        image = io.BytesIO(image)
        image = Image.open(image)
        image = np.array(image)
        image = image.reshape((240, 320, 3))
        var.append(variance(image))
        _ = board.write("zcclk,{}".format(50).encode())
        z += 50
        while True:
            data = board.readline()
            if data == b'Done\r\n':
                break
    var = np.array(var)
    l = np.argmax(var)
    sleep(.5)
    _ = board.write("zclk,{}".format(1290 - l * 50).encode())
    z -= 1290 - l * 50
   

def scan():
    global scan_count 
    cur_time = datetime.now()
    dir_path = "/home/pi/scan/gallery_data/scan_{}/".format(cur_time.strftime("%Y%m%d_%H%M"))
    subprocess.run(["mkdir", dir_path])
    auto()
    for i in range(10):
        for j in range(15):
            if j == 7:
                auto()
            if i % 2 == 0:
                main.cam.scan_capture(dir_path + "imagerow{0},{1}.jpg".format(i, j))
                scan_count += 1
                movexclock(15)
            else:
                main.cam.scan_capture(dir_path + "imagerow{0},{1}.jpg".format(i, 14 - j))
                scan_count += 1
                movexanticlock(15)
        movey(12)
        while True:
            data = board.readline()
            if data == b'Done\r\n':
                break
    #_ = board.write("init".encode())
    while True:
        data = board.readline()
        if data == b'Done\r\n':
            break
    stitch_images(dir_path, dir_path + 'complete_slide.jpg', 10, 15)

def stitch_images(image_paths, output_path, rows, cols):
    images = []
    max_width = 0
    max_height = 0
    for i in range(rows):
        for j in range(cols):
            image = Image.open(image_paths + "imagerow{},{}.jpg".format(i, j))
            images.append(image)
            max_width = max(max_width, image.width)
            max_height = max(max_height, image.height)
    stitched_width = max_width * cols
    stitched_height = max_height * rows
    stitched_image = Image.new('RGB', (stitched_width, stitched_height), (255, 255, 255))
    for i, image in enumerate(images):
        row = i // cols
        col = i % cols
        x = col * max_width
        y = row * max_height
        stitched_image.paste(image, (x, y))
    stitched_image.save(output_path)

class Scanner:
    _instance = None

    def __init__(self):
        if Scanner._instance:
            logging.error("[Scanner] Multiple instances requested")
            raise RuntimeError("Another instance of scanner interface already exists")
        logging.info("[Scanner] Creating new instance")
        self.is_scanning = False
        self.scan_perc = 0
        self._thread = None
        Scanner._instance = self

    def bring_to(self, axis, point):
        logging.info("[Scanner] Bringing platform to %s position in %s axis", point, axis)
        mover = {'x': movexclock, 'y': movey}[axis]
        mover(point)

    def _scan(self):
        self.is_scanning = True
        logging.info("[Scanner] Initializing slide-scan")
        scan()
        self.is_scanning = False

    def start_scan(self, top, left, right, bottom, target_dir):
        def func():
            for i in range(11):
                if self.is_scanning:
                    time.sleep(1)
                    self.scan_perc = i / 10
            self.is_scanning = False
            self.scan_perc = 0

        logging.info("[Scanner] Initializing scanning")
        if self._thread and not self._thread.is_alive():
            self._thread = None
        self.is_scanning = True
        self._thread = threading.Thread(target=self._scan)
        self._thread.start()

    def stop_scan(self):
        logging.info("[Scanner] Stopping ongoing slide scan")
        if not self._thread:
            return
        self.is_scanning = False
        if self._thread.is_alive():
            self._thread.join()
        self.scan_perc = 0

    def close(self, _vars_file=".internal_vars"):
        logging.info("[Scanner] Saving internal variables")
        if self.is_scanning:
            self.stop_scan()
        Scanner._instance = None

# Example usage:
scanner = Scanner()
top = 0.0
left = 0.0
right = 1.0
bottom = 1.0
target_dir = "/home/pi/Autoscope_Scan/scan_images"
scanner.start_scan(top, left, right, bottom, target_dir)
scanner.close()

