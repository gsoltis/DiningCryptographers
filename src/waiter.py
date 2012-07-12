#!/usr/bin/env python
from argparse import ArgumentParser

from utils import load_pubnub

def recv(msg):
    print msg
    return False

def inform_diners(pubsub, num_diners):
    #history = pubsub.history({'channel': 'waiter', 'limit': num_diners + 1})
    diners = []
    #while len(diners) < num_diners:
    pubsub.subscribe({'channel': 'waiter', 'callback': recv})

if __name__ == '__main__':
    parser = ArgumentParser()
    parser.add_argument('diners', help='Number of diners', type=int)
    args = parser.parse_args()
    pubsub = load_pubnub('pubnub_keys.cfg')
    inform_diners(pubsub, args.diners)
