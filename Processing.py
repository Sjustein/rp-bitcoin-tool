import orjson
from decimal import *

class Processing:
    conn = None
    cursor = None
    explorer = None

    def __init__(self, conn, bitcoinexplorer):
        self.conn = conn
        self.cursor = conn.cursor()
        self.explorer = bitcoinexplorer

    def propegateVictimFailed(self):
        self.cursor.execute("UPDATE \"RansomData\" SET \"FailedVictims\"=False WHERE 1=1; "
                            "UPDATE \"RansomData\" SET \"FailedVictims\"=True WHERE \"Id\" IN ( "
                            "SELECT DISTINCT \"DataId\" FROM \"RansomTransactions\" WHERE \"Id\" IN ( "
                            "SELECT DISTINCT \"TransactionId\" FROM \"VictimAddresses\" WHERE \"Failed\"=True));")
        self.conn.commit()

    def determineTimeDeltaDepositPayment(self, victimCases):
        self.cursor.execute(
            "PREPARE updateDelta AS UPDATE \"RansomTransactions\" SET \"DepositPaymentDelta\"=$1 WHERE \"Id\"=$2;")

        for i in range(len(victimCases)):
            if victimCases[i][3] is None and victimCases[i][4] is None:
                # This is not an entry in the simple case
                continue

            OutTransactions = orjson.loads(victimCases[i][4])
            InTransactions = orjson.loads(victimCases[i][3])
            paymentTime = self.determinePaymentTime(OutTransactions, victimCases[i][5])
            paymentBlockheight = self.determinePaymentBlockheight(OutTransactions, victimCases[i][5])
            allTransactions = []

            for entry in OutTransactions:
                entry["Amount"] = Decimal(str(entry["Amount"]))*Decimal(-1)
                allTransactions.append(entry)

            for entry in InTransactions:
                entry["Amount"] = Decimal(str(entry["Amount"]))
                allTransactions.append(entry)

            allTransactions = sorted(allTransactions, key=lambda val: (val["Blockheight"], val["Blockorder"]), reverse=True)

            balance = None
            depositTime = 0

            # The array is sorted to list later transactions first, so balance will start out negative, as the ransom payment is the first expense done according to the ordering
            # Then, with more deposit transactions, eventually the balance will become positive. This is the point that is determined to be the deposit transaction
            for transaction in allTransactions:
                if transaction["Blockheight"] <= paymentBlockheight and transaction["Address"] == victimCases[i][6]:
                    if balance is None:
                        balance = Decimal(0)
                    balance += transaction["Amount"]

                if balance is not None and balance >= 0:
                    depositTime = transaction["Time"]
                    break

            if balance is None:
                print("Deposit delta could not be calculated for: " + str(victimCases[i][0]))
                continue

            if balance < 0:
                print("Payment time could not be determined for transaction: " + str(victimCases[i][0]))
                continue

            delta = paymentTime - depositTime

            self.cursor.execute("EXECUTE updateDelta (%s, %s)", (delta, victimCases[i][0]))

        self.conn.commit()

    def determinePaymentTime(self, outTransactions, hash):
        for i in range(len(outTransactions)):
            if outTransactions[i]["Hash"] == hash:
                return outTransactions[i]["Time"]

        return None

    def determinePaymentBlockheight(self, outTransactions, hash):
        for i in range(len(outTransactions)):
            if outTransactions[i]["Hash"] == hash:
                return outTransactions[i]["Blockheight"]

        return None

    def determineSourceIsHolder(self, victimCases):
        self.cursor.execute(
            "PREPARE updateSourceIsHolder AS UPDATE \"RansomTransactions\" SET \"SourceIsHolder\"=$1 WHERE \"Id\"=$2;")

        for i in range(len(victimCases)):
            if victimCases[i][3] is None and victimCases[i][4] is None:
                # This is not an entry in the simple case
                continue

            isHolder = False

            # A new address would only have at most a small transaction to test before the ransom payment
            OutTransactions = orjson.loads(victimCases[i][4])
            InTransactions = orjson.loads(victimCases[i][3])

            paymentTime = self.determinePaymentTime(OutTransactions, victimCases[i][5])
            paymentBlockheight = self.determinePaymentBlockheight(OutTransactions, victimCases[i][5])

            OTBeforePayment = []
            ITBeforePayment = []

            for a in range(len(OutTransactions)):
                if OutTransactions[a]["Blockheight"] < paymentBlockheight:
                    if OutTransactions[a]["Hash"] not in OTBeforePayment:
                        OTBeforePayment.append(OutTransactions[a]["Hash"])

            for a in range(len(InTransactions)):
                if InTransactions[a]["Blockheight"] < paymentBlockheight:
                    if InTransactions[a]["Hash"] not in ITBeforePayment:
                        ITBeforePayment.append(InTransactions[a]["Hash"])

            # There are more than 1 payment in and out of the address, because the user might want to test deposit transactions and ransom payment transactions
            if len(OTBeforePayment) > 1:
                isHolder = True
            if len(ITBeforePayment) > 1:
                isHolder = True

            # If the first transaction is made longer than a month before the ransom payment, this address also held bitcoin before the ransom payment
            minTimeIn = min(InTransactions, key=lambda val: val["Blockheight"])["Time"]
            minTimeOut = min(OutTransactions, key=lambda val: val["Blockheight"])["Time"]
            minTime = min(minTimeIn, minTimeOut)

            # A month is: 60 seconds * 60 minutes * 24 hours * 31 days = 2678400
            if abs(paymentTime - minTime) > 2678400:
                isHolder = True

            self.cursor.execute("EXECUTE updateSourceIsHolder (%s, %s)", (isHolder, victimCases[i][0]))

        self.conn.commit()

    def timeDifRansomwhere(self, victimCases):
        misMatches = False

        for i in range(len(victimCases)):
            if victimCases[i][3] is None and victimCases[i][4] is None:
                continue

            case = victimCases[i]
            OutTransactions = orjson.loads(victimCases[i][4])

            match = False
            for a in range(len(OutTransactions)):
                if victimCases[i][5] == OutTransactions[a]["Hash"]:
                    match = True

            if not match:
                print("Mismatch between the ransomwhe.re and blockchain transaction hashes: " + str(
                    victimCases[i][0]))
                misMatches = True

        return misMatches

    def checkUniqueRansomAddresses(self):
        self.cursor.execute(
            "SELECT COUNT(*) AS Addresses, count(DISTINCT \"Address\") AS UniqueAddresses FROM \"RansomData\";")
        res = self.cursor.fetchall()

        return res[0][0] == res[0][1]

    def validateTransactionCache(self):
        self.cursor.execute("PREPARE delCache AS DELETE FROM \"TransactionCache\" WHERE \"TXId\"=$1;")

        with self.conn.cursor(name="selectTransactionCache", withhold=True) as selectCursor:
            selectCursor.itersize = 10000
            selectCursor.execute("SELECT \"TXId\", \"Content\" FROM \"TransactionCache\";")

            print("Transaction cache loaded to be purged of invalid entries")

            for entry in selectCursor:
                succes = True
                jdata = orjson.loads(entry[1])

                if 'vin' not in jdata or 'vout' not in jdata or 'blockhash' not in jdata:
                    succes = False

                if succes:
                    for a in range(len(jdata["vin"])):
                        if 'scriptSig' not in jdata["vin"][a] or 'address' not in jdata["vin"][a]["scriptSig"]:
                            succes = False
                            break

                    for a in range(len(jdata["vout"])):
                        if 'scriptPubKey' not in jdata["vout"][a] or 'address' not in jdata["vout"][a][
                            "scriptPubKey"] or 'value' not in jdata["vout"][a]:
                            succes = False
                            break

                        if jdata["vout"][a]["scriptPubKey"]["address"] is None:
                            succes = False
                            break

                if not succes:
                    print("Transaction " + entry[0] + " did not pass the test")
                    self.cursor.execute("EXECUTE delCache (%s)", (entry[0],))
                    self.conn.commit()

    def fillTransactionCounts(self):
        # Find all addresses in the cache
        self.cursor.execute("SELECT \"Address\", \"Content\" FROM \"AddressCache\" WHERE \"TXCount\" IS NULL;")
        addresses = self.cursor.fetchall()

        self.cursor.execute("PREPARE updateTxIds AS "
                            "UPDATE \"AddressCache\" SET \"TXCount\"=$1 WHERE \"Address\"=$2;")

        for i in range(len(addresses)):
            address = addresses[i]

            data = orjson.loads(address[1])

            if 'txHistory' in data and 'txCount' in data['txHistory']:
                self.cursor.execute("EXECUTE updateTxIds (%s, %s)", (data['txHistory']['txCount'], address[0]))

        self.conn.commit()

    def fillAttackerBalanceLeft(self):
        self.cursor.execute(
            "SELECT DISTINCT \"Address\" FROM \"RansomData\""
            "WHERE \"BalanceBTCAfterStakeholders\" IS NULL AND \"Failed\"=False "
            "AND \"Address\" IN (SELECT DISTINCT \"AttackerAddress\" FROM \"StakeholderOutputs\");")
        addresses = self.cursor.fetchall()

        self.cursor.execute("PREPARE updateBalanceLeft AS "
                            "UPDATE \"RansomData\" SET \"BalanceBTCAfterStakeholders\"=$1 WHERE \"Address\"=$2;")

        for i in range(len(addresses)):
            address = self.explorer.findAddressOrCache(addresses[i][0], self.conn)

            # This address has too many transactions to consider
            if address is None:
                continue

            if "txHistory" not in address or "balanceSat" not in address["txHistory"]:
                print("No balanceSat key is present for address " + addresses[i][0])
                continue

            self.cursor.execute("EXECUTE updateBalanceLeft (%s, %s)",
                                (round(address["txHistory"]["balanceSat"] / 100000000, 20), addresses[i][0]))

        self.conn.commit()

    def fillStakeholderSplitPercentage(self):
        self.cursor.execute(
            "SELECT \"Id\", \"Amount\", BalanceLeft + Subtotal AS Total FROM \"StakeholderOutputs\" AS SO "
            "LEFT JOIN (SELECT \"Address\", COALESCE(SUM(\"BalanceBTCAfterStakeholders\"), 0) AS BalanceLeft FROM \"RansomData\" "
            "                   GROUP BY \"Address\" "
            "                   HAVING COUNT(*) = 1) AS RD ON SO.\"AttackerAddress\" = RD.\"Address\" "
            "LEFT JOIN (SELECT \"AttackerAddress\", COALESCE(SUM(\"Amount\"), 0) AS Subtotal FROM \"StakeholderOutputs\" "
            "                   GROUP BY \"AttackerAddress\") AS ST ON SO.\"AttackerAddress\" = ST.\"AttackerAddress\" ")

        entries = self.cursor.fetchall()

        self.cursor.execute("PREPARE updatePercentage AS "
                            "UPDATE \"StakeholderOutputs\" SET \"PercentageSplit\"=$1 WHERE \"Id\"=$2;")

        for i in range(len(entries)):
            entry = entries[i]

            self.cursor.execute("EXECUTE updatePercentage (%s, %s)", (entry[1] / entry[2], entry[0]))

        self.conn.commit()

        # Verify that all percentages add up to 1, except entries that have balance left
        self.cursor.execute("SELECT COUNT(*) FROM ( "
                            "SELECT \"AttackerAddress\", SUM(\"PercentageSplit\") FROM \"StakeholderOutputs\" "
                            "WHERE \"AttackerAddress\" NOT IN (SELECT DISTINCT \"Address\" FROM \"RansomData\" WHERE \"BalanceBTCAfterStakeholders\" IS NOT NULL AND \"BalanceBTCAfterStakeholders\" <> 0) "
                            "GROUP BY \"AttackerAddress\" /* Script checks if attacker addresses are distinct */"
                            "HAVING SUM(\"PercentageSplit\") < 0.9999 OR SUM(\"PercentageSplit\") > 1.0001) AS t")

        notHundredPercent = self.cursor.fetchall()[0][0]

        if notHundredPercent != 0:
            print(str(notHundredPercent) + " ransom attacks do not add stakeholder outputs and balance left in the account to 100%. Exiting...")
            exit(6)

        # Verify that the amount left in the account is equal to the BalanceBTCLeftAfterStakeholders
        self.cursor.execute("SELECT \"Address\", \"BalanceBTCAfterStakeholders\" FROM \"RansomData\""
                            "WHERE \"BalanceBTCAfterStakeholders\" IS NOT NULL AND \"BalanceBTCAfterStakeholders\" <> 0;")

        balanceLeft = self.cursor.fetchall()

        for row in balanceLeft:
            # Verify that the amount left according to the internal calculations is equal to the actual amount left in the address
            addr = self.explorer.findAddressOrCache(row[0], self.conn)

            balanceBTC = Decimal(str(addr["txHistory"]["balanceSat"]/100000000))
            if balanceBTC != row[1]:
                print("Calculated amount left in the address is not equal to the actual amount left in the address: " + row[0] + ". Exiting...")
                exit(7)
