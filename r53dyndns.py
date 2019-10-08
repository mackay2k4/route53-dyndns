#! /usr/bin/env python
"""
Updates a set of route53-hosted A record(s) with the current ip of the system.
"""
import dns.resolver
import boto.route53
import logging
import os
from optparse import OptionParser
from re import sub
import socket
import sys

parser = OptionParser()
parser.add_option('-R', '--record', type='string', dest='records_to_update', help='The A record(s) to update (comma-separated).')
parser.add_option('-ip6R', '--record', type='string', dest='ip6records_to_update', help='The A record(s) to update (comma-separated).')
parser.add_option('-v', '--verbose', dest='verbose', default=False, help='Enable Verbose Output.', action='store_true')
parser.add_option('-T', '--ttl', type='int', dest='ttl', default=300, help='Set record TTL in seconds (default 300).')
(options, args) = parser.parse_args()

if options.records_to_update is None:
    logging.error('Please specify A record(s) with the -R switch.')
    parser.print_help()
    sys.exit(-1)
if options.verbose:
    logging.basicConfig(
        level=logging.INFO,
    )

# get external ip
resolver = dns.resolver.Resolver()
resolver.nameservers = [socket.gethostbyname('resolver1.opendns.com')]
for rdata in resolver.query('myip.opendns.com', 'A'):
    current_ip = str(rdata)
    logging.info('Current IP address: %s', current_ip)
for rdata in resolver.query('myip.opendns.com', 'AAAAA'):
    current_ipv6 = str(rdata)
    logging.info('Current IP address: %s', current_ipv6)
    
records_to_update = options.records_to_update.split(',')
ip6records_to_update = options.ip6records_to_update.split(',')
zone_to_update = '.'.join(records_to_update[0].split('.')[-2:])

try:
    socket.inet_aton(current_ip)
    conn = boto.route53.connect_to_region(os.getenv('AWS_CONNECTION_REGION', 'eu-west-1'))
    zone = conn.get_zone(zone_to_update)
    for ip6record_to_update in ip6records_to_update:
        ip6record_updated = False
        for ip6record in zone.get_records():
            # substitute '*' with '\052' due to boto weirdness
            # record = sub(r'\052','*', str(record))
            sub_ip6record_to_update = sub(r'\*',r'\\052',ip6record_to_update)
            if '<ip6Record:' + sub_ip6record_to_update + '.:A' in str(ip6record)  and not ip6record_updated:
                if current_ipv6 in ip6record.to_print():
                    logging.info('%s IPv6 matches, doing nothing.', ip6record_to_update)
                else:
                    logging.info('%s IPv6 does not match, update needed.', ip6record_to_update)
                    zone.delete_a(sub_ip6record_to_update)
                    zone.add_a(ip6record_to_update, current_ipv6, ttl=options.ttl)
                ip6record_updated = True
        if not ip6record_updated:
            logging.info('%s IPv6record not found, add needed', ip6record_to_update)
            zone.add_a(ip6record_to_update, current_ipv6, ttl=options.ttl)
            ip6record_updated = True
            
    for record_to_update in records_to_update:
        record_updated = False
        for record in zone.get_records():
            # substitute '*' with '\052' due to boto weirdness
            # record = sub(r'\052','*', str(record))
            sub_record_to_update = sub(r'\*',r'\\052',record_to_update)
            if '<Record:' + sub_record_to_update + '.:A' in str(record)  and not record_updated:
                if current_ip in record.to_print():
                    logging.info('%s IP matches, doing nothing.', record_to_update)
                else:
                    logging.info('%s IP does not match, update needed.', record_to_update)
                    zone.delete_a(sub_record_to_update)
                    zone.add_a(record_to_update, current_ip, ttl=options.ttl)
                record_updated = True

        if not record_updated:
            logging.info('%s record not found, add needed', record_to_update)
            zone.add_a(record_to_update, current_ip, ttl=options.ttl)
            record_updated = True
except socket.error as e:
     print repr(e)
