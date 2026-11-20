import websocket
import json
import ssl
import time
import matplotlib.pyplot as plt
from dotenv import load_dotenv
import os

import numpy as np
from scipy.signal import welch
from matplotlib.widgets import Button
from collections import deque

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


FS = 128

af3 = deque(maxlen=256)
t7  = deque(maxlen=256)
pz  = deque(maxlen=256)
t8  = deque(maxlen=256)
af4 = deque(maxlen=256)

selected_channel = "AF3"

# ----------------------------------
# Botones
# ----------------------------------

def select_af3(event):
    global selected_channel
    selected_channel = "AF3"

def select_t7(event):
    global selected_channel
    selected_channel = "T7"

def select_pz(event):
    global selected_channel
    selected_channel = "PZ"

def select_t8(event):
    global selected_channel
    selected_channel = "T8"

def select_af4(event):
    global selected_channel
    selected_channel = "AF4"

# ----------------------------------
# Potencia de banda
# ----------------------------------

def band_power(fft_values, freqs, low, high):

    idx = (freqs >= low) & (freqs < high)

    if not np.any(idx):
        return 0

    return np.mean(fft_values[idx])

# ----------------------------------
# Interfaz
# ----------------------------------

plt.ion()

fig, ax = plt.subplots(figsize=(10, 6))
plt.subplots_adjust(bottom=0.25)

btn_af3 = Button(plt.axes([0.05, 0.05, 0.12, 0.075]), "AF3")
btn_t7  = Button(plt.axes([0.22, 0.05, 0.12, 0.075]), "T7")
btn_pz  = Button(plt.axes([0.39, 0.05, 0.12, 0.075]), "PZ")
btn_t8  = Button(plt.axes([0.56, 0.05, 0.12, 0.075]), "T8")
btn_af4 = Button(plt.axes([0.73, 0.05, 0.12, 0.075]), "AF4")

btn_af3.on_clicked(select_af3)
btn_t7.on_clicked(select_t7)
btn_pz.on_clicked(select_pz)
btn_t8.on_clicked(select_t8)
btn_af4.on_clicked(select_af4)

labels = ["Delta", "Theta", "Alpha", "Beta", "Gamma"]

bars = ax.bar(labels, [0, 0, 0, 0, 0])

ax.set_title("Bandas EEG - AF3")
ax.set_ylabel("Potencia")
ax.set_xlabel("Bandas")

counter = 0

print("Recibiendo EEG...")

while plt.fignum_exists(fig.number):

    data = json.loads(ws.recv())

    if "eeg" not in data:
        continue

    af3.append(float(data["eeg"][2]))
    t7.append(float(data["eeg"][3]))
    pz.append(float(data["eeg"][4]))
    t8.append(float(data["eeg"][5]))
    af4.append(float(data["eeg"][6]))

    if len(af3) < 256:
        continue

    counter += 1

    # actualizar solo 8 veces por segundo
    if counter < 16:
        continue

    counter = 0

    signal_map = {
        "AF3": af3,
        "T7": t7,
        "PZ": pz,
        "T8": t8,
        "AF4": af4
    }

    signal = np.array(signal_map[selected_channel])

    fft_values = np.abs(np.fft.rfft(signal))
    freqs = np.fft.rfftfreq(len(signal), d=1/FS)

    delta = band_power(fft_values, freqs, 0.5, 4)
    theta = band_power(fft_values, freqs, 4, 8)
    alpha = band_power(fft_values, freqs, 8, 13)
    beta  = band_power(fft_values, freqs, 13, 30)
    gamma = band_power(fft_values, freqs, 30, 50)

    valores = [delta, theta, alpha, beta, gamma]

    for bar, valor in zip(bars, valores):
        bar.set_height(valor)

    ax.set_title(f"Bandas EEG - {selected_channel}")

    ymax = max(valores) * 1.2

    if ymax > 0:
        ax.set_ylim(0, ymax)

    fig.canvas.draw_idle()
    fig.canvas.flush_events()

print("Ventana cerrada")