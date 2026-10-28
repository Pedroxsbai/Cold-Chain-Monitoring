"""Simulate an IoT node: send fake readings to the API like the ESP8266 would.

Replays a whole incident in minutes instead of hours. Standard library only.

Examples:
    python scripts/simulate_node.py --key <API key> --scenario full --interval 10
    python scripts/simulate_node.py --key <API key> --scenario excursion --out-temp 14

Scenarios:
    normal     readings inside the 2–8 °C range
    excursion  normal → out of range → back to normal (opens then ends an incident)
    sensor     normal → invalid sensor readings → normal
    offline    normal → silence (node unplugged) → normal
    full       excursion, then offline

For a fast demo, start the server and the engine with short delays, e.g.:
    NOTIFY_EVERY_MINUTES=0.5 OFFLINE_AFTER_MINUTES=1 TICK_SECONDS=10
"""

import argparse
import json
import os
import random
import sys
import time
import urllib.error
import urllib.request


def send(args, temperature, humidity, sensor_ok=True):
    payload = {
        "device_id": args.device_id,
        "temperature": temperature,
        "humidity": humidity,
        "sensor_ok": sensor_ok,
        "firmware": "simulator",
    }
    request = urllib.request.Request(
        f"{args.url.rstrip('/')}/api/measurements/",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json", "X-Device-Key": args.key},
        method="POST",
    )
    label = f"{temperature} °C / {humidity} %" if sensor_ok else "capteur en défaut"
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            print(f"  → {label:<22} HTTP {response.status}")
    except urllib.error.HTTPError as error:
        print(f"  → {label:<22} HTTP {error.code} {error.read().decode(errors='replace')}")
    except urllib.error.URLError as error:
        sys.exit(f"Serveur injoignable ({error.reason}). Le serveur Django tourne-t-il ?")


def normal(args, count):
    print(f"Mesures normales ({count})")
    for _ in range(count):
        send(args, round(random.uniform(3.5, 6.5), 1), round(random.uniform(40, 55), 1))
        time.sleep(args.interval)


def out_of_range(args, count):
    print(f"Mesures hors plage ({count})")
    for _ in range(count):
        send(args, round(args.out_temp + random.uniform(-0.5, 0.5), 1), 50.0)
        time.sleep(args.interval)


def sensor_failure(args, count):
    print(f"Lectures capteur invalides ({count})")
    for _ in range(count):
        send(args, None, None, sensor_ok=False)
        time.sleep(args.interval)


def silence(args):
    print(f"Silence de {args.silence} s (nœud débranché)")
    time.sleep(args.silence)


SCENARIOS = {
    "normal": lambda a: normal(a, a.count),
    "excursion": lambda a: (normal(a, 2), out_of_range(a, a.count), normal(a, 2)),
    "sensor": lambda a: (normal(a, 2), sensor_failure(a, a.count), normal(a, 2)),
    "offline": lambda a: (normal(a, 2), silence(a), normal(a, 2)),
    "full": lambda a: (
        normal(a, 2),
        out_of_range(a, a.count),
        normal(a, 2),
        silence(a),
        normal(a, 2),
    ),
}


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--url", default="http://127.0.0.1:8000")
    parser.add_argument("--device-id", default="FRIGO-LAB-01")
    parser.add_argument("--key", default=os.environ.get("DEVICE_KEY"), help="ou DEVICE_KEY")
    parser.add_argument("--scenario", choices=SCENARIOS, default="full")
    parser.add_argument("--interval", type=float, default=10, help="secondes entre 2 mesures")
    parser.add_argument("--count", type=int, default=6, help="mesures dans la phase testée")
    parser.add_argument("--out-temp", type=float, default=12.0, help="température hors plage")
    parser.add_argument("--silence", type=float, default=120, help="durée du silence (s)")
    args = parser.parse_args()
    if not args.key:
        parser.error("clé du nœud manquante : --key ou variable DEVICE_KEY")

    print(f"Nœud simulé {args.device_id} → {args.url} (scénario {args.scenario})")
    SCENARIOS[args.scenario](args)
    print("Terminé.")


if __name__ == "__main__":
    main()
