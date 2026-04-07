import os, subprocess, sys, api
import urllib.request as r
import certifi
os.environ["SSL_CERT_FILE"] = certifi.where()

def update(name):
    with r.urlopen(url + name) as response:
        data = response.read()
    with open(name + ".tmp", "wb") as f:
        f.write(data)
    os.replace(name + ".tmp", name)

url = "https://raw.githubusercontent.com/7xy95/Mesh/main/"
print("Updating node...")
update("api.py")
update("main.py")
update("version.txt")
version = api.getLatestVersion()
print(f"Mesh v{version} installed successfully")
subprocess.Popen([sys.executable, "main.py"])