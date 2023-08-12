# OSU Benchmark Experiments

Here we wanted to try using [sole tenant nodes](https://cloud.google.com/kubernetes-engine/docs/how-to/sole-tenancy) with
the OSU Benchmarks. I couldn't get the sole tenancy to work (see link below) but I did a run without it.

## 1. Create Node Templates

See sole-tenant nodes available. I was interested in c2 and c3 in central:

```bash
$ gcloud compute sole-tenancy node-types list|grep c3 | grep central
c3-node-176-1408   us-central1-a              176   1441792
c3-node-176-352    us-central1-a              176   360448
c3-node-176-704    us-central1-a              176   720896
c3-node-176-1408   us-central1-b              176   1441792
c3-node-176-352    us-central1-b              176   360448
c3-node-176-704    us-central1-b              176   720896
c3-node-176-1408   us-central1-c              176   1441792
c3-node-176-352    us-central1-c              176   360448
c3-node-176-704    us-central1-c              176   720896
c3-node-176-352    us-central1-d              176   360448

$ gcloud compute sole-tenancy node-types list|grep c2 | grep central
c2-node-60-240     us-central1-a              60    245760
c2-node-60-240     us-central1-b              60    245760
c2-node-60-240     us-central1-c              60    245760
c2-node-60-240     us-central1-f              60    245760
```

We know that c3 has the lowest latency of the set (~45 microseconds from an unrelated experiment) so
let's try that first.

- c3-node-176-352

See the corresponding directory for full instructions.

 - **c3-node-176-352**: TBA - this was an epic failure to get sole tenancy nodes. See [this gist](https://gist.github.com/vsoch/6e049bbd26e59be62e152bb0b99db55c).
 - [c3-standard-176](c3-standard-176): ran the OSU benchmarks on c3-standard-176. Was the node size overkill? Yes. But I figure if we should try to be consistent for future experiments.
