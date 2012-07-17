from ConfigParser import ConfigParser

from Pubnub import Pubnub

def load_pubnub(config_file):
    config = ConfigParser()
    config.read(config_file)
    pub_key = config.get('pubnub', 'publish')
    sub_key = config.get('pubnub', 'subscribe')
    secret = config.get('pubnub', 'secret')
    pn = Pubnub(pub_key, sub_key, secret, ssl_on=True)
    return pn

xor_list = lambda l: reduce(lambda accum, bit: accum ^ bit, l)
