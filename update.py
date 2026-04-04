import os, subprocess, sys
import urllib.request as r

def update(name):
    with r.urlopen(url + name) as response:
        data = response.read()
    with open(name + ".tmp", "wb") as f:
        f.write(data)
    os.replace(name + ".tmp", name)

url = "https://raw.githubusercontent.com/7xy95/Mesh/main/"
update("api.py")
update("main.py")
update("version.txt")
subprocess.Popen([sys.executable, "main.py"])
sys.exit()