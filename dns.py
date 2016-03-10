#!/usr/bin/python2.7
# -*- coding: utf-8 -*-
from dnslib.dns import DNSRecord
from gevent import socket
from gevent.pool import Pool
from logging import StreamHandler, FileHandler
import logging
import os
import time

BUFFER_SIZE = 8192
CACHE_EXPIRE_SECONDS = 3600
DNS_PORT = 53
DOMESTIC_DNS = '223.5.5.5'
FOREIGN_DNS = '8.8.8.8'
FOREIGN_DOMAINS = []
SOCKET_TIMEOUT = 30
cache = {}
log = logging.getLogger()
sock = None

def calc_key(domain, type):
    key = '%s:%d' % (domain, type)
    return key.lower()

def check_resp(key, data):
    record = DNSRecord.parse(data)
    if len(record.rr) == 0:
        log.warn('No record returned for "%s".' % key)
    return len(record.rr) != 0

def clean_cache():
    now = time.time()
    cnt = 0
    for key, (cached_time, _) in cache.items():
        if now - cached_time > CACHE_EXPIRE_SECONDS:
            del cache[key]
            cnt += 1
    log.debug('Cleaned %d items from cache.' % cnt)

def decide_dns(domain):
    if 'google' in domain:
        return FOREIGN_DNS
    for d in FOREIGN_DOMAINS:
        if d == domain or domain.endswith('.' + d):
            return FOREIGN_DNS
    else:
        return DOMESTIC_DNS

def get_from_cache(key, header_id):
    cached_time, cached_data = cache.get(key, (None, None))
    if cached_data is None:
        return None
    repacked_data = repack(cached_data, header_id, cached_time)
    if repacked_data is None:
        del cache[key]
        return None
    return repacked_data

def handle(req, addr):
    start = time.time()
    record = parse(req)
    key = calc_key(record.q.domain, record.questions[0].qtype)
    resp = get_from_cache(key, record.header.id)
    if resp is None:
        dns = decide_dns(record.q.domain)
        log.info('Resolving "%s" @%s ...' % (key, dns))
        out_sock = socket.socket(type=socket.SOCK_DGRAM)  # @UndefinedVariable
        out_sock.sendto(req, (dns, DNS_PORT))
        try:
            socket.wait_read(out_sock.fileno(), SOCKET_TIMEOUT)
        except:
            log.warn('Timeout to receive "%s" from "%s".' % (key, dns))
            return
        resp = out_sock.recv(BUFFER_SIZE)
        if check_resp(key, resp):
            cache[key] = (int(time.time()), resp)
    else:
        dns = 'cache'
    sock.sendto(resp, addr)
    millis = int((time.time() - start) * 1000)
    log.info('Resolved "%s" @%s (%dms).' % (key, dns, millis))

def init():
    init_logging()
    init_foreign_domains()
    init_socks()
    
def init_foreign_domains():
    with open(os.path.join(os.path.dirname(__file__), 'foreigns')) as f:
        for line in f:
            line = line.strip()
            if line != '':
                FOREIGN_DOMAINS.append(line)
    
def init_logging():
    log.setLevel(logging.DEBUG)
    
    handler = StreamHandler()
    handler.setLevel(logging.DEBUG)
    handler.setFormatter(logging.Formatter('[%(asctime)s] [%(levelname)s] [%(funcName)s:%(lineno)d]\n%(message)s'))
    log.addHandler(handler)
    
    handler = FileHandler(os.path.join(os.path.dirname(__file__), 'dns.log'))
    handler.setLevel(logging.DEBUG)
    handler.setFormatter(logging.Formatter('[%(asctime)s] [%(levelname)s] [%(funcName)s:%(lineno)d]\n%(message)s'))
    log.addHandler(handler)
    
def init_socks():
    global sock
    sock = socket.socket(type=socket.SOCK_DGRAM)  # @UndefinedVariable
    sock.bind(('', DNS_PORT))
    
def main():
    init()
    run()
    
def parse(data):
    record = DNSRecord.parse(data)
    domain = str(record.q.qname).rstrip('.')
    record.q.domain = domain
    return record

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

def run():
    last_clean_time = time.time()
    pool = Pool(size=8)
    while True:
        data, addr = sock.recvfrom(BUFFER_SIZE)
        pool.spawn(handle, data, addr)
        if time.time() - last_clean_time > 60:
            log.debug('Currently %d greenlets.' % len(pool))
            clean_cache()
            last_clean_time = time.time()
    
if __name__ == '__main__':
    main()
    