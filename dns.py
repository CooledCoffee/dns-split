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

def get_from_cache(key, header_id):
    cached_time, cached_data = cache.get(key, (None, None))
    if cached_data is None:
        return None
    repacked_data = repack(cached_data, header_id, cached_time)
    if repacked_data is None:
        del cache[key]
        return None
    return repacked_data

def handle_request(data, addr):
    req = DNSRecord.parse(data)
    domain = str(req.q.qname).rstrip('.')
    key = '%s:%d' % (domain, req.questions[0].qtype)
    resp = get_from_cache(key, req.header.id)
    if resp is not None:
        log.info('Resolved "%s" @cache ...' % key)
        sock.sendto(resp, addr)
        return
    
    e = event.Event()
    cache[key + '/e'] = e
    start = time.time()
    dns = decide_dns(domain)
    log.info('Resolving "%s" @%s ...' % (key, dns))
    sock.sendto(data, (dns, 53))
    if e.wait(15):
        millis = (time.time() - start) * 1000
        log.info('Resolved "%s" @%s in %d ms.' % (key, dns, millis))
        cached_time, data = cache[key]
        data = repack(data, req.header.id, cached_time)
        sock.sendto(data, addr)
    else:
        log.info('Failed to resolve "%s" @%s.' % (key, dns))

def handle_response(data):
    resp = DNSRecord.parse(data)
    if len(resp.rr) == 0:
        return
    domain = str(resp.q.qname).rstrip('.')
    key = '%s:%d' % (domain, resp.questions[0].qtype)
    e = cache.get(key + '/e')
    if e is not None:
        cache[key] = (int(time.time()), data)
        e.set()
        del cache[key + '/e']

def handler(data, addr):
    req = DNSRecord.parse(data)
    if req.header.qr:
        handle_response(data)
    else:
        handle_request(data, addr)

def main():
    with open(os.path.join(os.path.dirname(__file__), 'foreigns')) as f:
        for line in f:
            line = line.strip()
            if line != '':
                FOREIGN_DOMAINS.append(line)
    while True:
        data, addr = sock.recvfrom(8192)
        gevent.spawn(handler, data, addr)
        
def repack(data, qid, cached_time):
    record = DNSRecord.parse(data)
    record.header.id = qid
    now = int(time.time())
    for r in record.rr:
        ttl = cached_time + r.ttl - now
        if ttl <= 0:
            return None
        r.ttl = ttl
    return record.pack()

def decide_dns(domain):
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
    handler.setFormatter(logging.Formatter('[%(asctime)s] [%(levelname)s] [%(funcName)s:%(lineno)d]\n%(message)s'))
    log.addHandler(handler)
    
    handler = FileHandler(os.path.join(os.path.dirname(__file__), 'dns.log'))
    handler.setLevel(logging.INFO)
    handler.setFormatter(logging.Formatter('[%(asctime)s] [%(levelname)s] [%(funcName)s:%(lineno)d]\n%(message)s'))
    log.addHandler(handler)
    
if __name__ == '__main__':
    init()
    main()
