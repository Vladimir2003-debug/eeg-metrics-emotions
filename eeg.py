import websocket
import json
import ssl
import time
import os
import csv
from datetime import datetime
import threading
from collections import deque
import atexit
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
from dotenv import load_dotenv

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
# Suscribirse al flujo de métricas de rendimiento (met)
subscribe = send_request(
    "subscribe",
    {
        "cortexToken": token,
        "session": session_id,
        "streams": ["met"]
    },
    5
)

print(subscribe)
print("Recibiendo métricas de rendimiento (MET)...\n")

# Configuración y preparación del archivo CSV
CSV_FILENAME = f"eeg_metricas_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
# CSV_FILENAME = "eeg_metricas.csv"  # Descomentar si se prefiere un nombre fijo

csv_lock = threading.Lock()
csv_file = open(CSV_FILENAME, mode="w", newline="", encoding="utf-8")
csv_writer = csv.writer(csv_file)

# Encabezados del archivo CSV
csv_writer.writerow([
    "Muestra",
    "Timestamp",
    "Fecha_Hora",
    "At",
    "En",
    "Ex",
    "In",
    "Re",
    "St"
])
csv_file.flush()

contador_muestras = 0
ejecutando = True

print(f"[INFO] Exportando datos a CSV en tiempo real: {os.path.abspath(CSV_FILENAME)}\n")

def cerrar_csv():
    global csv_file
    with csv_lock:
        if csv_file and not csv_file.closed:
            csv_file.flush()
            csv_file.close()
            print(f"\n[INFO] Grabación finalizada. Total de muestras guardadas: {contador_muestras}")
            print(f"[INFO] Archivo CSV guardado exitosamente en: {os.path.abspath(CSV_FILENAME)}")

atexit.register(cerrar_csv)

MAX_PUNTOS = 50

# Orden visual exacto de tu interfaz: At, En, Ex, In, Re, St
ORDEN_VISUAL = ["Attention", "Engagement", "Excitement", "Interest", "Relaxation", "Stress"]

CONFIG_METRICAS = {
    "Attention":  {"etiqueta": "At", "color": "#e63946"},
    "Engagement": {"etiqueta": "En", "color": "#00bcba"},
    "Excitement": {"etiqueta": "Ex", "color": "#e8c547"},
    "Interest":   {"etiqueta": "In", "color": "#ff8c42"},
    "Relaxation": {"etiqueta": "Re", "color": "#3a86ef"},
    "Stress":     {"etiqueta": "St", "color": "#ab47bc"}
}

metricas_data = {nombre: deque(maxlen=MAX_PUNTOS) for nombre in ORDEN_VISUAL}

def leer_websocket():
    global contador_muestras
    while ejecutando:
        try:
            msg = ws.recv()
            if not msg:
                break
            data = json.loads(msg)
            if "met" in data:
                m = data["met"]
                timestamp = data.get("time", time.time())
                fecha_hora = datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
                
                # Extraemos los valores de acuerdo a TU lista de columnas exacta:
                if len(m) >= 13:
                    val_at = m[1] * 100 if m[1] is not None else 0
                    val_en = m[3] * 100 if m[3] is not None else 0
                    val_ex = m[5] * 100 if m[5] is not None else 0
                    val_st = m[8] * 100 if m[8] is not None else 0
                    val_re = m[10] * 100 if m[10] is not None else 0
                    val_in = m[12] * 100 if m[12] is not None else 0

                    metricas_data["Attention"].append(val_at)
                    metricas_data["Engagement"].append(val_en)
                    metricas_data["Excitement"].append(val_ex)
                    metricas_data["Stress"].append(val_st)
                    metricas_data["Relaxation"].append(val_re)
                    metricas_data["Interest"].append(val_in)

                    # Exportar cada muestra recibida al CSV
                    contador_muestras += 1
                    with csv_lock:
                        if not csv_file.closed:
                            csv_writer.writerow([
                                contador_muestras,
                                timestamp,
                                fecha_hora,
                                val_at,
                                val_en,
                                val_ex,
                                val_in,
                                val_re,
                                val_st
                            ])
                            csv_file.flush()

        except Exception as e:
            if ejecutando:
                print(f"Error en WebSocket: {e}")
            break

# Hilo para recepción de datos
hilo_ws = threading.Thread(target=leer_websocket, daemon=True)
hilo_ws.start()

# Configuración del gráfico
fig, axes = plt.subplots(6, 1, figsize=(8, 10), sharex=True)
fig.canvas.manager.set_window_title("Métricas MET - Emotiv (Mapeo Exacto)")

lines = []
textos_valor = []

for i, nombre in enumerate(ORDEN_VISUAL):
    ax = axes[i]
    ax.set_ylim(0, 100)
    
    info = CONFIG_METRICAS[nombre]
    
    ax.set_ylabel(info["etiqueta"], rotation=0, labelpad=20, weight='bold', fontsize=12)
    ax.grid(True, linestyle='--', alpha=0.4)
    
    line, = ax.plot([], [], color=info["color"], lw=2)
    lines.append(line)
    
    txt = ax.text(0.02, 0.65, '', transform=ax.transAxes, fontsize=10, weight='bold',
                  bbox=dict(boxstyle='round,pad=0.3', facecolor='white', edgecolor=info["color"]))
    textos_valor.append(txt)

def actualizar_grafica(frame):
    for i, nombre in enumerate(ORDEN_VISUAL):
        datos = list(metricas_data[nombre])
        if datos:
            x = list(range(len(datos)))
            lines[i].set_data(x, datos)
            axes[i].set_xlim(0, max(MAX_PUNTOS, len(datos)))
            
            ultimo_valor = int(datos[-1])
            textos_valor[i].set_text(str(ultimo_valor))
            
    return lines + textos_valor

ani = FuncAnimation(fig, actualizar_grafica, interval=200, cache_frame_data=False)

def on_close(event):
    global ejecutando
    ejecutando = False
    cerrar_csv()

fig.canvas.mpl_connect('close_event', on_close)

try:
    plt.tight_layout()
    plt.show()
finally:
    ejecutando = False
    cerrar_csv()
    try:
        ws.close()
    except Exception:
        pass

