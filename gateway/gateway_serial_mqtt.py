#!/usr/bin/env python3
"""
Gateway IoT - leitura serial e publicacao MQTT
Etapa 3 - Projeto Final - Sistemas Operacionais Embarcados
"""
import configparser
import json
import logging
import sys
import time
from collections import deque
from datetime import datetime, timezone

import serial
import paho.mqtt.client as mqtt

CFG_PATH = "/etc/gateway-iot/config.ini"


# =============== utilidades ===============

def now_iso_utc():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def setup_logging(level_name):
    level = getattr(logging, level_name.upper(), logging.INFO)
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )


# =============== parsing da linha serial ===============

def parse_line(raw_line):
    """Recebe 'gw=gw01,type=sensors,t_soil=24.6' e devolve dict.
       Lanca ValueError se a linha nao estiver no formato esperado."""
    fields = {}
    for kv in raw_line.strip().split(","):
        if "=" not in kv:
            raise ValueError(f"campo invalido: {kv!r}")
        k, v = kv.split("=", 1)
        fields[k.strip()] = v.strip()
    if fields.get("type") != "sensors":
        raise ValueError("tipo de mensagem nao suportado")
    if "gw" not in fields:
        raise ValueError("campo gw ausente")
    return fields


# =============== montagem dos payloads ===============

def build_payloads(fields, gateway_id, site):
    """Converte um dict de campos em uma lista de (topico, payload_dict)."""
    base = {
        "gateway_id": gateway_id,
        "site": site,
        "origem": "arduino_uno",
        "timestamp": now_iso_utc(),
    }
    out = []

    # ---- DS18B20: temperatura do solo (ativo nesta etapa) ----
    if fields.get("t_soil") and fields["t_soil"] != "err":
        try:
            valor = float(fields["t_soil"])
            status = "ok" if -10.0 <= valor <= 60.0 else "warning"
            out.append((
                f"agro/{gateway_id}/ds18b20/temperatura_solo",
                {**base, "sensor_id": "ds18b20", "tipo": "temperatura_solo",
                 "valor": valor, "unidade": "C", "status": status}
            ))
        except ValueError:
            logging.warning("t_soil nao numerico: %r", fields["t_soil"])

    # ---- DHT22: temperatura e umidade do ar (preparado, sera ativado) ----
    # if fields.get("t_air") and fields["t_air"] != "err":
    #     valor = float(fields["t_air"])
    #     out.append((f"agro/{gateway_id}/dht22/temperatura",
    #                 {**base, "sensor_id": "dht22", "tipo": "temperatura",
    #                  "valor": valor, "unidade": "C", "status": "ok"}))
    # if fields.get("h_air") and fields["h_air"] != "err":
    #     valor = float(fields["h_air"])
    #     out.append((f"agro/{gateway_id}/dht22/umidade",
    #                 {**base, "sensor_id": "dht22", "tipo": "umidade",
    #                  "valor": valor, "unidade": "%", "status": "ok"}))

    # ---- Capacitivo: umidade do solo (preparado) ----
    # if fields.get("soil") and fields["soil"] != "err":
    #     bruto = int(fields["soil"])  # 0..1023
    #     SECO, MOLHADO = 800, 350
    #     pct = max(0, min(100, (SECO - bruto) * 100 / (SECO - MOLHADO)))
    #     out.append((f"agro/{gateway_id}/capacitivo/umidade_solo",
    #                 {**base, "sensor_id": "capacitivo", "tipo": "umidade_solo",
    #                  "valor": round(pct, 1), "unidade": "%", "status": "ok"}))

    # ---- BH1750: luminosidade (preparado) ----
    # if fields.get("lux") and fields["lux"] != "err":
    #     valor = float(fields["lux"])
    #     out.append((f"agro/{gateway_id}/bh1750/luminosidade",
    #                 {**base, "sensor_id": "bh1750", "tipo": "luminosidade",
    #                  "valor": valor, "unidade": "lux", "status": "ok"}))

    return out


# =============== buffer local ===============

