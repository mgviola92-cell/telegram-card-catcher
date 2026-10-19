"""Run manually or from a scheduled maintenance job; never runs on every message."""
import argparse
from app.storage import prune_counted_messages

if __name__=='__main__':
    parser=argparse.ArgumentParser(description='Bounded cleanup of old activity replay IDs')
    parser.add_argument('--days',type=int,default=7)
    parser.add_argument('--batch',type=int,default=1000)
    args=parser.parse_args()
    print('Deleted old message IDs:',prune_counted_messages(args.days,args.batch))
