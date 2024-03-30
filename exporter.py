import asyncio
import goodwe
import time
import json
import datetime
import logging
import argparse
from prometheus_client import start_http_server, Gauge, Counter

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] (%(threadName)-10s) %(message)s')
logger = logging.getLogger()

metrics = {}
fail_count = 0

metric_def = {
  "vpv1": {
    "type": "guage"
  },
  "ipv1": {
    "type": "guage"
  },
  "ppv1": {
    "type": "guage"
  },
  "vpv2": {
    "type": "guage"
  },
  "ipv2": {
    "type": "guage"
  },
  "ppv2": {
    "type": "guage"
  },
  "vpv3": {
    "type": "guage"
  },
  "ipv3": {
    "type": "guage"
  },
  "ppv3": {
    "type": "guage"
  },
  "vline1": {
    "type": "guage"
  },
  "vgrid1": {
    "type": "guage"
  },
  "fgrid1": {
    "type": "guage"
  },
  "igrid1": {
    "type": "guage"
  },
  "pgrid1": {
    "type": "guage"
  },
  "ppv": {
    "type": "guage"
  },
  "temperature": {
    "type": "guage"
  },
  "e_day": {
    "type": "counter"
  },
  "e_total": {
    "type": "counter"
  },
  "h_total": {
    "type": "counter"
  },
  "vbus": {
    "type": "guage"
  }
}

class DateTimeEncoder(json.JSONEncoder):
  def default(self, z):
    if isinstance(z, datetime.datetime):
      return (str(z))
    else:
      return super().default(z)

async def get_runtime_data(ip_address):
  global fail_count
  output_dict = {}

  try:
    logger.info(f"Attempting to get data from inverter at {ip_address}")
    inverter = await goodwe.connect(ip_address)
    runtime_data = await inverter.read_runtime_data()
    logger.info("Got data from inverter")

    fail_count = 0

    for sensor in inverter.sensors():
      if sensor.id_ in runtime_data:
        output_dict[sensor.id_] = {
          "name": sensor.name,
          "unit": sensor.unit,
          "value": runtime_data[sensor.id_]
        }
    logger.info("Data from inverter %s", json.dumps(output_dict, cls=DateTimeEncoder))

    for id, metric in output_dict.items():
      # need to handle timestamp differently
      if id == "timestamp":
        ts = datetime.datetime.timestamp(metric["value"])
        logger.info(f"Datetime from inverter {metric['value']}; Unix TS = {ts}")

        if "last_metrics_ts" not in metrics:
          logger.info("Registered last_metrics_ts metric")
          metrics["last_metrics_ts"] = Gauge("last_metrics_ts", "Timestamp of last metrics from inverter")
        metrics["last_metrics_ts"].set(ts)
        
        continue
      if id in metric_def:
        md = metric_def[id]
        if md["type"] == "guage":
          if id not in metrics:
            metrics[id] = Gauge(id, f"{metric['unit']} {metric['name']}")
            logger.info(f"Registered {id} as a Guage metric")
          metrics[id].set(metric["value"])
        if md["type"] == "counter":
          unit_mult = 0
          if metric["unit"] == "kWh":
            unit_mult = 1000
          if id not in metrics:
            metrics[id] = Counter(id, f"{metric['unit']} {metric['name']}")
            logger.info(f"Registered {id} as a Counter metric")
            metrics[id].inc(metric["value"] * unit_mult)
          metrics[id].inc((metric["value"] * unit_mult) - metrics[id]._value.get())

  except Exception as e:
    fail_count = fail_count + 1
    logger.error(f"Failed to get data from inverter, error = {e}")
    if fail_count > 2:
      logger.info("Zeroing metrics due to multiple failures, inverter is likely offline.")
      # we need to reset the gauges except timestamp
      for id, metric in metrics.items():
        if id == "last_metrics_ts":
          continue
        if metric_def[id]["type"] == "guage":
          metrics[id].set(0)

def main():
  parser = argparse.ArgumentParser("goodwe_exporter")
  parser.add_argument("-ip", "--ip-address", help="IP address of the inverter", type=str,required=True)
  args = parser.parse_args()
  logger.info(f"Starting with inverter ip = {args.ip_address}")
  start_http_server(8080)
  while True:
    asyncio.run(get_runtime_data(args.ip_address))
    time.sleep(30)

if __name__ == "__main__":
    main()