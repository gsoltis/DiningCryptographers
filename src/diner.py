#!/usr/bin/env python
from argparse import ArgumentParser
import uuid

from utils import load_pubnub

def dine(pubsub, is_payer):
    print 'dining'
    name = str(uuid.uuid4())
    print name
    msg = {'msg': 'I am here', 'name': name}
    print pubsub.publish({'channel': 'waiter', 'message': msg})


if __name__ == '__main__':
    parser = ArgumentParser()
    parser.add_argument('-p', '--payer', dest='is_payer', action='store_true')
    args = parser.parse_args()
    pubsub = load_pubnub('pubnub_keys.cfg')
    dine(pubsub, args.is_payer)
