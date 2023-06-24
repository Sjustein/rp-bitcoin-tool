class Attackers:
    conn = None

    def __init__(self, conn):
        self.conn = conn

    # Function to get all simple case attacker wallets. This means
    # - Only one victim for this wallet
    # - The amount of transactions made to and from this wallet is 2, 1 victim payment and 1 stakeholder split
    def getSimpleCases(self):
        cursor = self.conn.cursor()

        # Find all addresses that only occur once in ransomwhe.re
        cursor.execute(
            "SELECT DISTINCT \"RansomData\".\"Address\", COALESCE(SUM(OutTransactionCount), 0) AS OutTransactions, COALESCE(SUM(ITC.InTransactionCount), 0) AS InTransactions FROM \"RansomData\" "
            "LEFT JOIN (SELECT \"AttackerAddress\", count(DISTINCT \"TransactionHash\") AS OutTransactionCount FROM \"StakeholderOutputs\" GROUP BY \"AttackerAddress\") AS OTC ON \"RansomData\".\"Address\" = OTC.\"AttackerAddress\" "
            "LEFT JOIN (SELECT \"DataId\", COUNT(DISTINCT \"Hash\") AS InTransactionCount FROM \"RansomTransactions\" GROUP BY \"DataId\") AS ITC ON \"RansomData\".\"Id\" = ITC.\"DataId\" "
            "WHERE \"Failed\"=False "
            "GROUP BY \"RansomData\".\"Address\" "
            "HAVING count(*) = 1;")

        addresses = cursor.fetchall()

        cursor.execute("SELECT COUNT(*) FROM \"RansomData\" WHERE \"Failed\"=True;")
        failed = cursor.fetchall()[0][0]

        total = len(addresses) + failed
        notPaid = 0
        noCashOut = 0
        simpleCases = []

        for i in range(len(addresses)):
            # There are no outbound transactions, but there are inbound transactions
            if addresses[i][1] == 0 and addresses[i][2] > 0:
                noCashOut += 1
            # There are no inbound transactions
            elif addresses[i][2] == 0:
                notPaid += 1
            elif addresses[i][1] + addresses[i][2] == 2 and addresses[i][2] == 1:
                simpleCases.append(addresses[i])

        print("\nAttacker statistics:")
        print("Total cases: " + str(total))
        print("Failed imports (most likely too many transactions in address): " + str(failed))
        print("Ransom not cashed out in " + str(noCashOut) + " addresses ({:3.2f}%)".format((noCashOut / total) * 100))
        print("Ransom not paid in " + str(notPaid) + " addresses ({:3.2f}%)".format((notPaid / total) * 100))
        print(
            "Simple case: " + str(len(simpleCases)) + " addresses ({:3.2f}%)".format((len(simpleCases) / total) * 100))
        print("Extended case: " + str(total - noCashOut - notPaid - len(simpleCases) - failed) + " addresses ({:3.2f}%)".format(
            ((total - noCashOut - notPaid - len(simpleCases) - failed) / total) * 100))

        # Print RaaS statistics
        cursor.execute(
            "SELECT SUM(CASE WHEN \"RaasFamilies\".\"Raas\" IS NULL THEN 1 ELSE 0 END) AS NoRaas, SUM(CASE WHEN \"RaasFamilies\".\"Raas\" IS NULL THEN 0 ELSE 1 END) AS Raas FROM \"RansomData\""
            "LEFT JOIN \"RaasFamilies\" ON \"RansomData\".\"Family\" = \"RaasFamilies\".\"Family\"")
        raasData = cursor.fetchall()[0]

        cursor.execute(
            "SELECT SUM(CASE WHEN \"Raas\" = True THEN 1 ELSE 0 END) AS RaaS, SUM(CASE WHEN \"Raas\" = True THEN 0 ELSE 1 END) AS NonRaaS FROM \"RansomData\" "
            "LEFT JOIN \"RaasFamilies\" ON \"RansomData\".\"Family\" = \"RaasFamilies\".\"Family\";")
        raasStats = cursor.fetchall()[0]

        cursor.execute(
            "SELECT SUM(CASE WHEN \"Raas\" = True THEN 1 ELSE 0 END) AS NonRaaS, SUM(CASE WHEN \"Raas\" = True THEN 0 ELSE 1 END) AS RaaS FROM \"RansomData\" "
            "LEFT JOIN \"RaasFamilies\" ON \"RansomData\".\"Family\" = \"RaasFamilies\".\"Family\" "
            "LEFT JOIN ("
            "    SELECT DISTINCT \"RansomData\".\"Address\", COALESCE(SUM(OutTransactionCount), 0) AS OutTransactions, COALESCE(SUM(ITC.InTransactionCount), 0) AS InTransactions FROM \"RansomData\""
            "    LEFT JOIN (SELECT \"AttackerAddress\", count(DISTINCT \"TransactionHash\") AS OutTransactionCount FROM \"StakeholderOutputs\" GROUP BY \"AttackerAddress\") AS OTC ON \"RansomData\".\"Address\" = OTC.\"AttackerAddress\""
            "    LEFT JOIN (SELECT \"DataId\", COUNT(DISTINCT \"Hash\") AS InTransactionCount FROM \"RansomTransactions\" GROUP BY \"DataId\") AS ITC ON \"RansomData\".\"Id\" = ITC.\"DataId\""
            "    WHERE \"Failed\"=False"
            "    GROUP BY \"RansomData\".\"Address\""
            "    HAVING count(*) = 1) AS tStats ON \"RansomData\".\"Address\" = tStats.\"Address\" "
            "WHERE \"Failed\" = FALSE AND tStats.OutTransactions <> 0 AND NOT (tStats.OutTransactions = 0 AND tStats.OutTransactions > 0) AND tStats.OutTransactions + tStats.InTransactions = 2;")
        raasSCStats = cursor.fetchall()[0]

        print("----------- Raas statistics")
        print("Ransom cases with RaaS data: " + str(raasData[1]) + " addresses ({:3.2f}%)".format(
            (raasData[1] / total) * 100))
        print("Ransom cases without RaaS data: " + str(raasData[0]) + " addresses ({:3.2f}%)".format(
            (raasData[0] / total) * 100))

        # SC = Simple Case
        print("SC|ALL] Amount of RaaS cases: " + str(raasSCStats[0]) + "|" + str(raasStats[0]) + " addresses")
        print("SC|ALL] Amount of Non-RaaS cases: " + str(raasSCStats[1]) + "|" + str(raasStats[1]) +  " addresses")

        return simpleCases

    def printAddressReuse(self):
        print("SELECT \"DataId\", count(*) FROM \"RansomTransactions\" " \
              "GROUP BY \"DataId\"")
