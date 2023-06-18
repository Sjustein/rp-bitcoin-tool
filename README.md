# rp-tool-python
Note: this is an initial and work in progress version of the tool. The tool is far from polished (see ROADMAP.md)

## System requirements
### Minimum specs
- 1 TB HDD
- 16GB of RAM
- A CPU with 8 threads, less with lower concurrency

### Recommended specs
- 1 TB SSD
- 32GB of RAM
- A CPU with 16 threads

### Validation system
- 1 TB NVME SSD
- 64GB of RAM
- A CPU with 32 threads

It should be possible and easier to deploy the dependencies and software stack on linux, but this has not been tested yet.
Instead of that, a windows installation with WSL-2 (Windows Subsystem for Linux 2) was used.

## Setup dependencies
### Setup bitcoin core and bitcoin-cli
- Setup bitcoin core using the official bitcoin website: https://bitcoin.org/en/bitcoin-core/
- Make sure the bitcoin-cli is also availablem after installing the tool. On windows, this tool is automatically installed with bitcoin-core.
- Synchronise bitcoin-core with the blockchain before using this tool or proceding with the setup of the other tools.
- **IMPORTANT:** Create a wallet in bitcoin core. Without a wallet other tools might not work with bitcoin-core.

#### Recommended setttings for bitcoin-core
- Ensure to enable the RPC service in order to be able to communicate with the other tools.
- Threads for script verification: 15 (the maximum)

**Settings for bitcoin.conf**
- Create a file called bitcoin.conf in the working directory chosen on setup. 

**Recommended settings for bitcoin.conf:** 
assumevalid=0 # Required for other tools to properly work with bitcoin core \
dbcache=24000 # Change this based on the specifications of your system \
datadir= # Some file on a large enough disk (>500GB) \
rpcallowip=0.0.0.0/0 # The ip addresses to allow incoming connections from \
rpcbind=0.0.0.0 # This will listen to all incoming requests. If possible, lock this down to the local PC or subnet \
rpcconnect=0.0.0.0 \
rest=1 # Enable the rest server, required for other tools \
server=1 # Enable the server functionality of bittcoin-core \
txindex=1 # Keep a transaction index, helps speed up other tools \
mempoolfullrbf=1 # Required for proper working of the electrum server \
prune=0 # Don't prune transactions. This will help speed up the electrum server. Only enable this if there is really no disk space left, but this will have a performance impact on the electrum server \

\# Enable deprecated RPC endpoints for use with the electrum and bitcoinexplorer server. \
deprecatedrpc=accounts \
deprecatedrpc=signrawtransaction \
deprecatedrpc=addwitnessaddress \
deprecatedrpc=validateaddress \
maxconnections=1014 # Prevent the bitcoin core server to be the bottleneck in terms of connections

### Setup electrum server
Using development, the electrs tool was used as electrum server. The electrum server is required for enabling the address lookup functionality in the bitcoin explorer api.
The electrum source code can be found in its github repository: https://github.com/romanz/electrs. As there are no officially built binaries, it is recommended to use the installation from source guide.
Although deploying the tool on a different machine is possible, if the machines can connect to each other over the network.
It is recommended to host all tools on the same machine, for reducing network latency bottlenecks.

During development, WSL-2 was used, with an Ubuntu 22.04 installation: https://ubuntu.com/tutorials/install-ubuntu-on-wsl2-on-windows-11-with-gui-support#1-overview
Following the guide for GUI packages is not neccessary, as electrs is a CLI tool.

To properly connect to the WSL instance, the WSL firewall should allow connections to electrs and bitcoin-core.
Unless otherwise configured, the port for electrs is 50001 and for bitcoin core, 8332 and 8333 are used for incoming RPC connections and P2P connections respectively.

**Note:** electrs will only start building its cache when bitcoin-core is fully synchronised with the blockchain.
It can be started before to check whether a proper connection can be made to the bitcoin core server.
If done correctly, electrs will periodically print a message telling you how much transactions should still be synced in bitcoin-core.
When bitcoin-core is fully synchronised, electrs will start building its cache automatically. 

#### Recommended settings for electrs
When electrs is installed, in the .electrs folder in the home directory of the current user will contain a file called config.toml.
If not, create the directory and the file. More information can be found here: https://github.com/romanz/electrs/blob/master/doc/config.md

cookie_file = "/mnt/x/.cookie" # Use the bitcoin-cli cookie system to authenticate with bitcoin-core \
daemon_rpc_addr = "ip address:8332" # The port only needs to be changed when customised in the bitcoin-core settings \
daemon_p2p_addr = "ip address:8333" \
daemon_dir = "/mnt/d/RP" # The directory set as the daemon directory for bitcoin-core \
db_dir = "PATH_TO_ELECTRS_CACHE" # The directory where electrs keeps its cache. 50 - 100GB of disk space should be free \
network = "bitcoin" # Set the bitcoin network to mainnet, which should be set if using this tool on real world transactions \
electrum_rpc_addr = "0.0.0.0:50001" # Accept connections from any ip address. Ensure to properly install a firewall to only allow connections from bitcoin explorer \
log_filters = "INFO"

