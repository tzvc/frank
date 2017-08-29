#!/usr/bin/env python

from __future__ import print_function

# added for frank
import hardware_mgmt as hw
import threading
import queue
import sys
import signal

import argparse
import os.path
import json

import google.oauth2.credentials

from google.assistant.library import Assistant
from google.assistant.library.event import EventType
from google.assistant.library.file_helpers import existing_file

class SignalHandler:
    """
    This object handle signals and stop the workers cleanly
    """
    shutdown_flag = None
    workers = None

    def __init__(self, shutdown_flag, workers):
        self.shutdown_flag = shutdown_flag
        self.workers = workers

    def __call__(self, signum, frame):
        self.shutdown_flag.set()
        for worker in self.workers:
            worker.join()
        sys.exit(0)

def main():
    num_workers = 1
    shutdown_flag = threading.Event()
    event_queue = queue.Queue()
    hw_threads = [hw.LedMgmtThread(event_queue, shutdown_flag) for i in range(num_workers)]

    signal.signal(signal.SIGINT, SignalHandler(shutdown_flag, hw_threads))

    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument('--credentials', type=existing_file,
                        metavar='OAUTH2_CREDENTIALS_FILE',
                        default=os.path.join(
                            os.path.expanduser('~/.config'),
                            'google-oauthlib-tool',
                            'credentials.json'
                        ),
                        help='Path to store and read OAuth2 credentials')
    args = parser.parse_args()
    with open(args.credentials, 'r') as f:
        credentials = google.oauth2.credentials.Credentials(token=None,
                                                            **json.load(f))

    with Assistant(credentials) as assistant:
        hw_threads.append(hw.LedMgmtThread(assistant, shutdown_flag))
        for hw_thread in hw_threads:
            hw_thread.start()
        for event in assistant.start():
            event_queue.put(event)

if __name__ == '__main__':
    main()
