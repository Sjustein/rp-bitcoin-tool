import psycopg2


class Database:
    conn = None
    cursor = None

    def __init__(self):
        self.conn = psycopg2.connect(database="DBNAME",
                                     host="DBHOST",
                                     user="DBUSER",
                                     password="DBPASS",
                                     port=5432)

        # Prepare a few prepared transactions
        cursor = self.getCursor()

        cursor.execute("PREPARE selTxCache AS SELECT \"Content\" FROM \"TransactionCache\" WHERE \"TXId\"=$1;")
        cursor.execute("PREPARE insTxCache AS INSERT INTO \"TransactionCache\" (\"TXId\", \"Content\") VALUES ($1, $2);")

        cursor.execute("PREPARE selAdrCache AS SELECT \"Content\" FROM \"AddressCache\" WHERE \"Address\"=$1;")
        cursor.execute("PREPARE insAdrCache AS INSERT INTO \"AddressCache\" (\"Address\", \"Content\") VALUES ($1, $2);")

        cursor.execute("PREPARE selBlockCache AS SELECT \"Content\" FROM \"BlockCache\" WHERE \"Blockhash\"=$1;")
        cursor.execute("PREPARE insBlockCache AS INSERT INTO \"BlockCache\" (\"Blockhash\", \"Content\") VALUES ($1, $2);")

        cursor.execute("PREPARE failRD AS UPDATE \"RansomData\" SET \"Failed\"=True WHERE \"Address\"=$1;")
        cursor.execute("PREPARE failVA AS UPDATE \"VictimAddresses\" SET \"Failed\"=True WHERE \"Address\"=$1;")

    def getCursor(self):
        self.cursor = self.conn.cursor()
        return self.cursor

    def getConnection(self):
        return self.conn

    def cleanData(self):
        print("Cleaning data from previous runs")
        self.getCursor()
        self.cursor.execute("TRUNCATE \"RansomData\" CASCADE;")
        self.cursor.execute("TRUNCATE \"RansomTransactions\";")
        self.cursor.execute("TRUNCATE \"DepositTransactions\";")
        self.cursor.execute("TRUNCATE \"StakeholderOutputs\";")
        self.cursor.execute("TRUNCATE \"VictimAddresses\";")
        self.cursor.execute("TRUNCATE \"RaasFamilies\";")
        self.conn.commit()
        self.cursor.close()
        print("Cleaning data finished")

    def cleanCache(self):
        print("Modify the script to clear the cache")
        return

        print("Cleaning cache from previous runs")
        self.getCursor()
        self.cursor.execute("TRUNCATE \"AddressCache\" CASCADE;")
        self.cursor.execute("TRUNCATE \"TransactionCache\";")
        self.conn.commit()
        self.cursor.close()
        print("Cleaning cache finished")

