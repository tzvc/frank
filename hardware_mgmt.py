#!/usr/bin/env python

import RPi.GPIO as GPIO
import time
import threading
import queue
import math

from google.assistant.library.event import EventType

class HwComponent:
    def __init__(self, pin, input_mode):
        self.pin = pin
        self.state = None
        self.pwm = None
        self.dc = 0

        GPIO.setup(pin, input_mode)


class Led(HwComponent):
    def __init__(self, pin):
        super().__init__(pin, GPIO.OUT)
        self.pwm = GPIO.PWM(self.pin, 100);
        self.pwm.start(self.dc)
            

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
                    self.fade_in(0.0003, "blue")
                    self.listening = True
                elif (event.type == EventType.ON_CONVERSATION_TURN_FINISHED and
                    event.args and not event.args['with_follow_on_turn']):
                    self.fade_out(0.005, ["red", "green", "blue"])
                    self.listening = False
                    self.ct = (3*math.pi)/2  # minima in range [0;2pi]
                elif event.type == EventType.ON_CONVERSATION_TURN_TIMEOUT:
                    self.fade_out(0.0003, ["red", "green", "blue"])
                    for i in range(0, 2):
                        self.fade_in(0.0008, "red")
                        self.fade_out(0.0008, "red")
                elif event.type == EventType.ON_START_FINISHED:
                    self.service_started = True
                self.event_queue.task_done()

    def fade_in(self, speed, selected_leds):
        done = False
        print("Fading led " + str(selected_leds) + " in")
        while not done:
            done = True
            for c, led in self.leds.items():
                if c != selected_leds and led.dc > 0:
                    led.dc -= 1
                    led.pwm.ChangeDutyCycle(led.dc)
                    done = False
                elif c == selected_leds and led.dc < 100:
                    led.dc += 1
                    led.pwm.ChangeDutyCycle(led.dc)
                    done = False
            time.sleep(speed)

    def fade_out(self, speed, selected_leds):
        done = False
        if not isinstance(selected_leds, list):
            selected_leds = [selected_leds]
        print("Fading led " + str(selected_leds) + " out")
        while not done:
            done = True
            for led in selected_leds:
                if self.leds[led].dc > 0:
                    self.leds[led].dc -= 1
                    done = False
                self.leds[led].pwm.ChangeDutyCycle(self.leds[led].dc)
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
