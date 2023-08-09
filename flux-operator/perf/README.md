# Performance Flux Operator Python

Here we will test running sysstat (pidstat) on the Flux Operator entrypoint.
We are running LAMMPS and want to get data from all pods,
and see if the top level entrypoint (that runs flux) also contains signal
for LAMMPS. To run this example you will need to instal the Metrics Operator,
JobSet, along with generate and apply the config map files in [flux-operator](../).

```bash
$ python run-metric.py
```

The script will use the metricsoperator library to submit the [metrics.yaml](metrics.yaml)
and then wait for the pod to complete and parse the output in the log. Note that I need
to carefully look over the data and plots and decide what is important, so I'm
not linking any here.

