#!/usr/bin/env python

import RPi.GPIO as GPIO
import simpleaudio as sa
import time
import threading
import queue
import math

from google.assistant.library.event import EventType

class HwComponent:
    def __init__(self, pin):
        self.pin = pin
        self.state = None
        self.pwm = None
        self.dc = 0

class Led(HwComponent):
    def __init__(self, pin):
        super().__init__(pin)
        GPIO.setup(pin, GPIO.OUT)
        self.pwm = GPIO.PWM(self.pin, 100);
        self.pwm.start(self.dc)

class Button(HwComponent):
    def __init__(self, pin):
        super().__init__(pin)
        GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)

class LedMgmtThread(threading.Thread):
    """
    This thread manage integrated LEDs
    it poll event from a event queue and trigger
    corresponding animations
    """
    def __init__(self, event_queue, shutdown_flag):
        super().__init__()
        self.wave_obj = sa.WaveObject.from_wave_file("./sound/wakeup.wav")
        self.event_queue = event_queue
        self.shutdown_flag = shutdown_flag
        self.breathing_speed = 0.0079  # speed of the breathing effect (12/min)
        self.service_started = False
        self.listening = False
        self.dc = 0                    # PWM duty cycle
        self.ct = 0
        self.sampling_freq = 0.01  # sampling frequency for the breathing function

        GPIO.setwarnings(False)
        GPIO.setmode(GPIO.BCM)

        self.leds = {"red" : Led(18),
                     "green" : Led(13),
                     "blue" : Led(12)}

    def run(self):
        while not self.shutdown_flag.is_set():
            try:
                event = self.event_queue.get_nowait()
            except queue.Empty:
                if self.service_started and not self.listening:
                    self.breath()
            else:
                print(event)
                if event.type == EventType.ON_CONVERSATION_TURN_STARTED:
                    self.fade([("red", 0), ("green", 0), ("blue", 100)], 0.0003)
                    self.listening = True
                    self.wave_obj.play()
                elif (event.type == EventType.ON_CONVERSATION_TURN_FINISHED and
                    event.args and not event.args['with_follow_on_turn']):
                    self.fade([("red", 0), ("green", 0), ("blue", 0)], 0.005)
                    self.listening = False
                    self.ct = (3*math.pi)/2  # minima in range [0;2pi]
                elif event.type == EventType.ON_CONVERSATION_TURN_TIMEOUT:
                    self.fade([("red", 0), ("green", 0), ("blue", 0)], 0.0003)
                    for i in range(0, 2):
                        self.fade(("red", 100), 0.0008)
                        self.fade(("red", 0), 0.0008)
                elif event.type == EventType.ON_START_FINISHED:
                    self.service_started = True
                self.event_queue.task_done()

    def fade(self, leds, speed):
        done = False
        if not isinstance(leds, list):
            leds = [leds]
        print(leds)
        while not done:
            done = True
            for led, target_dc in leds:
                if self.leds[led].dc < target_dc:
                    self.leds[led].dc += 1
                elif self.leds[led].dc > target_dc:
                    self.leds[led].dc -= 1
                self.leds[led].pwm.ChangeDutyCycle(self.leds[led].dc)
                if self.leds[led].dc != target_dc:
                    done = False
            time.sleep(speed)

    def breath(self):
        if (self.ct > (2*math.pi)):
            self.ct = 0
        dc = (math.exp(math.sin(self.ct)) - 0.36787944)*42.545906412
        for led in self.leds.values():
            led.dc = int(dc)
            led.pwm.ChangeDutyCycle(dc)
        self.ct += self.sampling_freq
        time.sleep(self.breathing_speed)

class ButtonMgmtThread(threading.Thread):
    def __init__(self, assistant, shutdown_flag):
        super().__init__()
        self.assistant = assistant
        self.shutdown_flag = shutdown_flag

    def run(self):
        self.buttons = {"trigger" : Button(16)}

        while not self.shutdown_flag.is_set():
            chan = GPIO.wait_for_edge(self.buttons["trigger"].pin,
                                      GPIO.FALLING,
                                      bouncetime=600,
                                      timeout=700)
            if chan is not None:
                print("Starting mannual turn")
                self.assistant.start_conversation()
