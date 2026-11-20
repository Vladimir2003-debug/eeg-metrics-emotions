import websocket
import json
import ssl
import time
import matplotlib.pyplot as plt
from dotenv import load_dotenv
import os

load_dotenv()

CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")

ws = websocket.create_connection(
    "wss://localhost:6868",
    sslopt={"cert_reqs": ssl.CERT_NONE}
)

def send_request(method, params, request_id):
    req = {
        "jsonrpc": "2.0",
        "method": method,
        "params": params,
        "id": request_id
    }
    ws.send(json.dumps(req))
    return json.loads(ws.recv())

# Solicitar acceso
print(send_request(
    "requestAccess",
    {
        "clientId": CLIENT_ID,
        "clientSecret": CLIENT_SECRET,
    },
    1
))

# Autorizar
auth = send_request(
    "authorize",
    {
        "clientId": CLIENT_ID,
        "clientSecret": CLIENT_SECRET,
        "debit": 1
    },
    2
)
print(auth)

token = auth["result"]["cortexToken"]
print("Token obtenido")

# Buscar headset
headsets = send_request("queryHeadsets", {}, 3)
headset_id = headsets["result"][0]["id"]

print("Headset:", headset_id)

# Crear sesión
session = send_request(
    "createSession",
    {
        "cortexToken": token,
        "headset": headset_id,
        "status": "active"
    },
    4
)
print(session)
session_id = session["result"]["id"]

print("Session:", session_id)

license_info = send_request(
    "getLicenseInfo",
    {
        "cortexToken": token
    },
    20
)
print("License info:\n")
print(license_info)

# Suscribirse al EEG
subscribe = send_request(
    "subscribe",
    {
        "cortexToken": token,
        "session": session_id,
        "streams": ["eeg"]
    },
    5
)

print(subscribe)

print("Recibiendo EEG...")
plt.ion()

af3 = []
t7 = []
pz = []
t8 = []
af4 = []

while True:
    data = json.loads(ws.recv())

    if "eeg" in data:

        af3.append(data["eeg"][2])
        t7.append(data["eeg"][3])
        pz.append(data["eeg"][4])
        t8.append(data["eeg"][5])
        af4.append(data["eeg"][6])

        if len(af3) > 500:
            af3.pop(0)
            t7.pop(0)
            pz.pop(0)
            t8.pop(0)
            af4.pop(0)

        plt.clf()

        plt.plot(af3, label="AF3")
        plt.plot(t7, label="T7")
        plt.plot(pz, label="Pz")
        plt.plot(t8, label="T8")
        plt.plot(af4, label="AF4")

        plt.legend()
        plt.xlabel("Tiempo (muestras)")
        plt.ylabel("Amplitud EEG")
        plt.pause(0.01)