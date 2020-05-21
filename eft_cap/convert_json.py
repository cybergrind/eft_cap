#!/usr/bin/env python3
import argparse
import logging
import json


logging.basicConfig(level=logging.DEBUG, format='%(asctime)s [%(levelname)s] %(name)s: %(message)s')
log = logging.getLogger('convert_json')


def parse_args():
    parser = argparse.ArgumentParser(description='DESCRIPTION')
    parser.add_argument('src')
    parser.add_argument('dst')
    # parser.add_argument('-m', '--mode', default='auto', choices=['auto', 'manual'])
    # parser.add_argument('-l', '--ll', dest='ll', action='store_true', help='help')
    return parser.parse_args()


def main():
    args = parse_args()
    with open(args.src) as src, open(args.dst, 'w') as dst:
        packets = json.load(src)
        for packet in packets:
            dst.write(json.dumps(packet))
            dst.write('\n')


if __name__ == '__main__':
    main()

