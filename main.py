import warnings
warnings.filterwarnings("ignore", category=Warning)
import math, random, sys, ast, hashlib, threading, atexit, time, importlib, subprocess
def packageCheck(name):
    try: importlib.import_module(name)
    except ImportError:
        print(f"Installing {name}...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "--quiet", name])
packageCheck("coincurve")
packageCheck("requests")
packageCheck("certifi")
import os, termios, tty, select, multiprocessing, faulthandler, signal, api
faulthandler.register(signal.SIGUSR1)

from coincurve import PrivateKey, PublicKey
from collections import deque
#Colors: 31: red, 32 green, 33 yellow, 34 blue, 35 magenta, 36 cyan, 37 white
#todo: store chain in RAM rather than in a file
BLOCKS = "blocks.txt"
CONTACTS = "contactList.txt"
with open("version.txt", "r") as f:
    VERSION = f.read()
CONFIGS = []
with open("config.txt", "r") as f:
    data = f.readlines()
    for i in range(len(data)):
        CONFIGS.append(data[i].split("=")[1])

NETWORK_INFO = False
ID = [-1]
transactions = []
def getDifficulty(blockIndex: int) -> int:
    return int(2**getDifficultyBits(blockIndex))
def getDifficultyFromTs(tss: list[int]) -> float:
    gap = tss[1] - tss[0]
    TARGET = 300
    diff = (gap-TARGET)/TARGET
    diff = max(min(diff, 0.3), -0.3)
    return round(diff, 2)
def getDifficultyFromTs2(tss: list[int]) -> float:
    TARGET = 300
    avg = abs(tss[1]-tss[0])/5
    diff = (avg-TARGET)/TARGET
    diff = max(min(diff, 0.3), -0.3)
    return round(diff, 2)
def getDifficultyFromTs3(tss: list[int]) -> float:
    TARGET = 300
    avg = abs(tss[1]-tss[0])/25
    diff = math.log2(avg/TARGET)
    diff = max(min(diff, 0.5), -0.5)
    return round(diff, 2)
def getTs(block: str) -> int:
    header = block.strip().split(",", 1)[0]
    return int(header.split("|")[2])
def getDifficultyBits(blockIndex: int) -> float:
    tss = []
    with open(BLOCKS, "r") as f:
        blocks = f.readlines()[:blockIndex]
    for block in blocks:
        tss.append(getTs(block))
    net = 0
    for i in range(1, len(tss)):
        if i <= 155: net += getDifficultyFromTs([tss[i - 1], tss[i]])
        elif i <= 7680: net += getDifficultyFromTs2([tss[i - 5], tss[i]])
        else: net += getDifficultyFromTs3([tss[i - 25], tss[i]])
    return 230+net
def getBlockReward(blockIndex: int) -> int:
    if blockIndex < 5_000: return 10000
    if blockIndex < 15_000: return 5000
    if blockIndex < 35_000: return 2500
    if blockIndex < 75_000: return 1250
    if blockIndex < 155_000: return 625
    if blockIndex < 315_000: return 313
    if blockIndex < 635_000: return 156
    if blockIndex < 1_275_000: return 78
    if blockIndex < 2_555_000: return 39
    if blockIndex < 5_115_000: return 20
    if blockIndex < 10_235_000: return 10
    if blockIndex < 20_475_000: return 5
    if blockIndex < 40_955_000: return 2
    else: return 1

def getContact(address: str) -> str:
    with open(CONTACTS, "r") as f:
        contacts = f.readlines()
        for contact in contacts:
            addr, name = contact.split("=", 1)
            addr = addr.strip()
            name = name.strip()
            if addr == address: return name
        return address
def getAddress(name: str) -> str:
    with open(CONTACTS, "r") as f:
        contacts = f.readlines()
        for contact in contacts:
            addr, n = contact.split("=", 1)
            addr = addr.strip()
            n = n.strip()
            if n == name: return addr
        raise KeyError
def newContact(address: str, name: str):
    with open(CONTACTS, "a") as f:
        f.write(f"\n{address}={name}")

def remove():
    api.removeId(ID[0])
def start():
    try:
        if not sys.stdout.isatty():
            print("\033[31mEnable 'emulate terminal in output console'!\033[0m")
            print("To enable this go to: "
                  "\n'Current File' at the top"
                  "\n'Edit Configurations...'"
                  "\n'Edit configuration templates...' in bottom left corner"
                  "\nSelect python"
                  "\nPress alt/option+m"
                  "\nAnd tick 'Emulate terminal in output console'")
            sys.exit(1)
        bestVersion = api.getLatestVersion()
        if bestVersion == "..NETWORK_UNDER_MAINTENANCE" and VERSION != "-1.-1.-1":
            print("\033[31mThe network is currently under maintenance! Try again later!\033[0m")
            sys.exit(1)
        network, major, minor = bestVersion.split(".")
        cNetwork, cMajor, cMinor = VERSION.split(".")
        if ((network != cNetwork or major != cMajor) and VERSION != "-1.-1.-1") or (minor != cMinor and VERSION != "-1.-1.-1"):
            subprocess.Popen([sys.executable, "update.py"])
            time.sleep(1.5)
            sys.exit()
        with open(BLOCKS, "r") as f:
            original = [line.strip() for line in f.readlines() if line.strip()]
        global ID, transactions
        ids = api.getAllIds()
        ID[0] = api.newId()
        atexit.register(remove)
        if len(ids) == 0: return
        allCorrect = False
        while not allCorrect:
            left = len(ids)
            if left < 1: break
            allCorrect = True
            i = random.choice(ids)
            ids.remove(i)
            api.sendMessage(i, ID[0], "getBlockCount")
            gotCount = False
            gotMempool, gotBlocks = False, False
            while not gotCount:
                message, senderId, rowId = api.getNextMessage(ID[0], timeout=5)
                try:
                    if senderId != i and senderId != -1: continue
                    if message.startswith("r:getBlockCount:"):
                        message = message[16:]
                        if getBlockCount() == int(message): gotBlocks = True
                        else: api.sendMessage(i, ID[0], f"getLastBlocks:{int(message)-getBlockCount()}")
                        gotCount = True
                    elif message.startswith("noResponse"):
                        allCorrect = False
                        if int(CONFIGS[3]) == 1: print(f"Id {i} did not respond... requesting another id")
                        break
                finally: api.deleteMessageRow(rowId)
            if not allCorrect: continue
            api.sendMessage(i, ID[0], "getMempool")
            while not (gotMempool and gotBlocks):
                message, senderId, rowId = api.getNextMessage(ID[0])
                try:
                    if senderId != i: continue
                    if message.startswith("r:getMempool:"):
                        gotMempool = True
                        transactions = ast.literal_eval(message[13:])
                        for tx in transactions:
                            if tx.startswith("MSG|"):
                                ok = verifyMessage(tx)
                            else:
                                ok = verifyTx(tx)
                            if not ok:
                                allCorrect = False
                                break
                    elif message.startswith("r:getBlocks:"):
                        gotBlocks = True
                        blocks = ast.literal_eval(message[12:])
                        length = len(blocks)
                        if length < len(original):
                            allCorrect = False
                            break
                        with open(BLOCKS, "r") as f: backup = [line.strip() for line in f.readlines() if line.strip()]
                        with open(BLOCKS, "w"): pass
                        for b in range(0,length):
                            if not verifyBlock(blocks[b]):
                                with open(BLOCKS, "w") as f:
                                    for line in backup:
                                        f.write(f"{line}\n")
                                allCorrect = False
                                break
                            else:
                                with open(BLOCKS, "a") as f:
                                    f.write(f"{blocks[b]}\n")
                    elif message.startswith("r:getLastBlocks:"):
                        gotBlocks = True
                        blocks = ast.literal_eval(message[16:])
                        for block in blocks:
                            block = block.strip()
                            if verifyBlock(block):
                                with open(BLOCKS, "a") as f:
                                    f.write(f"{block}\n")
                            else:
                                allCorrect = False
                                break
                finally: api.deleteMessageRow(rowId)
    except Exception as e:
        print(e)
        end()
        sys.exit()
def end():
    api.removeId(ID[0])

def sha256(data: bytes) -> bytes:
    return hashlib.sha256(data).digest()
def hash160(d: bytes) -> bytes:
    d = sha256(d)
    d = hashlib.new("ripemd160", d).digest()
    return d
def h(i) -> int:
    return int.from_bytes(sha256(sha256(str(i).encode("utf-8"))), "big")
def combine(p, m, t, n) -> str:
    return f"{p}|{m}|{t}|{n}"
def getBlockCount() -> int:
    with open(BLOCKS, "r") as f:
        return len(f.readlines())

def formTransaction(fromAddress, toAddress, amount) -> str:
    global transactions
    nonce = getNextNonce(fromAddress)
    return f"{fromAddress}|{toAddress}|{amount}|{nonce}"
def formMessageTx(addressFrom, addressTo, message) -> str:
    nonce = getNextNonce(addressFrom)
    messageHex = message.encode("utf-8").hex()
    return f"MSG|{addressFrom}|{addressTo}|1000|{nonce}|{messageHex}"
def getMerkleRoot(txList=None) -> str:
    if txList is None: txList = transactions
    combined = ""
    for tx in txList:
        combined += tx
    return sha256(combined.encode("utf-8")).hex()
def verifyBlock(block: str) -> bool:
    try:
        header, txs = block.split(",", 1)
        txs = ast.literal_eval(txs)
        parts = header.split("|")
        if len(parts) != 4: return False
        priorHash, merkleRoot, ts, nonce = parts
        ts = int(ts)
        if ts >= int(time.time()) + 60: return False
        nonce = int(nonce)
    except (ValueError, SyntaxError): return False
    if len(txs) == 0: return False
    combined = ""
    for tx in txs:
        combined += tx
    if sha256(combined.encode("utf-8")).hex() != merkleRoot: return False
    t = []
    for tx in txs[1:]:
        tx_ = tx.split("||")[0]
        if tx_.startswith("MSG|"):
            try: kind, fromAddr, toAddr, amount, txNonce, messageHex = tx_.split("|", 5)
            except ValueError: return False
            if not verifyMessage(tx, checkMempool=False): return False
            if checkDuplicateTx(fromAddr, txNonce): return False
            if (fromAddr, txNonce) in t: return False
        else:
            fromAddr, toAddr, amount, txNonce = tx_.split("|", 3)
            if not verifyTx(tx, checkMempool=False): return False
            if checkDuplicateTx(fromAddr, txNonce): return False
            if (fromAddr, txNonce) in t: return False
        t.append((fromAddr, txNonce))

    tempBalances = getConfirmedBalances()
    for tx in txs[1:]:
        tx = tx.split("||")[0]
        if tx.startswith("MSG|"):
            kind, fromAddress, toAddress, amount, txNonce, messageHex = tx.split("|", 5)
            amount = 1000
        else:
            fromAddress, toAddress, amount, txNonce = tx.split("|")
            amount = int(amount)
        if tempBalances.get(fromAddress, 0) < amount: return False
        tempBalances[fromAddress] = tempBalances.get(fromAddress, 0) - amount
        tempBalances[toAddress] = tempBalances.get(toAddress, 0) + amount - getFee(amount)

    result = h(combine(priorHash, merkleRoot, ts, nonce))
    with open(BLOCKS, "r") as f:
        try:
            lines = f.readlines()
            blockIndex = len(lines)
            if (not txs[0].startswith("SYSTEM|")) or (not txs[0].endswith(f"|{getBlockReward(blockIndex)}|0")): return False
            if len(lines) == 0:
                if priorHash != "0" * 64: return False
            else:
                lastHeader = lines[-1].strip().split(",", 1)[0]
                lParts = lastHeader.split("|")
                lHash, lRoot, lTs, lNonce = lParts
                if int(lTs) > ts: return False
                expectedPrevHash = hex(h(combine(lHash, lRoot, int(lTs), int(lNonce))))[2:]
                if priorHash != expectedPrevHash: return False
        except (ValueError, IndexError): return False
    if result > getDifficulty(blockIndex): return False
    return True
def verifyTx(tx: str, checkMempool=True) -> bool:
    try:
        txString, pubKeyHex, sigHex = tx.split("||")
        pubKeyBytes = bytes.fromhex(pubKeyHex)
        sigBytes = bytes.fromhex(sigHex)
    except ValueError: return False
    parts = txString.split("|")
    if len(parts) != 4: return False

    fromAddress, toAddress, amount, nonce = parts
    try: amount = int(amount)
    except ValueError: return False
    if amount < 1: return False

    try:
        nonce = int(nonce)
        if checkMempool and nonce < getNextNonce(fromAddress): return False
    except ValueError: return False

    txHash = sha256(txString.encode("utf-8"))
    try:
        if not PublicKey(pubKeyBytes).verify(sigBytes, txHash, hasher=None): return False
    except Exception: return False
    derivedFrom = hash160(pubKeyBytes).hex()
    if fromAddress != derivedFrom: return False
    if checkMempool and amount > getSpendableBalance(fromAddress, ignoreTx=tx): return False
    return True
def verifyMessage(tx: str, checkMempool=True) -> bool:
    try:
        txString, pubKeyHex, sigHex = tx.split("||")
        pubKeyBytes = bytes.fromhex(pubKeyHex)
        sigBytes = bytes.fromhex(sigHex)
    except ValueError: return False
    parts = txString.split("|")
    if len(parts) != 6: return False
    kind, fromAddress, toAddress, amount, nonce, messageHex = parts
    if kind != "MSG": return False
    try:
        amount = int(amount)
        nonce = int(nonce)
        bytes.fromhex(messageHex)
    except ValueError: return False
    if amount != 1000: return False
    txHash = sha256(txString.encode("utf-8"))
    try:
        if not PublicKey(pubKeyBytes).verify(sigBytes, txHash, hasher=None): return False
    except Exception: return False
    derivedFrom = hash160(pubKeyBytes).hex()
    if fromAddress != derivedFrom: return False
    if checkMempool and (nonce < getNextNonce(fromAddress) or getSpendableBalance(fromAddress, ignoreTx=tx) < 1000): return False
    return True
def newBlock(priorHash, merkleRoot, ts, nonce, bTransactions, blockIndex):
    if h(combine(priorHash, merkleRoot, ts, nonce)) > getDifficulty(blockIndex): return
    with open(BLOCKS, "a") as file:
        file.write(f"{priorHash}|{merkleRoot}|{ts}|{nonce},{bTransactions}\n")
    for tx in bTransactions[1:]:
        if tx in transactions: transactions.remove(tx)
def getFee(amount: int) -> int:
    if amount > 10: return max(10, math.ceil(amount*0.01))
    else: return amount
def getMinerRewards(txs: str) -> int:
    total = 0
    for tx in txs:
        if tx.startswith("MSG|") or tx.startswith("SYSTEM|"): continue
        amount = int(tx.split("||")[0].split("|")[2])
        total += getFee(amount)
    return total
def getBalance(address) -> tuple[int, int]:
    vBalance = 0
    with open(BLOCKS, "r") as f:
        blocks = f.readlines()
        for block in blocks:
            txs: list[str] = ast.literal_eval(block.strip().split(",", 1)[1])
            for j, tx in enumerate(txs):
                if tx.startswith("SYSTEM|"):
                    parts = tx.split("|")
                    if parts[1] == address:
                        vBalance += int(parts[2])
                        if j == 0: vBalance += getMinerRewards(txs)
                else:
                    tx = tx.split("||")[0]
                    if tx.startswith("MSG|"):
                        kind, fromAddress, toAddress, amount, nonce, messageHex = tx.split("|", 5)
                        if fromAddress == address: vBalance -= int(amount)
                        continue
                    else: fromAddress, toAddress, amount, nonce = tx.split("|")
                    if fromAddress == address: vBalance -= int(amount)
                    if toAddress == address: vBalance += int(amount) - getFee(int(amount))
    balance = vBalance
    for tx in transactions:
        try:
            tx = tx.split("||")[0]
            if tx.startswith("MSG|"):
                kind, fromAddress, toAddress, amount, nonce, messageHex = tx.split("|", 5)
                if fromAddress == address: balance -= int(amount)
                continue
            else: fromAddress, toAddress, amount, nonce = tx.split("|")
            amount = int(amount)
        except ValueError: continue
        if fromAddress == address: balance -= amount
        if toAddress == address: balance += amount - getFee(amount)
    return vBalance, balance
def getConfirmedBalances() -> dict[str, int]:
    balances = {}
    with open(BLOCKS, "r") as f: blocks = f.readlines()
    for block in blocks:
        txs: list[str] = ast.literal_eval(block.strip().split(",", 1)[1])
        for j, tx in enumerate(txs):
            if tx.startswith("SYSTEM|"):
                _, toAddress, amount, nonce = tx.split("|")
                amount = int(amount)
                if j == 0:  balances[toAddress] = balances.get(toAddress, 0) + amount + getMinerRewards(txs)
                else: balances[toAddress] = balances.get(toAddress, 0) + amount
            else:
                tx = tx.split("||")[0]
                if tx.startswith("MSG|"):
                    kind, fromAddress, toAddress, amount, nonce, messageHex = tx.split("|", 5)
                    amount = int(amount)
                    balances[fromAddress] = balances.get(fromAddress, 0) - amount
                else:
                    fromAddress, toAddress, amount, nonce = tx.split("|")
                    amount = int(amount)
                    balances[fromAddress] = balances.get(fromAddress, 0) - amount
                    balances[toAddress] = balances.get(toAddress, 0) + amount - getFee(amount)

    return balances
def getSpendableBalance(address, ignoreTx=None) -> int:
    vBalance = 0
    with open(BLOCKS, "r") as f:
        blocks = f.readlines()
        for block in blocks:
            txs: list[str] = ast.literal_eval(block.strip().split(",", 1)[1])
            for j, tx in enumerate(txs):
                if tx.startswith("SYSTEM|"):
                    parts = tx.split("|")
                    if parts[1] == address:
                        vBalance += int(parts[2])
                        if j == 0: vBalance += getMinerRewards(txs)
                else:
                    tx = tx.split("||")[0]
                    if tx.startswith("MSG|"):
                        kind, fromAddress, toAddress, amount, nonce, messageHex = tx.split("|", 5)
                        if fromAddress == address: vBalance -= int(amount)
                        continue
                    else: fromAddress, toAddress, amount, nonce = tx.split("|")
                    if fromAddress == address: vBalance -= int(amount)
                    if toAddress == address: vBalance += int(amount) - getFee(int(amount))
    for tx in transactions:
        if tx == ignoreTx: continue
        try:
            tx = tx.split("||")[0]
            if tx.startswith("MSG|"): kind, fromAddress, toAddress, amount, nonce, messageHex = tx.split("|", 5)
            else: fromAddress, toAddress, amount, nonce = tx.split("|")
            amount = int(amount)
        except ValueError: continue
        if fromAddress == address: vBalance -= amount
    return vBalance
def getHistory(address) -> str:
    def formatAddress(address) -> str:
        address = getContact(address)
        if len(address) == 40: return f"\033[36m{address[:10]}...\033[0m"
        return f"\033[36m{address}\033[0m"
    history = ""
    with open(BLOCKS, "r") as f:
        blocks = f.readlines()
        b = len(blocks)+1
        i = -1
        for block in blocks:
            i += 1
            b -= 1
            txs: list[str] = ast.literal_eval(block.strip().split(",", 1)[1])
            for tx in txs:
                s = ""
                if tx.startswith("SYSTEM|"):
                    if i != 0:
                        parts = tx.split("|")
                        if parts[1] == address: s = f"\n\033[32m+{(getBlockReward(b)+getMinerRewards(txs))/1000:.3f}\033[0m from hashing block \033[32m({b} block(s) ago)\033[0m"
                else:
                    tx = tx.split("||")[0]
                    if tx.startswith("MSG|"):
                        kind, fromAddress, toAddress, amount, nonce, messageHex = tx.split("|", 5)
                        messageText = bytes.fromhex(messageHex).decode("utf-8", errors="replace")
                        if fromAddress == address: history += f"\n\033[31m-1\033[0m Message sent to {formatAddress(toAddress)}"
                        if toAddress == address: history += f"\nMessage received from {formatAddress(fromAddress)}: {messageText}"
                    else:
                        fromAddress, toAddress, amount, nonce = tx.split("|")
                        if fromAddress == address: history += f"\n\033[31m-{int(amount)/1000:.3f}\033[0m Sent to {formatAddress(toAddress)} \033[32m({b} block(s) ago)\033[0m"
                        if toAddress == address: history += f"\n\033[32m+{(int(amount)-getFee(int(amount)))/1000:.3f}\033[0m Received from {formatAddress(fromAddress)} \033[32m({b} block(s) ago)\033[0m"
                history += s
    for tx in transactions:
        try:
            tx = tx.split("||")[0]
            if tx.startswith("MSG|"):
                kind, fromAddress, toAddress, amount, nonce, messageHex = tx.split("|", 5)
                messageText = bytes.fromhex(messageHex).decode("utf-8", errors="replace")
                if fromAddress == address: history += f"\n\033[31m-1\033[0m Message sent to {formatAddress(toAddress)}"
                if toAddress == address: history += f"\nMessage received from {formatAddress(fromAddress)}: {messageText}"
            else:
                fromAddress, toAddress, amount, nonce = tx.split("|")
                amount = int(amount)
                if fromAddress == address: history += f"\n\033[35m[Unverified]\033[0m \033[31m-{int(amount)/1000:.3f}\033[0m Sent to {formatAddress(toAddress)}"
                if toAddress == address: history += f"\n\033[35m[Unverified]\033[0m \033[32m+{(int(amount)-getFee(int(amount)))/1000:.3f}\033[0m Received from {formatAddress(fromAddress)}"
        except ValueError: continue
    return history
def getRecentTxs(address) -> str:
    info = ""
    with open(BLOCKS, "r") as f:
        blocks = deque(f, maxlen=24)
    b = getBlockCount() + 1
    for block in blocks:
        b -= 1
        txs: list[str] = ast.literal_eval(block.strip().split(",", 1)[1])
        for tx in txs:
            if tx.startswith("SYSTEM|"):
                parts = tx.split("|")
                if parts[1] == address: info += f"SYSTEM|{address}|{getBlockReward(b)},"
            else:
                tx = tx.split("||")[0]
                fromAddress, toAddress, amount, nonce = tx.split("|")
                if fromAddress == address: info += f"{address}|{toAddress}|{amount}"
                if toAddress == address: info += f"{fromAddress}|{address}|{amount}"
    return info
def getNextNonce(address) -> int:
    nonce = 0
    with open(BLOCKS, "r") as f:
        blocks = f.readlines()
        for block in blocks:
            txs: list[str] = ast.literal_eval(block.strip().split(",", 1)[1])
            for tx in txs:
                if not tx.startswith("SYSTEM|"):
                    if tx.startswith("MSG|"): kind, fromAddr, toAddr, amount, n, messageHex = tx.split("||")[0].split("|", 5)
                    else: fromAddr, toAddr, amount, n = tx.split("||")[0].split("|")
                    if fromAddr == address: nonce = max(nonce, int(n))
    for tx in transactions:
        try:
            if tx.startswith("SYSTEM|"): continue
            if tx.startswith("MSG|"): kind, fromAddr, toAddr, amount, n, messageHex = tx.split("||")[0].split("|", 5)
            else: fromAddr, toAddr, amount, n = tx.split("||")[0].split("|")
            if fromAddr == address: nonce = max(nonce, int(n))
        except ValueError: continue
    return nonce + 1
def n(s: str) -> str:
    return f"\033[36m{s}\033[0m"
def printBlockInfo(block: str, index: int):
    d = getDifficultyBits(index)
    txs: list[str] = ast.literal_eval(block.strip().split(",", 1)[1])
    header = block.strip().split(",", 1)[0]
    parts = header.split("|")
    if len(parts) == 3:
        priorHash, merkleRoot, nonce = parts
        noTs = True
    else:
        priorHash, merkleRoot, ts, nonce = parts
        noTs = False
    print("\n" + ("-" * 50))
    print(f"\033[1;32mBlock {index}\033[0m\n")
    print(f"{'Previous Hash:':<15} {n(priorHash):<15}")
    print(f"{'Merkle Root:':<15} {n(merkleRoot):<15}")
    print(f"{'Nonce:':<15} {n(nonce):<15}")
    print(f"{'Difficulty:':<15} {n(d):<15}")
    if not noTs: print(f"{'Time:':<15} {n(time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(int(ts)))):<15}")
    print("Transactions:")
    i = 0
    for tx in txs:
        i += 1
        if tx.startswith("SYSTEM|"):
            fromAddress, toAddress, amount, nonce = tx.split("|")
            print(f"\t\033[34m[{i}]\033[0m +10 to {n(toAddress[:10])}...")
        else:
            tx = tx.split("||")[0]
            if tx.startswith("MSG|"): print(f"\t\033[34m[{i}]\033[0m -1 Message sent")
            else:
                fromAddress, toAddress, amount, nonce = tx.split("|")
                print(f"\t\033[34m[{i}]\033[0m {int(amount):+} to {n(toAddress[:10])}... from {n(fromAddress[:10])}...")
    print("-" * 50)
def checkDuplicateTx(address, nonce) -> bool:
    try:
        i = -1
        with open(BLOCKS, "r") as f:
            blocks = f.readlines()
            for block in blocks:
                i += 1
                txs: list[str] = ast.literal_eval(block.strip().split(",", 1)[1])
                for tx in txs:
                    if tx.startswith("SYSTEM|"): continue
                    if tx.startswith("MSG|"): kind, fromAddress, toAddress, amount, n, messageHex = tx.split("||")[0].split("|", 5)
                    else: fromAddress, toAddress, amount, n = tx.split("||")[0].split("|")
                    if fromAddress == address and n == nonce: return True
        return False
    except Exception: return True
def reorgTxs(blocks: str):
    pass
def input_(prompt=""):
    #NOTE: This subprogram is not written by me, this is for inputs and not for the actual logic
    global refreshFreq
    stdinFd = sys.stdin.fileno()
    oldSettings = termios.tcgetattr(stdinFd)
    buffer = ""
    lastRefresh = 0.0
    try:
        tty.setcbreak(stdinFd)
        if prompt: print(prompt, end="", flush=True)
        while True:
            now = time.time()
            if buffer == "" and now - lastRefresh >= refreshFreq:
                refresh()
                if prompt: print(prompt, end="", flush=True)
                lastRefresh = now
            ready, _, _ = select.select([sys.stdin], [], [], 0.05)
            if not ready: continue
            ch = sys.stdin.read(1)
            if ch in ("\n", "\r"):
                print()
                return buffer
            if ch == "\x03": raise KeyboardInterrupt
            if ch == "\x7f":
                if buffer:
                    buffer = buffer[:-1]
                    sys.stdout.write("\b \b")
                    sys.stdout.flush()
                continue
            if ch.isprintable():
                buffer += ch
                sys.stdout.write(ch)
                sys.stdout.flush()
    finally:
        termios.tcsetattr(stdinFd, termios.TCSADRAIN, oldSettings)
def mine_(args):
    os.nice(10)
    prefix, targetBytes, startNonce, count = args
    bestHashBytes = b"\xff" * 32
    foundNonce = None
    attempts = 0
    for nonce in range(startNonce, startNonce+count):
        hashBytes = hashlib.sha256(hashlib.sha256(prefix + str(nonce).encode("utf-8")).digest()).digest()
        attempts += 1
        if hashBytes < bestHashBytes: bestHashBytes = hashBytes
        if hashBytes <= targetBytes:
            foundNonce = nonce
            return foundNonce, bestHashBytes, attempts
    return None, bestHashBytes, attempts

forkCase = False
mine = False
extraText, miningInfo = "", ""
refreshFreq = float(CONFIGS[0])
mineProcesses = int(CONFIGS[4])
peers = 0
address = None
pool = None
def laptopSleep():
    while True:
        l = time.time()
        time.sleep(1)
        g = time.time() - l
        if g > 30 + float(CONFIGS[1]): os._exit(0)
def mining():
    try:
        def broadcastBlock():
            ids = api.getAllIds()
            with open(BLOCKS, "r") as f:
                block = f.readlines()[-1].strip()
            for i in ids:
                    if i != ID[0]: api.sendMessage(i, ID[0], f"verifyBlock:{block}")
        global mine, miningInfo, address, mineProcesses
        batchSize = 10000
        while True:
            if not mine:
                time.sleep(0.1)
                continue
            miningInfo = " "
            r = random.randrange(0, 10000000000000)
            counter = 0
            lastInfoCounter = 0
            minFound = 256
            minFoundBytes = b"\xff" * 32
            totalHashesFound = 0
            ts_ = 0
            lastTs_ = 0
            s = ""
            while True:
                if not mine:
                    miningInfo = ""
                    break
                blockIndex = getBlockCount()
                target = getDifficulty(blockIndex)
                targetBits = getDifficultyBits(blockIndex)
                with open(BLOCKS, "r") as f:
                    try:
                        lastLine = f.readlines()[-1].strip()
                        header, txs = lastLine.split(",", 1)
                        parts = header.split("|")
                        if len(parts) == 3:
                            oldPriorHash, oldMerkleRoot, oldNonce = parts
                            prevHash = hex(h(f"{oldPriorHash}|{oldMerkleRoot}|{int(oldNonce)}"))[2:]
                        else:
                            oldPriorHash, oldMerkleRoot, oldTs, oldNonce = parts
                            prevHash = hex(h(combine(oldPriorHash, oldMerkleRoot, oldTs, int(oldNonce))))[2:]
                    except IndexError:
                        prevHash = "0" * 64
                bTransactions = transactions[:]
                bTransactions.insert(0, f"SYSTEM|{address}|{getBlockReward(blockIndex)}|0")
                merkleRoot = getMerkleRoot(bTransactions)
                ts = int(time.time())
                prefix = f"{prevHash}|{merkleRoot}|{ts}|".encode("utf-8")
                targetBytes = target.to_bytes(32, "big")

                jobs = []
                for i in range(0,mineProcesses):
                    jobs.append((prefix, targetBytes, r + i * batchSize, batchSize))
                results = pool.map(mine_, jobs)
                foundNonce = None
                roundAttempts = 0
                bestRoundBytes = b"\xff" * 32
                for nonceResult, bestBytes, attempts in results:
                    roundAttempts += attempts
                    if bestBytes < bestRoundBytes: bestRoundBytes = bestBytes
                    if nonceResult is not None and foundNonce is None: foundNonce = nonceResult
                counter += roundAttempts
                r += batchSize * mineProcesses
                if bestRoundBytes < minFoundBytes:
                    minFoundBytes = bestRoundBytes
                    minFoundInt = int.from_bytes(bestRoundBytes, "big")
                    if minFoundInt > 0: minFound = math.log2(minFoundInt)
                if counter - lastInfoCounter >= 1_000_000:
                    lastTs_ = ts_
                    ts_ = time.time() * 1000
                    mHashes = 1000/abs(lastTs_ - ts_)
                    miningInfo = (f"Min found: {minFound:.2f}, Requirement: <{targetBits}. "
                                  f"Total attempts: {counter:,}, total hashes found: {totalHashesFound}\n{mHashes:.3f} MH/sec\n" + ("-" * 115))
                    lastInfoCounter = counter
                if foundNonce is None: continue
                newBlock(prevHash, merkleRoot, ts, foundNonce, bTransactions, blockIndex)
                broadcastBlock()
                totalHashesFound += 1
    except Exception as e:
        print(e)
        time.sleep(1)
def peerCount():
    global peers
    while True:
        time.sleep(4)
        try:
            ids = api.getAllIds()
            if ID[0] not in ids:
                ID[0] = api.newId()
                ids = api.getAllIds()
            peers = len(ids) - 1
        except Exception: pass
def check():
    global transactions, forkCase
    while True:
        try:
            message, senderId, rowId = api.getNextMessage(ID[0])
            if message.startswith("verifyTx:"):
                if NETWORK_INFO: print(f"\033[34m[RECEIVED]\033[0m tx from node {senderId}")
                if message[9:].startswith("MSG|"): result = verifyMessage(message[9:])
                else: result = verifyTx(message[9:])
                if result and message[9:] not in transactions:
                    transactions.append(message[9:])
                    if NETWORK_INFO: print(f"\033[32m[ACCEPTED]\033[0m tx accepted")
            elif message.startswith("verifyBlock:"):
                if NETWORK_INFO: print(f"\033[34m[RECEIVED]\033[0m block from node {senderId}")
                result = verifyBlock(message[12:])
                if result:
                    file = open(BLOCKS, "a")
                    file.write(f"{str(message[12:])}\n")
                    file.close()
                    try:
                        _, txs = message[12:].split(",", 1)
                        txs = ast.literal_eval(txs)
                        for tx in txs[1:]:
                            if tx in transactions: transactions.remove(tx)
                        if NETWORK_INFO: print(f"\033[32m[ACCEPTED]\033[0m block accepted")
                    except (ValueError, SyntaxError): pass
                else:
                    api.sendMessage(senderId, ID[0], "getBlockCount")
                    # if NETWORK_INFO: print(f"\033[31m[REJECTED]\033[0m block rejected: requesting full chain")
                    forkCase = True
            elif message.startswith("getMempool"):
                if NETWORK_INFO: print(f"\033[36m[SENDING]\033[0m mempool to node {senderId}")
                api.sendMessage(senderId, ID[0], f"r:getMempool:{str(transactions)}")
            elif message.startswith("getBlock:"):
                t = message[9:]
                if NETWORK_INFO: print(f"\033[36m[SENDING]\033[0m block {t} to node {senderId}")
                with open(BLOCKS, "r") as f:
                    try:
                        block = f.readlines()[int(t)].strip()
                        api.sendMessage(senderId, ID[0], f"r:getBlock:{block}")
                    except (ValueError, IndexError): pass
            elif message.startswith("getBlocks"):
                if NETWORK_INFO: print(f"\033[36m[SENDING]\033[0m all blocks to node {senderId}")
                with open(BLOCKS, "r") as f:
                    try:
                        blocks = f.readlines()
                        for block in range(0,len(blocks)):
                            blocks[block] = blocks[block].strip()
                        api.sendMessage(senderId, ID[0], f"r:getBlocks:{blocks}")
                    except (ValueError, IndexError): pass
            elif message.startswith("getBlockCount"):
                if NETWORK_INFO: print(f"\033[36m[SENDING]\033[0m block count to node {senderId}")
                with open(BLOCKS, "r") as f:
                    api.sendMessage(senderId, ID[0], f"r:getBlockCount:{len(f.readlines())}")
            elif message.startswith("getBalance:"):
                addr = message[11:]
                v, unV = getBalance(addr)
                api.sendMessage(senderId, ID[0], f"r:getBalance:{v},{unV}")
            elif message.startswith("getRecentTxs:"):
                addr = message[13:]
                api.sendMessage(senderId, ID[0], f"r:getRecentTxs:{getRecentTxs(addr)}")
            elif message.startswith("getLastBlocks:"):
                try:
                    amount = int(message[14:])
                    if NETWORK_INFO: print(f"\033[36m[SENDING]\033[0m last {amount} blocks to node {senderId}")
                    result = []
                    with open(BLOCKS, "r") as f:
                        blocks = f.readlines()
                        for i in range(len(blocks)-1, len(blocks)-1-amount, -1):
                            result.append(blocks[i])
                    result.reverse()
                    api.sendMessage(senderId, ID[0], f"r:getLastBlocks:{result}")
                except Exception: pass
            elif message.startswith("getDifficulty"):
                api.sendMessage(senderId, ID[0], f"r:getDifficulty:{getDifficultyBits(getBlockCount())}")
            elif message.startswith("r:getBlocks:") and forkCase:
                if NETWORK_INFO: print(f"\033[34m[RECEIVED]\033[0m all blocks from node {senderId}")
                with open(BLOCKS, "r") as f:
                    original = f.readlines()
                blocks = ast.literal_eval(message[12:])
                length = len(blocks)
                if length < len(original): continue
                with open(BLOCKS, "w"): pass
                for b in range(0, length):
                    if b == 0:
                        with open(BLOCKS, "a") as f:
                            f.write(f"{blocks[0]}\n")
                        continue
                    if not verifyBlock(blocks[b]):
                        with open(BLOCKS, "w") as f:
                            for line in original:
                                f.write(line)
                        if NETWORK_INFO: print(f"\033[31m[REJECTED]\033[0m other node's chain is invalid")
                        break
                    with open(BLOCKS, "a") as f:
                        f.write(f"{blocks[b]}\n")
                if NETWORK_INFO: print(f"\033[32m[ACCEPTED]\033[0m other node's chain is longer, chain replaced")
                forkCase = False
            elif message.startswith("r:getBlockCount:") and forkCase:
                try:
                    l = int(message[16:])
                    if l > getBlockCount(): api.sendMessage(senderId, ID[0], "getBlocks")
                    else: forkCase = False
                except Exception: forkCase = False
        except Exception:
            pass
        finally:
            if rowId is not None: api.deleteMessageRow(rowId)
def refresh():
    try:
        t = ""
        global extraText, peers, miningInfo
        privateKey = PrivateKey(bytes.fromhex(hPassword.strip().removeprefix("0x")))
        publicKey = privateKey.public_key.format(compressed=True)
        address = hash160(publicKey).hex()
        v, unV = getBalance(address)
        history = getHistory(address)
        history = history.split("\n")[-9:]
        bTransactions = transactions[:]
        bTransactions.insert(0, f"SYSTEM|{address}|{getBlockReward(getBlockCount())}|0")
        info = [f"Node version: {n(VERSION)}", f"Connected peers: {n(peers)}", f"Address: {n(address)}",
                f"Verified balance: {n(f"{v/1000:.3f}")}", f"Unverified balance: {n(f"{unV/1000:.3f}")}", f"Block count: {n(getBlockCount())}",
                f"Current block difficulty: {n(getDifficultyBits(getBlockCount()))}",
                f"Current block reward: {n(f"{getBlockReward(getBlockCount())/1000:.3f} (+{getMinerRewards(bTransactions)/1000:.3f})")}"]
        for i in range(0, 8):
            if i+1 < len(history): t += f"\n{info[i]:<60} {history[i+1].strip():<60}"
            else: t += f"\n{info[i]:<60}"
        t += "\n" + ("-" * 115)
        if miningInfo != "": t += f"\n{miningInfo}"
        if extraText == "":
            items = ["Send Coins", "Toggle Mining", "Send Message (costs 1 coin)", "Add Contact", "Log Out", "Quit"]
            numberColor = "34"
            selectionColor = "32"
            r = "Select option:"
            a = len(items)
            for i in range(0, a):
                if numberColor is not None:
                    r += f"\n\033[{numberColor}m[{i + 1}]\033[0m {items[i]}"
                else:
                    r += f"\n[{i + 1}] {items[i]}"
            t += f"\n{r}"
        else:
            t += f"\n{extraText}"
        print("\033[H\033[J" + t + "\n", end="", flush=True)
    except Exception: pass
def clear():
    os.system("cls" if os.name == "nt" else "clear")
hPassword = ""
def main():
    global extraText, NETWORK_INFO, hPassword, mine, miningInfo, address
    def broadcastTransaction(transaction: str):
        ids = api.getAllIds()
        for i in ids:
            if i != ID[0]: api.sendMessage(i, ID[0], f"verifyTx:{transaction}")
    def getSeed() -> str:
        while True:
            try:
                uInput = input("Enter wallet seed: ")
                return f"{h(uInput):064x}"
            except ValueError:
                print("Invalid input")
                continue
    hPassword = getSeed()
    privateKey = PrivateKey(bytes.fromhex(hPassword.strip().removeprefix("0x")))
    publicKey = privateKey.public_key.format(compressed=True)
    address = hash160(publicKey).hex()
    while True:
        try:
            refresh()
            uInput = int(input_("[User] "))
            if not 0 < uInput <= 6: raise ValueError
        except ValueError:
            print("\033[31mInvalid input\033[0m")
            continue
        if uInput == 1:
            try:
                extraText = " "
                refresh()
                fromAddress = address
                toAddress_ = input("Enter receiver address: ")
                if len(toAddress_) != 40: toAddress = getAddress(toAddress_)
                else: toAddress = toAddress_
                amount = int(round(float(input_("Enter amount: "))*1000, 3))
                spend = getSpendableBalance(fromAddress)
                if amount < 10 or amount > spend:
                    print("\033[31mInvalid amount\033[0m")
                    continue
                transactionString = formTransaction(fromAddress, toAddress, amount)
                transactionBytes = transactionString.encode("utf-8")
                transactionHash = sha256(transactionBytes)
                signature = privateKey.sign(transactionHash, hasher=None)
                txPacket = f"{transactionString}||{publicKey.hex()}||{signature.hex()}"
                response = input_(f"Confirm Send {n(f"{amount/1000:.3f}")} coins to {n(toAddress_)} (y/n)?: ").lower()
                if response == 'y':
                    broadcastTransaction(txPacket)
                    transactions.append(txPacket)
                extraText = ""
            except KeyboardInterrupt:
                extraText = ""
                continue
            except Exception:
                extraText = "\033[31mInvalid input!\033[0m"
                time.sleep(1)
                extraText = ""
                continue
        elif uInput == 2:
            if mine:
                mine = False
                miningInfo = ""
            else: mine = True
        elif uInput == 3:
            try:
                extraText = " "
                refresh()
                if getSpendableBalance(address) < 1000:
                    extraText = "\033[31mInsufficient funds!\033[0m"
                    time.sleep(1)
                    extraText = ""
                    continue
                text = input_("Enter message (to go back leave blank): ")
                a = input("Enter receiver's address: ")
                if len(a) != 40: a = getAddress(a)
                if text == "" or a == "": continue
                txString = formMessageTx(address, a, text)
                txHash = sha256(txString.encode("utf-8"))
                signature = privateKey.sign(txHash, hasher=None)
                txPacket = f"{txString}||{publicKey.hex()}||{signature.hex()}"
                broadcastTransaction(txPacket)
                transactions.append(txPacket)
                extraText = "\033[32mMessage sent\033[0m"
                time.sleep(1)
                extraText = ""
            except Exception:
                extraText = "\033[31mInvalid input!\033[0m"
                time.sleep(1)
                extraText = ""
                continue
        elif uInput == 4:
            extraText = " "
            refresh()
            addr = input("Enter address: ")
            name = input_("Enter name: ")
            newContact(addr, name)
            extraText = ""
        elif uInput == 5:
            hPassword = ""
            clear()
            hPassword = getSeed()
            privateKey = PrivateKey(bytes.fromhex(hPassword.strip().removeprefix("0x")))
            publicKey = privateKey.public_key.format(compressed=True)
            address = hash160(publicKey).hex()
            miningInfo = ""
            mine = False
            continue
        elif uInput == 6: sys.exit(0)

if __name__ == '__main__':
    multiprocessing.freeze_support()
    pool = multiprocessing.get_context("spawn").Pool(processes=int(CONFIGS[4]))
    try:
        if int(CONFIGS[2]) == 0: #if not onlyNode
            start()
            threading.Thread(target=check, daemon=True).start()
            threading.Thread(target=peerCount, daemon=True).start()
            threading.Thread(target=mining).start()
            threading.Thread(target=laptopSleep, daemon=True).start()
            main()
        else:
            NETWORK_INFO = True
            start()
            check()
    except KeyboardInterrupt: pass
    finally:
        if pool is not None:
            pool.close()
            pool.join()
        end()
        os._exit(0)