### Setup bitcoin explorer
**IMPORTANT:** Bitcoin explorer version 3.4.0 (API version 2.0) is recommended, as it pre-parses input addresses for transactions, drastically decreasing the amount of API calls the script will make.
Using this version will thus significantly speed up the initial import process.
Bitcoin explorer provides an easy to use API, combining the bitcoin-core client and electrum client to provide an easily accessible API.
The source code can be found in the github repository: https://github.com/janoside/btc-rpc-explorer.
It is recommended to use the installation instructions using npm to install bitcoin explorer. 

### Setup the postgresql database
Setup a postgresql server, preferably on the same machine as the script is run (preferably, the entire software stack is hosted on the same machine).\
Create a database and user for the script:
- CREATE USER rp_admin WITH PASSWORD '<upass>';
- CREATE DATABASE rp_data;
- GRANT ALL PRIVILEGES ON DATABASE "rp_data" to rp_admin;

After that, create the database schema with the createschema.sql file.

Please update the user, database and host configuration in Database/Database.py.
**Note:** after testing, the database, including data and cache used between 50 and 70GB of disk space. Increasing the limits set in the code and in the electrum server will increase this usage up till 500+GB's.

### Time required
- Synchronising the bitcoin blockchain took around 8-10 hours.
- Building the electrs cache took around 4-5 hours.
- First run of the script: 12 - 36 hours (limited to 50 transactions per address).
- Subsequent runs using cache: < 60 minutes (depending on the limited transactions and postgresql server speed and latency).

All tools must be fully synchronised and cannot sync in parallel.

### Startup tools
- On windows, bitcoin-core can automatically start the server when it is started and will automatically use the configuration file in the specified directory. If not using the bitcoin-core gui tool, ensure to use the created configuration file.
- Electrs should be set to only handle requests for addresses with 50 transactions or less, unless your purpose requires larger addresses to be processed as well. As electrs can take a lot of time to gather the entire address, especially with higher transaction counts, the amount of threads during the queueVictimAddressTransactions() function should be lowered accordingly, as to not 'stall' electrs or bitcoin explorer. 
  - This limitation can be enforced by starting electrs with the following command: electrs --index-batch-size=512 --index-lookup-limit=50 --ignore-mempool. Memory pool transactions are not needed, as the data in the ransomwhe.re dataset is at least 90 days old.
  - Make sure electrs can find the configuration file and using the configuration provided by it.
- Start btc-rpc-explorer in the directory that contains its environment file and provide the path to the bitcoin core cookie file to authenticate with bitcoin core
  - Use the following command to achieve this: btc-rpc-explorer -c C:\PATH\TO\.cookie

### The workings of this tool
All transactions and addresses will be cached. The bitcoin explorer instance is always used first and it is possible to use a publicly hosted instance.
This script will make a lot of highly parallelized requests, so this is not recommended.
The bitcoin.info API is used as a backup API, as not all transactions will be properly interpreted by bitcoin explorer.
The script will adhere to the rate limits provided by bitcoin.info, which might limit how fast lookups can be done if a lot of failed lookups stack up.
- On startup, the cache will be validated and invalid entries will be purged. No entries should be purged if the tool is working as it should, checks are in place to only cache valid transactions, addresses and blocks.
- The data tables will be cleared on startup by default. The first run will take between 24 and 48 hours to fill the cache and data tables, but after the first run, the program should finish in under 60 minutes, using its cache. However, the actual speed depends on your hardware and the limits set in the code and in the electrum server.
- After that, the ransomwhe.re dataset will be downloaded and inserted in the 'RansomData' and 'RansomTransactions' tables.
- This data will be used to fill the 'VictimAddresses' table, containing a list of addresses, related ransom payment transaction id and addition infered metadata (inserted later in the script).
- After that, all transactions in victim addresses that have less than 50 transactions are looked up and cached. All found transactions are stored in the 'DepositTransactions' table.
- Then, all addresses and transactions from attacker wallets are looked up, cached and stored in the 'StakeholderOutputs' table.
- As a final step, additional infered data is added to these tabled. This step can be expanded upon easily by updating the script and updating the database.

**Data accuracy:** If any transactions fail to properly import, their id will be printed in the console. Nothing should be printed for the data to be reliable.
The script is tested to use the blockchaininfo API as a fallback and no transactions should fail to import.
Every failed address or transaction will be printed to the standard output as well. Addresses are expected not to properly import if they contain more than the amount of transactions set in the code and the electrum server.
