# goodwe-exporter

This is a very simple application which scrapes metrics from a Goodwe solar inverter and exposes a metrics endpoint which can be scraped by Prometheus.

It requires a single parameter when it is run to tell it the IP address of the inverter.

For example

```{shell}
# these lines only needed for initial install
python -m venv .env
source .env/bin/activate
pip install -r requirements.txt

# this command runs the script
python exporter.py -ip <IP_ADDRESS>
```

The metrics are exposed on port 8080 at the server root

e.g. `http://<ip>:8080/`

## Notes

* The code will 0 all the gauge metrics once the inverter is unreachable 3 times in a row - as it is assumed that the inverter is offline (as there is no daylight)
* the `e_day` which is the kWh of generation for the day is automatically reset to 0 at midnight
* The timezone is hard coded to Australia/Melbourne, an improvement would be make this a command line parameter
* The script scrapes for metrics every 30 seconds, again an improvement would be to make this a command line parameter
