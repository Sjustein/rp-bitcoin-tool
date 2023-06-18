class Victims:
    conn = None
    cursor = None

    def __init__(self, conn):
        self.conn = conn
        self.cursor = conn.cursor()

    def printHolderStatistics(self):
        self.cursor.execute(
            "SELECT SUM(CASE WHEN \"SourceIsHolder\" IS NOT NULL AND \"SourceIsHolder\" THEN 1 ELSE 0 END) AS Holders, "
            "SUM(CASE WHEN \"SourceIsHolder\" IS NOT NULL AND NOT \"SourceIsHolder\" THEN 1 ELSE 0 END) AS NonHolders, "
            "SUM(CASE WHEN \"SourceIsHolder\" IS NULL THEN 1 ELSE 0 END) AS NotDetermined FROM \"RansomTransactions\"")

        statistics = self.cursor.fetchall()
        total = statistics[0][0] + statistics[0][1] + statistics[0][2]

        print("\nVictim bitcoin holder statistics:")
        print("Total ransom payments: " + str(total))
        print("Ransom payments that could not determine whether the victim has owned bitcoin prior to paying: " + str(
            statistics[0][2]) + " ({:3.2f}%)".format((statistics[0][2] / total) * 100))
        print("Ransom payments with victims that owned bitcoin prior to paying: " + str(
            statistics[0][0]) + " ({:3.2f}%)".format((statistics[0][0] / total) * 100))
        print("Ransom payments with victims that did not own bitcoin prior to paying: " + str(
            statistics[0][1]) + " ({:3.2f}%)".format((statistics[0][1] / total) * 100))

    def getCases(self):
        dataQuery = "SELECT \"RansomTransactions\".\"Id\", \"RansomTransactions\".\"Time\", \"AmountUSD\", InTransactions, OutTransactions, \"RansomTransactions\".\"Hash\", VA.\"Address\" FROM \"RansomTransactions\"" \
                    "LEFT JOIN (" \
                    "   /* Select only one address per victim, if there has been only one payment (simple case) */" \
                    "   SELECT DISTINCT ON (\"TransactionId\") \"TransactionId\", \"Address\" FROM \"VictimAddresses\"" \
                    "   WHERE \"TransactionId\" IN (SELECT \"TransactionId\" FROM \"VictimAddresses\"" \
                    "                               GROUP BY \"TransactionId\" " \
                    "                               HAVING count(*) <= 1) " \
                    ") AS VA on \"RansomTransactions\".\"Id\" = VA.\"TransactionId\" " \
                    "LEFT JOIN ( " \
                    "    SELECT \"VictimAddress\", jsonb_pretty(json_agg(json_build_object( " \
                    "        'Amount', \"Amount\", " \
                    "        'Time', \"Time\", " \
                    "        'Hash', \"TransactionHash\"," \
                    "        'Address', \"Address\"," \
                    "        'Blockheight', \"Blockheight\"," \
                    "        'Blockorder', \"Blockorder\" " \
                    "        ))::jsonb) AS InTransactions FROM \"DepositTransactions\" " \
                    "    WHERE \"IsDeposit\" = TRUE " \
                    "    GROUP BY \"VictimAddress\" " \
                    ") AS INT ON VA.\"Address\" = INT.\"VictimAddress\" " \
                    "LEFT JOIN ( " \
                    "    SELECT \"VictimAddress\", jsonb_pretty(json_agg(json_build_object( " \
                    "        'Amount', \"Amount\", " \
                    "        'Time', \"Time\", " \
                    "        'Hash', \"TransactionHash\", " \
                    "        'Address', \"Address\", " \
                    "        'Blockheight', \"Blockheight\", " \
                    "        'Blockorder', \"Blockorder\" " \
                    "        ))::jsonb) AS OutTransactions FROM \"DepositTransactions\" " \
                    "    WHERE \"IsDeposit\" = FALSE " \
                    "    GROUP BY \"VictimAddress\" " \
                    ") AS OT ON VA.\"Address\" = OT.\"VictimAddress\" " \
                    "LEFT JOIN (SELECT \"TransactionId\", COUNT(*) AS InputAddresses FROM \"VictimAddresses\" " \
                    "                               GROUP BY \"TransactionId\") AS IA ON VA.\"TransactionId\" = IA.\"TransactionId\" " \
                    "WHERE \"RansomTransactions\".\"DataId\" NOT IN (SELECT DISTINCT \"Id\" FROM \"RansomData\" WHERE \"FailedVictims\"=TRUE)"

        self.cursor.execute(
            "SELECT SUM(CASE WHEN InTransactions IS NULL THEN 0 ELSE 1 END) AS SimpleCase, SUM(CASE WHEN InTransactions IS NULL THEN 1 ELSE 0 END) AS ExtendedCase "
            "FROM (" + dataQuery + ") AS DAT")

        statistics = self.cursor.fetchall()

        self.cursor.execute(
            "SELECT COUNT(*) FROM \"RansomTransactions\" WHERE \"DataId\" IN (SELECT DISTINCT \"Id\" FROM \"RansomData\" WHERE \"FailedVictims\"=True);")
        failed = self.cursor.fetchall()[0][0]

        self.cursor.execute("SELECT COUNT(*) FROM \"RansomTransactions\";")
        total = self.cursor.fetchall()[0][0]

        print("\nVictim statistics:")
        print("Total payment transactions: " + str(total))
        print("Failed imports (most likely too many transactions in address): " + str(failed) + " ({:3.2f}%)".format(
            (failed / total) * 100))
        print("Simple case payments: " + str(statistics[0][0]) + " ({:3.2f}%)".format((statistics[0][0] / total) * 100))
        print(
            "Extended case payments: " + str(statistics[0][1]) + " ({:3.2f}%)".format((statistics[0][1] / total) * 100))

        # Print RaaS statistics
        self.cursor.execute(
            "SELECT SUM(CASE WHEN \"RaasFamilies\".\"Raas\" IS NULL THEN 1 ELSE 0 END) AS NoRaas, SUM(CASE WHEN \"RaasFamilies\".\"Raas\" IS NULL THEN 0 ELSE 1 END) AS Raas FROM \"RansomTransactions\""
            "LEFT JOIN \"RansomData\" ON \"RansomTransactions\".\"DataId\" = \"RansomData\".\"Id\""
            "LEFT JOIN \"RaasFamilies\" ON \"RansomData\".\"Family\" = \"RaasFamilies\".\"Family\"")
        raasData = self.cursor.fetchall()[0]

        self.cursor.execute(
            "SELECT SUM(CASE WHEN \"Raas\" = True THEN 1 ELSE 0 END) AS RaaS, SUM(CASE WHEN \"Raas\" = True THEN 0 ELSE 1 END) AS NonRaaS FROM \"RansomTransactions\" "
            "LEFT JOIN \"RansomData\" ON \"RansomTransactions\".\"DataId\" = \"RansomData\".\"Id\" "
            "LEFT JOIN \"RaasFamilies\" ON \"RansomData\".\"Family\" = \"RaasFamilies\".\"Family\" ")
        raasSCStats = self.cursor.fetchall()[0]

        self.cursor.execute(
            "SELECT SUM(CASE WHEN \"Raas\" = True THEN 1 ELSE 0 END) AS RaaS, SUM(CASE WHEN \"Raas\" = True THEN 0 ELSE 1 END) AS NonRaaS FROM \"RansomTransactions\" "
            "LEFT JOIN \"RansomData\" ON \"RansomTransactions\".\"DataId\" = \"RansomData\".\"Id\" "
            "LEFT JOIN \"RaasFamilies\" ON \"RansomData\".\"Family\" = \"RaasFamilies\".\"Family\" "
            "WHERE \"FailedVictims\" = FALSE AND \"SourceIsHolder\" IS NOT NULL;")
        raasStats = self.cursor.fetchall()[0]

        print("----------- Raas statistics")
        print("Ransom cases with RaaS data: " + str(raasData[1]) + " victim payments ({:3.2f}%)".format(
            (raasData[1] / total) * 100))
        print("Ransom cases without RaaS data: " + str(raasData[0]) + " victim payments ({:3.2f}%)".format(
            (raasData[0] / total) * 100))

        # SC = Simple Case
        print("SC|ALL] Amount of RaaS cases: " + str(raasSCStats[0]) + "|" + str(raasStats[0]) + " victim payments")
        print("SC|ALL] Amount of Non-RaaS cases: " + str(raasSCStats[1]) + "|" + str(raasStats[1]) + " victim payments")

        self.cursor.execute(dataQuery)
        return self.cursor.fetchall()
