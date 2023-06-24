import time
from datetime import datetime

import requests
import orjson
import gc

from queue import Empty, Queue
from threading import Thread

from Database.Database import Database


class Bitcoinexplorer:
    conn = None
    threads = 256
    blockchaininfo = None

    def __init__(self, conn, blockchaininfo):
        self.conn = conn
        self.blockchaininfo = blockchaininfo

    def queryAttackerAddresses(self):
        cursor = self.conn.cursor()

        # Find all transactions
        cursor.execute("SELECT DISTINCT \"Address\" FROM \"RansomData\";")

        return cursor.fetchall()

    def queryVictimTransactions(self):
        cursor = self.conn.cursor()

        # Find all transactions
        cursor.execute("SELECT \"Id\", \"Hash\" FROM \"RansomTransactions\" WHERE \"Id\" NOT IN ("
                       "    SELECT DISTINCT \"TransactionId\" FROM \"VictimAddresses\");")

        return cursor.fetchall()

    def queryVictimAddressess(self):
        cursor = self.conn.cursor()

        # Find all transactions
        cursor.execute("SELECT DISTINCT \"Address\" FROM \"VictimAddresses\""
                       "WHERE \"Address\" NOT IN (SELECT DISTINCT \"VictimAddress\" FROM \"DepositTransactions\")"
                       "GROUP BY \"Address\";")

        return cursor.fetchall()

    def findBlockOrCache(self, blockhash, conn):
        cursor = conn.cursor()

        cursor.execute("EXECUTE selBlockCache ('%s')" % str(blockhash))

        res = cursor.fetchall()
        success = False
        content = None

        if len(res) > 0:
            success = True
            content = res[0][0]
        else:
            for i in range(10):
                # Query the bitcoin explorer api and update the row
                try:
                    response = requests.get("http://localhost:3002/api/block/" + blockhash, timeout=600)
                except Exception as e:
                    print(e)
                    print("Exception caught, calling garbage collector")
                    gc.collect()
                    time.sleep(60)
                    continue

                if response.status_code != 200:
                    print("Error code " + str(
                        response.status_code) + " received while querying the bitcoinexplorer api. Block hash: " +
                          blockhash + " retrying...")
                    time.sleep(60)
                    continue

                # Parse the json and verify that the data is valid
                jdata = orjson.loads(response.text)
                response.close()

                if 'height' not in jdata or 'tx' not in jdata:
                    continue

                success = True
                content = orjson.dumps(jdata)

                break

            try:
                # Insert this content into the database
                cursor.execute("EXECUTE insBlockCache (%s, %s)", (blockhash, content.decode("utf-8")))
                conn.commit()
            except Exception:
                conn.rollback()
                conn.commit()

        if success:
            return orjson.loads(content)
        else:
            return None

    # Function to find a transaction, find all source addresses and cache the result in the database
    def findTransactionOrCache(self, txId, conn, noChecks=False):
        res = self.findTransactionOrCacheInternal(txId, conn, noChecks)

        try:
            if res is None:
                # Log this in the invalid transactions table
                cursor = conn.cursor()

                print("Failed transaction: " + txId)
                conn.commit()
        except Exception:
            conn.rollback()
            conn.commit()
            print(
                "Inserting failed transaction into the failed transaction list failed. Maybe it's already in the list? Transaction: " + txId)

        return res

    def findTransactionOrCacheInternal(self, txId, conn, noChecks):
        # First, check if this entry is in the cache. If not, request it from the api and cache it
        cursor = conn.cursor()

        cursor.execute("EXECUTE selTxCache ('%s')" % str(txId))

        res = cursor.fetchall()
        success = False
        content = None

        if len(res) > 0:
            success = True
            content = res[0][0]
        else:
            # print("Cache miss for transaction " + txId)

            # Request the content from the API and insert it into the database. Retry up to 10 times
            for i in range(10):
                # Query the bitcoin explorer api and update the row
                try:
                    # Without the postman runtime user agent, the API might only return partial data
                    response = requests.get("http://localhost:3002/api/tx/" + txId,
                                            headers={'User-Agent': 'PostmanRuntime/7.32.2'}, timeout=600)
                except Exception as e:
                    print(e)
                    print("Exception caught, calling garbage collector")
                    gc.collect()
                    time.sleep(60)
                    continue

                if response.status_code != 200:
                    print("Error code " + str(
                        response.status_code) + " received while querying the bitcoinexplorer api. Transaction hash: " +
                          txId + " retrying...")
                    time.sleep(60)
                    continue

                # Parse the json and verify that the data is valid
                jdata = orjson.loads(response.text)
                response.close()

                if 'vin' not in jdata or 'vout' not in jdata:
                    continue

                if not noChecks:
                    if 'blockhash' not in jdata:
                        print("No blockhash in transaction " + txId)
                        return None

                    for a in range(len(jdata["vin"])):
                        if 'scriptSig' not in jdata["vin"][a] or 'address' not in jdata["vin"][a]["scriptSig"]:
                            if 'coinbase' in jdata["vin"][a]:
                                # This is a coinbase transaction, which doesn't have an input address
                                jdata["vin"][a]["scriptSig"] = {"address": 'coinbase'}
                            elif 'txid' not in jdata["vin"][a] or 'vout' not in jdata["vin"][a]:
                                print("No txid or vout in vin entry for transaction " + txId)
                                return None
                            else:
                                rec = self.findTransactionOrCache(jdata["vin"][a]["txid"], conn, True)
                                if rec is None:
                                    # Try to resolve the vout lookup using blockchain.info
                                    print("Rec is null")
                                    voutInfo = self.blockchaininfo.getVoutAddress(jdata["vin"][a]["txid"])
                                    if voutInfo is None:
                                        print(
                                            "Recursive call for vout lookup returned none for transaction " + txId + ". Impossible to determine address")
                                        return None

                                    rec = {
                                        'vout': voutInfo
                                    }

                                if 'vout' not in rec:
                                    # Try to resolve the vout lookup using blockchain.info
                                    print("vout not in rec")
                                    voutInfo = self.blockchaininfo.getVoutAddress(jdata["vin"][a]["txid"])
                                    if voutInfo is None:
                                        print(
                                            "Path for looking up in vout of new transaction not found for transaction " + txId + ". Impossible to determine address")
                                        return None

                                    rec['vout'] = voutInfo

                                entry = None
                                value = None
                                for n in rec["vout"]:
                                    if "n" in n and n["n"] == jdata["vin"][a]["vout"]:
                                        if 'scriptPubKey' in n and 'address' in n["scriptPubKey"]:
                                            entry = n["scriptPubKey"]["address"]
                                            value = n["value"]
                                            break

                                if entry is None or value is None:
                                    print(
                                        "Could not find vout address in the recursive transaction: " + jdata["vin"][a][
                                            "txid"] + "(" + txId + ")")
                                    return None

                                jdata["vin"][a]["scriptSig"]["address"] = entry
                                jdata["vin"][a]["value"] = value

                for a in range(len(jdata["vout"])):
                    if 'scriptPubKey' not in jdata["vout"][a] or 'value' not in jdata["vout"][a] or 'address' not in \
                            jdata["vout"][a]["scriptPubKey"]:
                        if noChecks:
                            # This will be resolved by a single blockchain.info lookup for the parent transaction
                            return None

                        # Try to resolve the vout lookup using blockchain.info
                        print("Invalid transaction: " + txId)

                        voutInfo = self.blockchaininfo.getVoutAddress(txId)
                        if voutInfo is None:
                            print(
                                "Vout fix lookup returned none for transaction " + txId + ". Invalid transaction.")
                            return None

                        jdata['vout'] = voutInfo
                        break

                success = True
                content = orjson.dumps(jdata)

                break

            try:
                if not noChecks:
                    # Insert this content into the database
                    cursor.execute("EXECUTE insTxCache (%s, %s)", (txId, content.decode("utf-8")))
                    conn.commit()
            except Exception:
                conn.rollback()
                conn.commit()

        if success:
            return orjson.loads(content)
        else:
            return None

    # Function to find an address and cache the result in the database
    def findAddressOrCache(self, address, conn):
        # First, check if this entry is in the cache. If not, request it from the api and cache it
        cursor = conn.cursor()

        cursor.execute("EXECUTE selAdrCache ('%s')" % str(address))

        res = cursor.fetchall()
        success = False
        content = None

        if len(res) > 0:
            success = True
            content = res[0][0]
        else:
            # print("Cache miss for address " + address)

            # Request the content from the API and insert it into the database. Retry up to 10 times
            for i in range(10):
                # Query the bitcoin explorer api and update the row
                try:
                    response = requests.get("http://localhost:3002/api/address/" + address + "?limit=200000", timeout=7200)
                except Exception as e:
                    print("Exception caught, calling garbage collector")
                    gc.collect()
                    time.sleep(600)
                    continue

                if response.status_code != 200:
                    print("Error code " + str(
                        response.status_code) + " received while querying the bitcoinexplorer api. Address hash: " +
                          address + " retrying...")
                    time.sleep(30)
                    continue

                # Parse the json and verify that the data is valid
                jdata = orjson.loads(response.text)

                if 'txHistory' not in jdata or 'txids' not in jdata['txHistory']:
                    if not ('txHistory' in jdata and 'errors' in jdata['txHistory']):
                        print("txHistory or txids not found for address " + address)
                    return None

                if len(jdata['txHistory']['txids']) != jdata['txHistory']['txCount']:
                    print("Mismatch between txids (" + str(len(jdata['txHistory']['txids'])) + ") and txCount (" + str(
                        jdata['txHistory']['txCount']) + ") for address " + address)
                    return None

                success = True
                content = response.text

                try:
                    # Insert this content into the database
                    cursor.execute("EXECUTE insAdrCache (%s, %s)", (address, content))
                    conn.commit()
                except Exception as e:
                    print("Address exception")
                    conn.rollback()
                    conn.commit()

                break

        if success:
            return orjson.loads(content)
        else:
            return None

    # Stage 0: from known transaction hashes to victim addresses
    def enrichVictimTransactionsThread(self, queue, conn):
        # Loop through all transactions and query their source address
        while True:
            try:
                transaction = queue.get(timeout=5)
            except Empty:
                return
            else:
                cursor = conn.cursor()

                content = self.findTransactionOrCache(transaction[1], conn)

                if content is None:
                    print("Empty content returned for transaction: " + transaction[1])
                    continue

                for a in range(len(content["vin"])):
                    cursor.execute("EXECUTE insertaddress (%s, %s, %s)",
                                   (transaction[0], str(content["vin"][a]["scriptSig"]["address"]),
                                    content["vin"][a]["value"]))

                conn.commit()

                queue.task_done()

    def collectVictimSources(self):
        transactions = self.queryVictimTransactions()
        print("Found " + str(len(transactions)) + " transactions to enrich with source wallets")

        queue = Queue(maxsize=len(transactions))

        for i in range(len(transactions)):
            queue.put(transactions[i])

        threads = []
        for t in range(self.threads):
            db = Database()
            conn = db.getConnection()

            cursor = conn.cursor()

            cursor.execute("PREPARE insertaddress AS "
                           "INSERT INTO \"VictimAddresses\" (\"TransactionId\", \"Address\", \"Amount\") VALUES ($1, $2, $3);")

            curThread = Thread(
                target=self.enrichVictimTransactionsThread,
                args=(queue, conn,),
                daemon=True
            )
            curThread.start()
            threads.append(curThread)

        for t in range(len(threads)):
            threads[t].join()
            # print("Thread " + str(t) + " finished.")

        print("All threads finished")

        if not queue.empty():
            print("Queue did not finish properly, please manually check for issues")
            exit(2)

        self.conn.commit()
        cursor = self.conn.cursor()
        cursor.close()

    def determineBlockOrder(self, block, txId):
        for i in range(len(block["tx"])):
            if block["tx"][i] == txId:
                return i

        return -1

    def failVA(self, address, conn):
        cursor = conn.cursor()
        cursor.execute("EXECUTE failVA (%s)", (address,))
        conn.commit()

    def gatherTransactionsFromVictimsThread(self, queue, conn):
        while True:
            try:
                entry = queue.get(timeout=5)
            except Empty:
                return
            else:
                cursor = conn.cursor()

                transaction = self.findTransactionOrCache(entry[1], conn)

                if transaction is None:
                    print("Empty transaction returned: " + entry[1] + ". Address: " + entry[0])
                    self.failVA(entry[0], conn)
                    continue

                if "time" not in transaction:
                    print("No time key found in transaction " + entry[1] + ". Address: " + entry[0])
                    self.failVA(entry[0], conn)
                    continue

                # Find the associated block to find the height of that block, for sorting later
                block = self.findBlockOrCache(transaction["blockhash"], conn)

                if block is None:
                    print("Empty block returned: " + transaction["blockhash"] + " (transaction: " + entry[1] + ", address: " + entry[0] + ")")
                    self.failVA(entry[0], conn)
                    continue

                blockOrder = self.determineBlockOrder(block, entry[1])
                if blockOrder < 0:
                    print("Invalid block order for transaction: " + entry[1])

                isDeposit = False

                # First, determine whether this is a transaction into the address or out of the address
                for i in range(len(transaction["vout"])):
                    if transaction["vout"][i]["scriptPubKey"]["address"] == entry[0]:
                        isDeposit = True
                        break

                for i in range(len(transaction["vin"])):
                    if transaction["vin"][i]["scriptSig"]["address"] == entry[0]:
                        isDeposit = None if isDeposit else False
                        break

                # Insert this transaction in the database as a deposit transaction
                if isDeposit is None:
                    for a in range(len(transaction['vin'])):
                        cursor.execute("EXECUTE insertdeposit (%s, %s, %s, %s, %s, %s, %s, %s)",
                                       (entry[0], transaction['vin'][a]['value'], transaction["time"], entry[1], False, transaction['vin'][a]['scriptSig']['address'], block["height"], blockOrder))

                    isDeposit = True

                for a in range(len(transaction['vout' if isDeposit else 'vin'])):
                    cursor.execute("EXECUTE insertdeposit (%s, %s, %s, %s, %s, %s, %s, %s)",
                                   (entry[0], transaction['vout' if isDeposit else 'vin'][a]['value'], transaction["time"], entry[1], isDeposit, transaction['vout' if isDeposit else 'vin'][a]['scriptPubKey' if isDeposit else 'scriptSig']['address'], block["height"], blockOrder))
                conn.commit()
                queue.task_done()

    def addAllTransactionsToQueue(self, addressQueue, transactionQueue, conn):
        while True:
            try:
                addressEntry = addressQueue.get(timeout=5)
            except Empty:
                return
            else:
                address = self.findAddressOrCache(addressEntry[0], conn)

                if address is None:
                    print("Empty content returned for address (victims): " + addressEntry[0])

                    self.failVA(addressEntry[0], conn)

                    addressQueue.task_done()
                    continue

                # TODO: move this to the configuration file
                if len(address["txHistory"]["txids"]) <= 100:
                    for t in range(len(address["txHistory"]["txids"])):
                        transactionQueue.put((addressEntry[0], address["txHistory"]["txids"][t]))

                addressQueue.task_done()

    def queueVictimAddressTransactions(self):
        addresses = self.queryVictimAddressess()
        addressQueue = Queue()

        queue = Queue()

        dbConnections = []

        threads = []
        for i in range(len(addresses)):
            addressQueue.put(addresses[i])

        for i in range(self.threads):
            db = Database()
            conn = db.getConnection()

            dbConnections.append(conn)
            curThread = Thread(
                target=self.addAllTransactionsToQueue,
                args=(addressQueue, queue, conn,),
                daemon=True
            )
            curThread.start()
            threads.append(curThread)

        for t in range(len(threads)):
            threads[t].join()
            # print("Thread " + str(t) + " finished.")

        print("Found " + str(queue.qsize()) + " victim transactions")

        return (dbConnections, queue)

    def gatherTransactionsFromVictimAddresses(self, dbConnections, queue):
        threads = []
        for t in range(self.threads):
            cursor = dbConnections[t].cursor()

            cursor.execute("PREPARE insertdeposit AS "
                           "INSERT INTO \"DepositTransactions\" (\"VictimAddress\", \"Amount\", \"Time\", \"TransactionHash\", \"IsDeposit\", \"Address\", \"Blockheight\", \"Blockorder\") VALUES ($1, $2, $3, $4, $5, $6, $7, $8);")

            curThread = Thread(
                target=self.gatherTransactionsFromVictimsThread,
                args=(queue, dbConnections[t],),
                daemon=True
            )
            curThread.start()
            threads.append(curThread)

        for t in range(len(threads)):
            threads[t].join()
            # print("Thread " + str(t) + " finished.")

        print("All threads finished")

        if not queue.empty():
            print("Queue did not finish properly, please manually check for issues")
            exit(2)

        self.conn.commit()
        cursor = self.conn.cursor()
        cursor.close()

    def gatherStakeholderTransactionsThread(self, queue, conn):
        while True:
            try:
                addressEntry = queue.get(timeout=5)
            except Empty:
                return
            else:
                cursor = conn.cursor()

                # Request the information for this address from the bitcoinexplorer api and cache it
                address = self.findAddressOrCache(addressEntry[0], conn)

                if address is None:
                    print("Empty content returned for address (stakeholders): " + addressEntry[0])

                    cursor.execute("EXECUTE failRD (%s)", (addressEntry[0],))
                    conn.commit()

                    queue.task_done()
                    continue

                # Now, do the same for every transaction that is made from or to this address
                succes = True

                for t in range(len(address["txHistory"]["txids"])):
                    transaction = self.findTransactionOrCache(address["txHistory"]["txids"][t], conn)

                    if transaction is None:
                        print("Empty transaction returned: " + str(address["txHistory"]["txids"][t]) + " (address: " +
                              addressEntry[0] + ")")
                        succes = False
                        continue

                    if "time" not in transaction:
                        print("No time key found in transaction " + str(
                            address["txHistory"]["txids"][t]) + " (address: " + str(addressEntry[0]) + ")")
                        succes = False
                        continue

                    # Figure out if this is a transaction out of the attackers wallet
                    outTransaction = False
                    for a in range(len(transaction["vin"])):
                        if transaction["vin"][a]["scriptSig"]["address"] == addressEntry[0]:
                            outTransaction = True
                            break

                    if outTransaction:
                        for a in range(len(transaction["vout"])):
                            if 'value' not in transaction["vout"][a]:
                                print("No value key is present in vout " + str(a) + " in transaction " +
                                      address["txHistory"]["txids"][t] + ". Address: " + addressEntry[0])
                                succes = False
                                continue

                            if 'scriptPubKey' not in transaction["vout"][a] or 'address' not in transaction["vout"][a][
                                "scriptPubKey"]:
                                print("No scriptPubKey or address tag in vout " + str(a) + " in transaction " +
                                      address["txHistory"]["txids"][t] + ". Address: " + addressEntry[0])
                                succes = False
                                continue

                            if addressEntry[0] is None:
                                print("NONE: " + addressEntry[0])

                            cursor.execute("EXECUTE insertstakeholder (%s, %s, %s, %s, %s, %s)", (
                                addressEntry[0], transaction["vout"][a]["scriptPubKey"]["address"],
                                transaction["vout"][a]["value"], transaction["time"], address["txHistory"]["txids"][t], datetime.fromtimestamp(transaction["time"]).strftime('%c')))

                if succes:
                    conn.commit()
                else:
                    conn.rollback()

                    cursor.execute("EXECUTE failRD (%s)", (addressEntry[0],))
                    conn.commit()

                queue.task_done()

    # Stage 2: gather all attacker wallets and transactions
    def gatherTransactionsFromAttackers(self):
        addresses = self.queryAttackerAddresses()
        print("Found " + str(len(addresses)) + " attacker addresses")

        queue = Queue(maxsize=len(addresses))

        for i in range(len(addresses)):
            queue.put(addresses[i])

        threads = []
        for t in range(self.threads):
            db = Database()
            conn = db.getConnection()

            cursor = conn.cursor()

            cursor.execute("PREPARE insertstakeholder AS "
                           "INSERT INTO \"StakeholderOutputs\" (\"AttackerAddress\", \"StakeholderAddress\", \"Amount\", \"Time\", \"TransactionHash\", \"ConvertedTime\") VALUES ($1, $2, $3, $4, $5, $6);")

            curThread = Thread(
                target=self.gatherStakeholderTransactionsThread,
                args=(queue, conn,),
                daemon=True
            )
            curThread.start()
            threads.append(curThread)

        for t in range(len(threads)):
            threads[t].join()
            # print("Thread " + str(t) + " finished.")

        print("All threads finished")

        if not queue.empty():
            print("Queue did not finish properly, please manually check for issues")
            exit(2)

        self.conn.commit()
        cursor = self.conn.cursor()
        cursor.close()
