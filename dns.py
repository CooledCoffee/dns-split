#!/usr/bin/python2.7
# -*- coding: utf-8 -*-
from dnslib import DNSRecord
from gevent import event, socket
from logging import StreamHandler, FileHandler
import gevent
import logging
import os
import time

log = logging.getLogger()

DOMESTIC_DNS = '223.5.5.5'
FOREIGN_DNS = '8.8.8.8'
FOREIGN_DOMAINS = []
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)  # @UndefinedVariable
sock.bind(('', 53))

cache = {}

def handle_request(s, data, addr):
    req = DNSRecord.parse(data)
    qname = str(req.q.qname)
    key = '%s:%d' % (qname.rstrip('.'), req.questions[0].qtype)
    result = cache.get(key)
    if result is not None:
        cache_time, data = result
        repacked_data = repack(data, req.header.id, cache_time)
        if repacked_data is None:
            del cache[key]
        else:
            log.info('Resolved "%s" @cache ...' % key)
            s.sendto(repacked_data, addr)
            return
    
    e = event.Event()
    cache[key + '/e'] = e
    start = time.time()
    dns = decide_dns(qname)
    log.info('Resolving "%s" @%s ...' % (key, dns))
    sock.sendto(data, (dns, 53))
    if e.wait(15):
        log.info('Resolved "%s" @%s in %d ms.' % (key, dns, (time.time() - start) * 1000))
        expire, data = cache[key]
        data = repack(data, req.header.id, expire)
        s.sendto(data, addr)
    else:
        log.info('Failed to resolve "%s" @%s.' % (key, dns))

def handle_response(data):
    req = DNSRecord.parse(data)
    qname = str(req.q.qname)
    key = '%s:%d' % (qname.rstrip('.'), req.questions[0].qtype)
    e = cache.get(key + '/e')
    if e is not None:
        cache[key] = (int(time.time()), data)
        e.set()
        del cache[key + '/e']

def handler(s, data, addr):
    req = DNSRecord.parse(data)
    if req.header.qr:
        handle_response(data)
    else:
        handle_request(s, data, addr)

def main():
    with open(os.path.join(os.path.dirname(__file__), 'foreigns')) as f:
        for line in f:
            line = line.strip()
            if line != '':
                FOREIGN_DOMAINS.append(line)
    while True:
        data, addr = sock.recvfrom(8192)
        gevent.spawn(handler, sock, data, addr)
        
def repack(data, qid, cache_time):
    record = DNSRecord.parse(data)
    record.header.id = qid
    now = int(time.time())
    for r in record.rr:
        ttl = cache_time + r.ttl - now
        if ttl <= 0:
            return None
        r.ttl = ttl
    return record.pack()

def decide_dns(qname):
    domain = qname.rstrip('.')
    if 'google' in domain:
        return FOREIGN_DNS
    for d in FOREIGN_DOMAINS:
        if d == domain or domain.endswith('.' + d):
            return FOREIGN_DNS
    else:
        return DOMESTIC_DNS
    
def init():
    log.setLevel(logging.INFO)
    
    handler = StreamHandler()
    handler.setLevel(logging.INFO)
    handler.setFormatter(logging.Formatter('%(message)s'))
    log.addHandler(handler)
    
    handler = FileHandler(os.path.join(os.path.dirname(__file__), 'dns.log'))
    handler.setLevel(logging.INFO)
    handler.setFormatter(logging.Formatter('[%(asctime)s] [%(levelname)s] [%(process)d:%(threadName)s] [%(name)s:%(funcName)s:%(lineno)d]\n%(message)s'))
    log.addHandler(handler)
    
if __name__ == '__main__':
    init()
    main()
