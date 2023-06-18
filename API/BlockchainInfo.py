import gc
import time
from queue import Queue
from threading import Thread

import orjson
import requests


class BlockchainInfo:
    bucket = Queue()
    requestCount = 0
    timeoutSecs = 10

    # https://www.blockchain.com/explorer/api/q
    # Rate limit should be 1 request per 10 seconds
    def __init__(self, timeoutSecs=10):
        self.timeoutSecs = timeoutSecs

        self.bucket.put(None)

        Thread(target=self.produceTokensThread, daemon=True).start()

    def produceTokensThread(self):
        while True:
            if self.bucket.qsize() == 0:
                # The bucket could have been emptied during the previous sleep time
                time.sleep(self.timeoutSecs)
                self.bucket.put(None)

            time.sleep(self.timeoutSecs)

    def getVoutAddress(self, txId):
        self.bucket.get()

        for i in range(10):
            try:
                print("Blockchaininfo request for: " + txId)
                response = requests.get("https://api.blockchain.info/haskoin-store/btc/transaction/" + txId,
                                        timeout=600)
            except Exception as e:
                print(e)
                print("Blockchain.info exception caught")
                gc.collect()
                continue
            finally:
                self.requestCount += 1
                print("Blockchain.info requests: " + str(self.requestCount))
                try:
                    self.bucket.task_done()
                except Exception as e:
                    print(e)

            if response.status_code != 200:
                print("Error code " + str(
                    response.status_code) + " received while querying the blockchaininfo api. Transaction hash: " +
                      txId + " retrying...")
                continue

            jdata = orjson.loads(response.text)
            response.close()

            if 'outputs' not in jdata:
                print("No outputs key in the json data from blockchaininfo for transaction: " + txId)
                return None

            voutContent = []
            for voutId in range(len(jdata['outputs'])):
                if 'address' not in jdata['outputs'][voutId] or 'value' not in jdata['outputs'][voutId]:
                    print("VOut address or value not found in blockchaininfo outputs for transaction: " + txId)
                    return None

                if jdata['outputs'][voutId]['address'] is not None:
                    voutContent.append({
                        'value': jdata['outputs'][voutId]['value'] / 100000000,
                        'n': voutId,
                        'scriptPubKey': {
                            'address': jdata['outputs'][voutId]['address']
                        }
                    })

            return voutContent

        print("Request to blockchaininfo timed out for transaction: " + txId)
        return None
