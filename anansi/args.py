import argparse
from anansi import config

def parse_anansi_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("-c","--config",help="anansi configuration file (updates defaults)")
    parser.add_argument("-l","--logging_config",help="anansi logging configuration file (replaces defaults)")
    args = parser.parse_args()
    return args

def init():
    args = parse_anansi_args()
    if args.config:
        config.build_config(args.config,args.logging_config)
    
