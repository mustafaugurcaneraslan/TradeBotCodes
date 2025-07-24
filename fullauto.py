import subprocess
import time
from xconfig import BINANCE_SECRET_KEY, BINANCE_API_KEY
from binance.um_futures import UMFutures
from binance.error import ClientError

client = UMFutures(key=BINANCE_API_KEY, secret=BINANCE_SECRET_KEY)

def algo_calistir():
    subprocess.run(["python", "randomforestfantasy.py"])

while True: 
    algo_calistir()     
    time.sleep(5)   