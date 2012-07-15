#!/usr/bin/env python
from argparse import ArgumentParser
from Queue import Queue
from random import randint
from threading import Thread, Event
from time import sleep
import uuid

from utils import load_pubnub


def secret_bit():
    return randint(0, 1)

def recv_msg_fn(channel, pubsub, queue, cb):
    def recv_msg():
        def _recv(msg):
            return cb(msg, queue)
        pubsub.subscribe({'channel': channel, 'callback': _recv})
    return recv_msg


class AckedPublisher(Thread):

    def __init__(self, channel, msg, pubsub):
        super(AckedPublisher, self).__init__()
        self.channel = channel
        self.msg = msg
        self.pubsub = pubsub
        self.worker = Thread(target=recv_msg_fn(self.channel, self.pubsub, None, self.recv))
        self._stop = Event()

    def recv(self, msg, _):
        if msg == 'ack':
            self.stop()
            return False
        return True

    def stop(self):
        self._stop.set()

    def run(self):
        self.worker.start()
        while not self._stop.is_set():
            self.pubsub.publish({'channel': self.channel, 'message': self.msg})
            sleep(1)
        self.worker.join()



def establish_secret_fn(channel, pubsub, other, secret_q):
    def recv_secret(msg, q):
        if 'secret' in msg:
            q.put({'other': other, 'secret': msg['secret']})
            return False
        return True

    def establish_secret():
        i = channel.index(other)
        if i == 0:
            # we are waiting for them to publish a secret
            worker = Thread(target=recv_msg_fn(channel, pubsub, secret_q, recv_secret))
            worker.start()
            worker.join()
            pubsub.publish({'channel': channel, 'message': 'ack'})
        else:
            # we are publishing the secret
            secret = secret_bit()
            publisher = AckedPublisher(channel, {'secret': secret}, pubsub)
            publisher.start()
            publisher.join()
            secret_q.put({'other': other, 'secret': secret})
    return establish_secret


def establish_secrets(name, others, pubsub):
    secret_q = Queue()
    secrets = {}
    for other in others:
        channel_name = [name, other]
        channel_name.sort()
        channel_name = '.'.join(channel_name)
        worker = Thread(target=establish_secret_fn(channel_name, pubsub, other, secret_q))
        worker.start()

    while len(secrets) < len(others):
        item = secret_q.get()
        secrets[item['other']] = item['secret']
        secret_q.task_done()
    secret_q.join()
    return secrets

def dine(pubsub, is_payer):
    name = str(uuid.uuid4())
    results_q = Queue()
    names, waiter = get_names(name, results_q)
    names.remove(name)
    print 'establishing secrets'
    secrets = establish_secrets(name, names, pubsub)
    print name, secrets
    result = announce_bit(name, is_payer, secrets, pubsub, results_q)
    if result:
        print 'A diner paid'
    else:
        print 'The NSA paid'
    waiter.join()

def announce_bit(name, is_payer, secrets, pubsub, results_q):
    xor_list = lambda l: reduce(lambda accum, bit: accum ^ bit, l)
    bit = xor_list(secrets.values())
    if is_payer:
        print 'is payer'
        bit = int(not bit)

    pubsub.publish({'channel': 'to_waiter', 'message': {'my_bit': bit, 'name': name}})
    print 'my_bit: %i' % bit
    results = []
    while len(results) < len(secrets):
        item = results_q.get()
        results_q.task_done()
        if item['name'] != name:
            results.append(item['my_bit'])
    results.append(bit)
    print results
    bit = xor_list(results)
    return bool(bit)


def on_waiter_msg(msg, q):
    if 'diners' in msg:
        q['names'].put(msg['diners'])
    elif 'the bill is settled' == msg:
        return False
    elif 'my_bit' in msg:
        q['results'].put(msg)
    return True


def get_names(name, results_q):
    waiter_q = Queue()
    worker = recv_msg_fn('to_waiter', pubsub, {'names': waiter_q, 'results': results_q}, on_waiter_msg)
    waiter = Thread(target=worker)
    waiter.start()
    sleep(1)
    msg = {'msg': 'I am here', 'name': name}
    pubsub.publish({'channel': 'to_waiter', 'message': msg})

    names = waiter_q.get()
    #print names
    waiter_q.task_done()
    #waiter.join()
    return names, waiter

if __name__ == '__main__':
    parser = ArgumentParser()
    parser.add_argument('-p', '--payer', dest='is_payer', action='store_true')
    args = parser.parse_args()
    pubsub = load_pubnub('pubnub_keys.cfg')
    dine(pubsub, args.is_payer)
    print 'done'
