#!/usr/bin/env python
from argparse import ArgumentParser
from ConfigParser import ConfigParser
import json
from random import randint
import requests
from threading import Thread, Event
import uuid

from websocket import WebSocketApp

from utils import xor_list

config = ConfigParser()
config.read('firebase.cfg')

BASE_URL = config.get('firebase', 'root')

def entity(*path):
    return 'https://%s/%s.json' % (BASE_URL, '/'.join(path))

def secret_bit():
    return randint(0, 1)

class Firebase(Thread):

    def __init__(self):
        super(Firebase, self).__init__()
        self.sock = WebSocketApp(url='ws://%s.ws' % BASE_URL,
                                 on_message=self.msg_handler,
                                 on_open=self.connect_handler,
                                 on_error=self.err_handler)
        self.ready = Event()
        self._rn = 0

    def run(self):
        self.sock.run_forever()

    def connect_handler(self, sock):
        sock.send(u'version=1')

    def err_handler(self, exc):
        print exc

    def send(self, msg):
        self.sock.send(msg)

    @property
    def rn(self):
        self._rn = self._rn + 1
        return self._rn

    def listen_to_channel(self, channel):
        print 'listening to %s' % channel
        self.send('1')
        data = {
            "rn": "%i" % self.rn,
            "payload": {
                "action": "listen",
                "path": channel
            }
        }
        self.send(json.dumps(data))

    def close(self):
        self.sock.close()

def is_data_packet(payload):
    return isinstance(payload, dict) and 'data' in payload

class Waiter(Firebase):
    def __init__(self, num_diners):
        super(Waiter, self).__init__()
        self.waiting_for_diners = True
        self.num_diners = num_diners
        self.bit_count = 0
        self.diners = []

    def msg_handler(self, sock, msg):
        print 'msg: %s' % msg
        if msg == 'ok':
            self.ready.set()
        else:
            payload = json.loads(msg)
            if is_data_packet(payload):
                data = payload['data']
                path = data.get('path', '')
                if self.waiting_for_diners and path[:8] == '/diners/' and 'name' in data.get('data', {}):
                    name = data['data']['name']
                    print 'got diner named %s' % name
                    self.diners.append(name)
                    if len(self.diners) == self.num_diners:
                        print 'ready to dine'
                        ready_entity = entity('diners', 'ready')
                        put_data = {
                            'ready': 'true'
                        }
                        resp = requests.put(ready_entity, data=json.dumps(put_data))
                        print resp.status_code
                elif path[:len('/announce/')] == '/announce/' and data is not None:
                    self.bit_count = self.bit_count + 1
                    if self.bit_count == self.num_diners:
                        # we're done, post a notice
                        data = {'done': 'true'}
                        requests.put(entity('diners', 'done'), data=json.dumps(data))
                        self.close()



class Diner(Firebase):

    def __init__(self):
        super(Diner, self).__init__()
        self.diners_ready = Event()
        self.secrets_ready = Event()
        self.bits_ready = Event()

    def msg_handler(self, sock, msg):
        if msg == 'ok':
            self.ready.set()
        else:
            payload = json.loads(msg)
            if is_data_packet(payload):
                path = payload['data'].get('path', '')
                data = payload['data']['data']
                if path == '/diners/ready' and data is not None:
                    self.diners_ready.set()
                elif path == '/diners/done' and data is not None:
                    self.bits_ready.set()
                    self.close()
                elif path[:9] == '/secrets/':
                    if data and 'bit' in data:
                        self.secrets.append(data['bit'])
                        if len(self.secrets) == self.secret_count:
                            self.secrets_ready.set()

    def get_secrets(self, to_watch):
        self.secret_count = len(to_watch)
        self.secrets = []
        if self.secret_count > 0:
            for channel in to_watch:
                channel = '/secrets/%s' % channel
                self.listen_to_channel(channel)
        else:
            self.secrets_ready.set()


def clear_session():
    requests.delete(entity('diners'))
    requests.delete(entity('secrets'))
    requests.delete(entity('announce'))

def run():
    worker = Waiter(num_diners=3)
    worker.start()
    clear_session()
    worker.ready.wait()
    worker.listen_to_channel('/diners')
    worker.listen_to_channel('/announce')
    print 'ready for diners'
    worker.join()

def get_names(name, diner_data):
    names = []
    for k, v in diner_data.iteritems():
        if k == 'ready':
            continue
        if v['name'] != name:
            names.append(v['name'])
    return names

def establish_secrets(name, others):
    results = []
    to_watch = []
    for other in others:
        k = [name, other]
        k.sort()
        generate = name == k[0]
        k = '_'.join(k)
        if generate:
            # do a put
            bit = secret_bit()
            results.append(bit)
            k_entity = entity('secrets', k)
            data = {'bit': bit}
            resp = requests.put(k_entity, data=json.dumps(data))
        else:
            # need to listen
            to_watch.append(k)
    return results, to_watch

def announce_bit(secrets, is_payer):
    bit = xor_list(secrets)
    if is_payer:
        bit = int(not bit)
    data = {'bit': bit}
    requests.post(entity('announce'), data=json.dumps(data))

def run_diner(is_payer):
    worker = Diner()
    worker.start()
    worker.ready.wait()
    worker.listen_to_channel('/diners/ready')
    worker.listen_to_channel('/diners/done')
    name = str(uuid.uuid4())
    data = {
        'name': name
    }
    data = json.dumps(data)
    diners_entity = entity('diners')
    requests.post(diners_entity, data=data)
    worker.diners_ready.wait()
    resp = requests.get(diners_entity)
    diner_data = resp.json
    others = get_names(name, diner_data)
    secrets, to_watch = establish_secrets(name, others)
    worker.get_secrets(to_watch)
    worker.secrets_ready.wait()
    secrets = secrets + worker.secrets
    announce_bit(secrets, is_payer)
    print 'waiting for bits'
    worker.bits_ready.wait()
    print 'got bits'
    resp = requests.get(entity('announce'))
    bits = []
    for _, data in resp.json.iteritems():
        bits.append(data['bit'])
    result = xor_list(bits)
    if result:
        print 'A diner paid'
    else:
        print 'The NSA paid'
    worker.join()

if __name__ == '__main__':
    parser = ArgumentParser()
    parser.add_argument('-d', '--diner', dest='is_diner', action='store_true')
    parser.add_argument('-p', '--payer', dest='is_payer', action='store_true')
    args = parser.parse_args()
    if args.is_diner:
        run_diner(is_payer=args.is_payer)
    else:
        run()
