package main

// Prometheus metrics of the machine eagled runs on, read on each scrape, for
// watching a vehicle's computer during a flight: whether it is busy, hot or
// throttling, and how much it sends. They are read with procfs, the library
// node_exporter is built on, so eagled serves them without a node_exporter.
//
//   - eagled_host_cpu_seconds_total, by mode: CPU time of all CPUs.
//   - eagled_host_cpu_frequency_hertz, by cpu: each CPU's current frequency.
//     A drop under load is thermal throttling.
//   - eagled_host_memory_total_bytes and eagled_host_memory_available_bytes.
//   - eagled_host_temperature_celsius, by zone and type: each thermal zone,
//     e.g. the CPUs, GPU and NPU (nspss) of a Qualcomm SoC.
//   - eagled_host_network_receive_bytes_total and
//     eagled_host_network_transmit_bytes_total, by device.

import (
	"github.com/prometheus/client_golang/prometheus"
	"github.com/prometheus/procfs"
	"github.com/prometheus/procfs/sysfs"
	"github.com/rs/zerolog/log"
)

const (
	millidegreesPerDegree = 1000
	hertzPerKilohertz     = 1000
)

var (
	hostCPUSeconds = prometheus.NewDesc("eagled_host_cpu_seconds_total",
		"CPU time of all CPUs, by mode", []string{"mode"}, nil)
	hostCPUFrequency = prometheus.NewDesc("eagled_host_cpu_frequency_hertz",
		"Current frequency of each CPU", []string{"cpu"}, nil)
	hostMemoryTotal = prometheus.NewDesc("eagled_host_memory_total_bytes",
		"Total memory", nil, nil)
	hostMemoryAvailable = prometheus.NewDesc("eagled_host_memory_available_bytes",
		"Memory available to start new programs without swapping", nil, nil)
	hostTemperature = prometheus.NewDesc("eagled_host_temperature_celsius",
		"Temperature of each thermal zone", []string{"zone", "type"}, nil)
	hostNetworkReceive = prometheus.NewDesc("eagled_host_network_receive_bytes_total",
		"Bytes received on each network device", []string{"device"}, nil)
	hostNetworkTransmit = prometheus.NewDesc("eagled_host_network_transmit_bytes_total",
		"Bytes sent on each network device", []string{"device"}, nil)
)

// hostCollector reads the host's metrics on each scrape. A metric it cannot
// read, e.g. one the kernel does not have, is left out, and logged at debug.
type hostCollector struct {
	proc procfs.FS
	sys  sysfs.FS
}

func newHostCollector() (*hostCollector, error) {
	proc, err := procfs.NewDefaultFS()
	if err != nil {
		return nil, err
	}
	sys, err := sysfs.NewDefaultFS()
	if err != nil {
		return nil, err
	}
	return &hostCollector{proc: proc, sys: sys}, nil
}

func (c *hostCollector) Describe(ch chan<- *prometheus.Desc) {
	for _, desc := range []*prometheus.Desc{
		hostCPUSeconds, hostCPUFrequency, hostMemoryTotal, hostMemoryAvailable,
		hostTemperature, hostNetworkReceive, hostNetworkTransmit,
	} {
		ch <- desc
	}
}

func (c *hostCollector) Collect(ch chan<- prometheus.Metric) {
	if stat, err := c.proc.Stat(); err != nil {
		log.Debug().Err(err).Msg("reading CPU time")
	} else {
		cpu := stat.CPUTotal
		for mode, seconds := range map[string]float64{
			"user": cpu.User, "nice": cpu.Nice, "system": cpu.System, "idle": cpu.Idle,
			"iowait": cpu.Iowait, "irq": cpu.IRQ, "softirq": cpu.SoftIRQ, "steal": cpu.Steal,
		} {
			ch <- prometheus.MustNewConstMetric(hostCPUSeconds, prometheus.CounterValue, seconds, mode)
		}
	}

	if cpus, err := c.sys.SystemCpufreq(); err != nil {
		log.Debug().Err(err).Msg("reading CPU frequencies")
	} else {
		for _, cpu := range cpus {
			if cpu.ScalingCurrentFrequency != nil {
				hertz := float64(*cpu.ScalingCurrentFrequency) * hertzPerKilohertz
				ch <- prometheus.MustNewConstMetric(hostCPUFrequency, prometheus.GaugeValue, hertz, cpu.Name)
			}
		}
	}

	if memory, err := c.proc.Meminfo(); err != nil {
		log.Debug().Err(err).Msg("reading memory")
	} else {
		// Meminfo's *Bytes fields are already in bytes.
		if memory.MemTotalBytes != nil {
			ch <- prometheus.MustNewConstMetric(hostMemoryTotal, prometheus.GaugeValue, float64(*memory.MemTotalBytes))
		}
		if memory.MemAvailableBytes != nil {
			ch <- prometheus.MustNewConstMetric(hostMemoryAvailable, prometheus.GaugeValue, float64(*memory.MemAvailableBytes))
		}
	}

	if zones, err := c.sys.ClassThermalZoneStats(); err != nil {
		log.Debug().Err(err).Msg("reading thermal zones")
	} else {
		for _, zone := range zones {
			if zone.ReadErrors != nil {
				continue
			}
			celsius := float64(zone.Temp) / millidegreesPerDegree
			ch <- prometheus.MustNewConstMetric(hostTemperature, prometheus.GaugeValue, celsius, zone.Name, zone.Type)
		}
	}

	if devices, err := c.proc.NetDev(); err != nil {
		log.Debug().Err(err).Msg("reading network devices")
	} else {
		for name, device := range devices {
			ch <- prometheus.MustNewConstMetric(hostNetworkReceive, prometheus.CounterValue, float64(device.RxBytes), name)
			ch <- prometheus.MustNewConstMetric(hostNetworkTransmit, prometheus.CounterValue, float64(device.TxBytes), name)
		}
	}
}
