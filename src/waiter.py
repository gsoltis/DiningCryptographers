#!/usr/bin/env python
from argparse import ArgumentParser

from utils import load_pubnub


def inform_diners(pubsub, num_diners):
    diners = []
    results = []
    def recv(msg):

        if 'my_bit' in msg:
            results.append(msg)
            if len(results) == num_diners:
                pubsub.publish({'channel': 'to_waiter', 'message': 'the bill is settled'})
                return False
        else:
            name = msg['name']
            diners.append(name)
            if len(diners) == num_diners:
                pubsub.publish({'channel': 'to_waiter', 'message': {'diners': diners}})
        return True

    pubsub.subscribe({'channel': 'to_waiter', 'callback': recv})
    pubsub.publish({'channel': 'to_waiter', 'message': {'diners': diners}})

if __name__ == '__main__':
    parser = ArgumentParser()
    parser.add_argument('diners', help='Number of diners', type=int)
    args = parser.parse_args()
    pubsub = load_pubnub('pubnub_keys.cfg')
    inform_diners(pubsub, args.diners)
