import asyncio
import goodwe
import time
import json
import datetime
import logging
import argparse
import pytz
from prometheus_client import start_http_server, Gauge, Counter

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] (%(threadName)-10s) %(message)s')
logger = logging.getLogger()
LOCALTZ = pytz.timezone("Australia/Melbourne")

success_counter = Counter("inverter_read_success", "Count of successful reads from the inverter")
fail_counter = Counter("inverter_read_fail", "Count of failures to read from inverter")

metrics = {}
fail_count = 0
last_update_ts = 0
last_update_hour = 0

metric_def = {
  "vpv1": {
    "type": "gauge"
  },
  "ipv1": {
    "type": "gauge"
  },
  "ppv1": {
    "type": "gauge"
  },
  "vpv2": {
    "type": "gauge"
  },
  "ipv2": {
    "type": "gauge"
  },
  "ppv2": {
    "type": "gauge"
  },
  "vpv3": {
    "type": "gauge"
  },
  "ipv3": {
    "type": "gauge"
  },
  "ppv3": {
    "type": "gauge"
  },
  "vline1": {
    "type": "gauge"
  },
  "vgrid1": {
    "type": "gauge"
  },
  "fgrid1": {
    "type": "gauge"
  },
  "igrid1": {
    "type": "gauge"
  },
  "pgrid1": {
    "type": "gauge"
  },
  "ppv": {
    "type": "gauge"
  },
  "temperature": {
    "type": "gauge"
  },
  "e_day": {
    "type": "gauge",
    "dontreset": True,
    "midnightreset": True
  },
  "e_total": {
    "type": "counter"
  },
  "h_total": {
    "type": "counter"
  },
  "vbus": {
    "type": "gauge"
  }
}

class DateTimeEncoder(json.JSONEncoder):
  def default(self, z):
    if isinstance(z, datetime.datetime):
      return (str(z))
    else:
      return super().default(z)

async def get_runtime_data(ip_address):
  global fail_count, last_update_ts
  output_dict = {}
  current_update_ts = 0
  current_update_hour = datetime.datetime.now(LOCALTZ).hour

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
        current_update_ts = ts

        if "last_metrics_ts" not in metrics:
          logger.info("Registered last_metrics_ts metric")
          metrics["last_metrics_ts"] = Gauge("last_metrics_ts", "Timestamp of last metrics from inverter")
        metrics["last_metrics_ts"].set(ts)
        
        continue
      if id in metric_def:
        md = metric_def[id]
        if md["type"] == "gauge":
          if id not in metrics:
            metrics[id] = Gauge(id, f"{metric['unit']} {metric['name']}")
            logger.info(f"Registered {id} as a Gauge metric")
          metrics[id].set(metric["value"])
        if md["type"] == "counter":
          unit_mult = 1
          if metric["unit"] == "kWh":
            unit_mult = 1000
          if id not in metrics:
            metrics[id] = Counter(id, f"{metric['unit']} {metric['name']}")
            logger.info(f"Registered {id} as a Counter metric")
            metrics[id].inc(metric["value"] * unit_mult)
          metrics[id].inc((metric["value"] * unit_mult) - metrics[id]._value.get())
    logger.info("Metric update complete")
    success_counter.inc()
    
  except Exception as e:
    fail_count = fail_count + 1
    logger.error(f"Failed to get data from inverter, error = {e}")
    fail_counter.inc()
    if fail_count > 2:
      logger.info("Zeroing metrics due to multiple failures, inverter is likely offline.")
      # we need to reset the gauges except timestamp
      for id, metric in metrics.items():
        if id == "last_metrics_ts":
          continue
        if metric_def[id]["type"] == "gauge":
          # check to see if this gauge should not be reset based on the config
          if "dontreset" not in metric_def[id]:
            logger.info(f"Resetting gauge {id} to 0")
            metrics[id].set(0)
          else:
            logger.info(f"Skipping reset for {id} as dontrest is set")
          # handle reset after midnight
          if "midnightreset" in metric_def[id]:
            if current_update_hour == 0 and last_update_hour == 23:
              logger.info(f"Gauge {id} should reset at midnight and this is the first run past midnight, so resetting")
              metrics[id].set(0)
  
  logger.info(f"Setting last update TS to {current_update_ts}")
  last_update_ts = current_update_ts
  logger.info(f"Setting last_update_hour to {current_update_hour}")
  last_update_hour = current_update_hour

def main():
  global last_update_hour
  parser = argparse.ArgumentParser("goodwe_exporter")
  parser.add_argument("-ip", "--ip-address", help="IP address of the inverter", type=str, required=True)
  args = parser.parse_args()
  last_update_hour = datetime.datetime.now(LOCALTZ).hour
  logger.info(f"Starting with inverter ip = {args.ip_address}, localtime = {datetime.datetime.now(LOCALTZ)}, current hour = {last_update_hour}")
  start_http_server(8080)
  while True:
    asyncio.run(get_runtime_data(args.ip_address))
    time.sleep(30)

if __name__ == "__main__":
    main()