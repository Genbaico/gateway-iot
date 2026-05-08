# Gateway IoT — Projeto Final SO Embarcados (FACAMP)

Gateway local em Raspberry Pi 3 que lê sensores ambientais via Arduino,
estrutura os dados em JSON e publica via MQTT para monitoramento de estufa.

## Hardware

- Raspberry Pi 3 Model B (Debian GNU/Linux 13 trixie, kernel 6.12.75+rpt-rpi-v8)
- Arduino Uno conectado por USB
- Sensores: DS18B20 (ativo nesta etapa), DHT22, capacitivo de solo e BH1750 (previstos)

## Estrutura do repositório

- `arduino/gateway_sensors/` — firmware do Arduino
- `gateway/` — script Python e configuração-modelo
- `systemd/` — arquivo de unidade do serviço
- `docs/` — documentos das entregas (Etapas 1, 2 e 3)
- `evidencias/` — prints e fotos das validações

## Tópicos MQTT

- `agro/gw01/ds18b20/temperatura_solo`
- `agro/gw01/dht22/temperatura` (previsto)
- `agro/gw01/dht22/umidade` (previsto)
- `agro/gw01/capacitivo/umidade_solo` (previsto)
- `agro/gw01/bh1750/luminosidade` (previsto)
- `agro/gw01/status` (heartbeat / last-will)
- `agro/gw01/eventos` (reconexões, descargas de buffer)

## Como rodar no Raspberry Pi

```bash
sudo apt update
sudo apt install -y mosquitto mosquitto-clients python3-serial python3-paho-mqtt

sudo mkdir -p /opt/gateway-iot /etc/gateway-iot /var/lib/gateway-iot
sudo chown pi:pi /opt/gateway-iot /var/lib/gateway-iot

sudo cp gateway/gateway_serial_mqtt.py /opt/gateway-iot/
sudo cp gateway/config.example.ini /etc/gateway-iot/config.ini
sudo cp systemd/gateway-iot.service /etc/systemd/system/

sudo systemctl daemon-reload
sudo systemctl enable --now gateway-iot
sudo systemctl status gateway-iot
```

## Validação

```bash
journalctl -u gateway-iot -f
mosquitto_sub -h localhost -t 'agro/gw01/#' -v
```

## Equipe

- Henrique Radi — 202410144
- Rafael Rodrigues — 202410262
- Pedro Rovere — 202410039

## Disciplina

Sistemas Operacionais Embarcados — FACAMP — Prof. Nivaldo T. Marcusso — 2026