class LocalSpool:
    def __init__(self, max_messages, spool_path):
        self.queue = deque(maxlen=max_messages)
        self.spool_path = spool_path

    def append(self, topic, payload):
        self.queue.append((topic, payload))
        try:
            with open(self.spool_path, "a") as f:
                f.write(json.dumps({"topic": topic, "payload": payload}) + "\n")
        except OSError as e:
            logging.warning("falha ao escrever no spool: %s", e)

    def __len__(self):
        return len(self.queue)


# =============== cliente MQTT ===============

connected = False

def on_connect(client, userdata, flags, rc, properties=None):
    global connected
    if rc == 0:
        connected = True
        logging.info("MQTT conectado")
    else:
        logging.error("MQTT falhou ao conectar (rc=%s)", rc)

def on_disconnect(client, userdata, rc, properties=None, reason=None):
    global connected
    connected = False
    logging.warning("MQTT desconectado (rc=%s)", rc)


def build_mqtt_client(cfg):
    client_id = cfg["mqtt"]["client_id"]
    client = mqtt.Client(client_id=client_id)
    client.on_connect = on_connect
    client.on_disconnect = on_disconnect
    # last-will: avisa o broker se cairmos abruptamente
    gateway_id = cfg["gateway"]["id"]
    will_topic = f"agro/{gateway_id}/status"
    will_payload = json.dumps({"online": False, "ts": now_iso_utc()})
    client.will_set(will_topic, will_payload, qos=1, retain=True)
    client.connect_async(cfg["mqtt"]["host"], int(cfg["mqtt"]["port"]),
                         keepalive=int(cfg["mqtt"]["keepalive_s"]))
    return client


def publish_or_spool(client, spool, topic, payload, qos):
    msg = json.dumps(payload)
    if connected:
        result = client.publish(topic, msg, qos=qos)
        if result.rc != mqtt.MQTT_ERR_SUCCESS:
            logging.warning("publish falhou (rc=%s) -> spool", result.rc)
            spool.append(topic, payload)
        else:
            # se havia mensagens no buffer, descarrega agora
            drain_spool(client, spool, qos)
    else:
        spool.append(topic, payload)


def drain_spool(client, spool, qos):
    if not spool.queue:
        return
    logging.info("descarregando spool: %d mensagens", len(spool.queue))
    while spool.queue and connected:
        topic, payload = spool.queue.popleft()
        client.publish(topic, json.dumps(payload), qos=qos)


# =============== loop principal ===============

def main():
    cfg = configparser.ConfigParser()
    cfg.read(CFG_PATH)
    setup_logging(cfg["runtime"]["log_level"])

    spool = LocalSpool(int(cfg["buffer"]["max_messages"]),
                       cfg["buffer"]["spool_path"])

    client = build_mqtt_client(cfg)
    client.loop_start()

    backoff = 1
    while True:
        try:
            ser = serial.Serial(
                cfg["serial"]["port"],
                int(cfg["serial"]["baudrate"]),
                timeout=float(cfg["serial"]["read_timeout_s"]),
            )
            logging.info("serial aberta em %s", ser.port)
            backoff = 1
            with ser:
                while True:
                    raw = ser.readline().decode("ascii", errors="ignore")
                    if not raw:
                        continue
                    try:
                        fields = parse_line(raw)
                    except ValueError as e:
                        logging.warning("linha invalida: %s | %r", e, raw)
                        continue
                    payloads = build_payloads(
                        fields,
                        cfg["gateway"]["id"],
                        cfg["gateway"]["site"],
                    )
                    for topic, payload in payloads:
                        publish_or_spool(client, spool, topic, payload,
                                         qos=int(cfg["mqtt"]["qos"]))
                        logging.info("pub %s valor=%s",
                                     topic, payload.get("valor"))
        except serial.SerialException as e:
            logging.error("falha serial: %s | tentando reconectar em %ds", e, backoff)
            time.sleep(backoff)
            backoff = min(backoff * 2, 8)
        except KeyboardInterrupt:
            logging.info("encerrando por sinal do usuario")
            client.loop_stop()
            client.disconnect()
            sys.exit(0)


if __name__ == "__main__":
    main()
