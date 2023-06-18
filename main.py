from API.BlockchainInfo import BlockchainInfo
from API.Ransomwhere import Ransomwhere
from API.Bitcoinexplorer import Bitcoinexplorer
from Database.Database import Database

from Processing import Processing
from Statistics.Attackers import Attackers
from Statistics.Victims import Victims

db = Database()
blockchaininfo = BlockchainInfo()
explorer = Bitcoinexplorer(db.getConnection(), blockchaininfo)
processing = Processing(db.getConnection(), explorer)

db.cleanData()
processing.validateTransactionCache()
print("Database connected and cleaned")

api = Ransomwhere(db.getConnection())
api.importData()

explorer.threads = 256
explorer.collectVictimSources()
print("Victim addresses enriched with address information")

prepData = explorer.queueVictimAddressTransactions()
explorer.gatherTransactionsFromVictimAddresses(prepData[0], prepData[1])
print("Victim addresses enriched with transactions")

explorer.gatherTransactionsFromAttackers()
processing.propegateVictimFailed()

if not processing.checkUniqueRansomAddresses():
    print(
        "Error: this script is designed to work with a list of unique ransom addresses, but there are multiple entries per address for some ransom addresses.")
    exit(4)

processing.fillTransactionCounts()
processing.fillAttackerBalanceLeft()
processing.fillStakeholderSplitPercentage()

print("Attacker statistics calculated")

attackerStats = Attackers(db.getConnection())
attackerStats.getSimpleCases()

victimStats = Victims(db.getConnection())
victimSCases = victimStats.getCases()

timeDiff = processing.timeDifRansomwhere(victimSCases)
# Enable this check if there may not be a time difference the blockchain time and the indicated ransomwhe.re time
if timeDiff:
    print("\nThere are ransom payment transactions that should match with an address transaction, but do not. The rest of the script might not work as expected, exiting.")
    exit(4)
else:
    print("\nThere are no mismatches between the ransomwhe.re and blockchain data.")

# Determine if the source address has been a bitcoin holder prior to the ransomware payment
processing.determineSourceIsHolder(victimSCases)
victimStats.printHolderStatistics()

# Determine the time between funds being deposited and ransom payment
processing.determineTimeDeltaDepositPayment(victimSCases)

print("\nScript finished, dataset is complete")
