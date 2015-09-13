import argparse
from config import update_config_from_args

def parse_anansi_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("-c","--config",help="anansi configuration file (updates defaults)")
    parser.add_argument("-l","--logging_config",help="anansi logging configuration file (replaces defaults)")
    parser.add_argument("-v","--verbose",help="turn on verbose messages",default=False)
    args = parser.parse_args()
    return args

if __name__ == "__main__":
    args = parse_anansi_args()
    print args.__dict__
