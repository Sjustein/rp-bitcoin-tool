from datetime import datetime

import requests
import json

class Ransomwhere:
    conn = None

    def __init__(self, conn):
        self.conn = conn

    def importData(self):
        print("Importing ransomwhe.re transactions...")
        response = requests.get("https://api.ransomwhe.re/export")

        if response.status_code != 200:
            print("Error code " + str(response.status_code) + " received while querying the ransomwhe.re api.")
            exit(2)

        # Now parse the json data to insert it into the database
        jdata = json.loads(response.text)['result']

        cursor = self.conn.cursor()

        cursor.execute(
            "PREPARE apiinsert AS "
            "INSERT INTO \"RansomData\" (\"Address\", \"Balance\", \"BlockChain\", \"CreatedAt\", \"UpdatedAt\", \"Family\", \"BalanceUSD\") VALUES ($1, $2, $3, $4, $5, $6, $7) RETURNING \"Id\""
        )

        cursor.execute(
            "PREPARE transinsert AS "
            "INSERT INTO \"RansomTransactions\" (\"DataId\", \"Hash\", \"Time\", \"Amount\", \"AmountUSD\", \"ConvertedTime\") VALUES ($1, $2, $3, $4, $5, $6)"
        )

        for row in jdata:
            # First, insert a data row into the database. Then get that id and insert the transactions
            cursor.execute("EXECUTE apiinsert (%s, %s, %s, %s, %s, %s, %s)",
                            (row["address"], int(row["balance"]), row["blockchain"], row["createdAt"], row["updatedAt"], row["family"], row["balanceUSD"]))

            # Now insert the list of transactions into the transactions table
            lastId = cursor.fetchone()[0]

            for transaction in row["transactions"]:
                cursor.execute("EXECUTE transinsert (%s, %s, %s, %s, %s, %s)",
                               (lastId, transaction["hash"], transaction["time"], transaction["amount"], transaction["amountUSD"], datetime.fromtimestamp(transaction["time"]).strftime('%c')))



        self.conn.commit()
        cursor.close()

        print("Ransomwhe.re data imported")
