# Design for Experiments with Fio 

For these experiments, we will create a design for experiments that
demonstrate measuring IO stats for FIO. We will be emulating [this design](https://juicefs.com/docs/cloud/single_node_benchmark/)
for single node benchmarks. You can read more about Fio [here](https://fio.readthedocs.io/en/latest/fio_doc.html#i-o-size).
We will be using the [FIO metric](https://converged-computing.github.io/metrics-operator/getting_started/metrics.html#fio) of the Metrics operator. 

## Design

We will use a [single node benchmark](https://juicefs.com/docs/cloud/single_node_benchmark/) design, and note that a lot of my learning and description is from reading that post. In this section, we will overview the design types, and then applications (and examples) that use each one, first for generic and then (hopefully) for HPC. To define some terms:

 - sequential: reading in an ordered fashion
 - random: reading in a random fashion
 - concurrent: reading different slices or collections at the same time
 
I need to improve these, still trying to understand myself :)
The storage backends I want to test:

 - Filestore (implemented, working)
 - Fusion (implemented, working)
 - CSI to Google Storage (implemented, working)

Maybe, if I can get them working...

 - Alluxio Filesystem (maybe)
 - CephFS (maybe)
 - JuiceFS (maybe)

### Reading and Writing Big Files

> Large file sequential reading and writing.

Examples include collecting logs, backing up data, or more generally, large file reading and writing.
In these cases, block size is really important -

> block size is the main factor affecting sequential read and write throughput. The larger the block size, the stronger the sequential read and write throughput

And the above should show up in results. Sequential means "in a row" and concurrent means at the same time. Example commands for fio looks like:

```bash
# large file sequential read
fio --name=big-file-sequential-read --directory=/jfs --rw=read --refill_buffers --bs=256k --size=4G

# large file sequential write
fio --name=big-file-sequential-write --directory=/jfs --rw=write --refill_buffers --bs=256k --size=4G 

# large file concurrent read
fio --name=big-file-multi-read --directory=/jfs --rw=read --refill_buffers --bs=256k --size=4G --numjobs={1, 2, 4, 8, 16}

# large file concurrent write
fio --name=big-file-multi-write --directory=/jfs --rw=write --refill_buffers --bs=256k --size=4G --numjobs={1, 2, 4, 8, 16}

# large file random write
fio --name=big-file-random-write --directory=/jfs --rw=randwrite --refill_buffers --size=4G --bs={4k, 16k, 64k, 256k}
```

We are interested to see if there is a concurrent write limit for cloud storage solutions.
E.g., for JuiceFS:

> Concurrent write in a single process has already reached the bandwidth limit of AWS EC2 and S3 with 600MB/s. To further exploit the advantages of JuiceFS, it is recommended to use a multi-machine parallel approach, especially in big data computing scenarios.

```bash
# large file random read
fio --name=big-file-rand-read --directory=/jfs --rw=randread --refill_buffers --size=4G --filename=randread.bin --bs={4k, 16k, 64k, 256k} --pre_read=1
sync && echo 3 > /proc/sys/vm/drop_caches
fio --name=big-file-rand-read --directory=/jfs --rw=randread --refill_buffers --size=4G --filename=randread.bin --bs={4k, 16k, 64k, 256k}
```

From the JuiceFS page:

> In order to accurately test the performance of large file random read, here we first pre-read the file using fio, then drop the kernel cache (including PageCache, dentries, inodes cache), and then use fio to perform random read test.

### Reading and Writing Small Files

```bash
# Small file sequential read
fio --name=small-file-seq-read --directory=/jfs --rw=read --file_service_type=sequential --bs={file_size} --filesize={file_size} --nrfiles=1000 

# Small file sequential write
fio --name=small-file-seq-write --directory=/jfs --rw=write --file_service_type=sequential --bs={file_size} --filesize={file_size} --nrfiles=1000 

# Small file concurrent read
fio --name=small-file-multi-read --directory=/jfs --rw=read --file_service_type=sequential --bs=4k --filesize=4k --nrfiles=1000 --numjobs={1, 2, 4, 8, 16}

# Small file concurrent write
fio --name=small-file-multi-write --directory=/jfs --rw=write --file_service_type=sequential --bs=4k --filesize=4k --nrfiles=1000 --numjobs={1, 2, 4, 8, 16}
```

### Possible Tips

- The *way* that you do the bind can influence the application performance depending on the IO pattern, so looking at your IO pattern and figuring out the best way to bind is a good strategy.
- (from JuiceFS) In the scenario where frequently read large files randomly, for better performance, it is recommended to set the cache size of the mount parameter to be larger than the file size to be read.
- (from JuiceFS) When a local cache is used, can greatly improve number of small files read per unit time.

## Usage

### 1. Create the Cluster

From [run0](../run0) we saw that instance size didn't really matter, so we are going to stick with a reasonably sized
one, albeit not as large as it could be. I'd like to still test a few sizes with this new design until I'm convinced the
size does not matter.

 - c2d-standard-2
 - c2d-standard-16
 - c2d-standard-64 
 

Under development, coming soon!
