#!/usr/bin/env python

import RPi.GPIO as GPIO
import time
import threading
import queue
import math

from google.assistant.library.event import EventType

class HwComponent:
    def __init__(self, pin, input_mode, is_pwm=False):
        self.pin = pin
        self.state = None
        self.pwm = None
        self.dc = 0

        GPIO.setup(pin, input_mode)
        if is_pwm:
            self.pwm = GPIO.PWM(self.pin, 100);

class LedMgmtThread(threading.Thread):
    """
    This thread manage integrated LEDs
    it poll event from a event queue and trigger
    corresponding animations
    """
    def __init__(self, event_queue, shutdown_flag):
        super().__init__()
        self.event_queue = event_queue
        self.shutdown_flag = shutdown_flag
        self.breathing_speed = 0.0079  # speed of the breathing effect (12/min)
        self.listening = False
        self.dc = 0                    # PWM duty cycle
        self.ct = 0
        self.sampling_freq = 0.01  # sampling frequency for the breathing function

        GPIO.setwarnings(False)
        GPIO.setmode(GPIO.BCM)

        self.leds = {"red" : HwComponent(18, GPIO.OUT, is_pwm=True),
                     "green" : HwComponent(13, GPIO.OUT, is_pwm=True),
                     "blue" : HwComponent(12, GPIO.OUT, is_pwm=True)}

        for led in self.leds.values():
            led.pwm.start(led.dc)

    def run(self):
        while not self.shutdown_flag.is_set():
            try:
                event = self.event_queue.get_nowait()
            except queue.Empty:
                if not self.listening:
                    if (self.ct > (2*math.pi)):
                        self.ct = 0
                    self.dc = (math.exp(math.sin(self.ct)) - 0.36787944)*42.545906412
                    print(self.dc / 100)
                    for led in self.leds.values():
                        led.dc = int(self.dc)
                        led.pwm.ChangeDutyCycle(self.dc)
                    self.ct += self.sampling_freq
                    time.sleep(self.breathing_speed)
            else:
                print(event)
                if event.type == EventType.ON_CONVERSATION_TURN_STARTED:
                    self.fade_in(0.0003, "blue")
                    self.listening = True
                elif (event.type == EventType.ON_CONVERSATION_TURN_FINISHED and
                    event.args and not event.args['with_follow_on_turn']):
                    self.reset(0.005)
                    self.listening = False
                    self.ct = (3*math.pi)/2  # minima in range [0;2pi]
                elif event.type == EventType.ON_CONVERSATION_TURN_TIMEOUT:
                    self.reset(0.005)
                    for i in range(0, 2):
                        self.fade_in(0.0005, "red")
                        self.fade_out(0.0005, "red")
                self.event_queue.task_done()

    def fade_in(self, speed, color):
        done = False
        while not done:
            done = True
            for c, led in self.leds.items():
                if c != color and led.dc > 0:
                    led.dc -= 1
                    led.pwm.ChangeDutyCycle(led.dc)
                    done = False
                elif c == color and led.dc < 100:
                    led.dc += 1
                    led.pwm.ChangeDutyCycle(led.dc)
                    done = False
                print(c + " " + str(led.dc))
            time.sleep(speed)

    def fade_out(self, speed, leds):
        done = False
        if not isinstance(leds, list):
            leds = [leds]
        while not done:
            done = True
            for color, led in leds.items():
                if led.dc > 0:
                    led.dc -= 1
                    done = False
                print(color + " : " + str(led.dc))
                led.pwm.ChangeDutyCycle(led.dc)
            time.sleep(speed)
