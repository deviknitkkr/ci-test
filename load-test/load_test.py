#!/usr/bin/env python3
"""
Incremental Load Testing Script
=====================================================================

This script performs incremental load testing on your Spring Boot application to:
1. Test auto-scaling behavior with gradual TPS ramping
2. Measure performance metrics (current TPS, avg latency, P90 latency)
3. Generate smooth time-series graphs for reporting

Requirements: pip install requests numpy matplotlib aiohttp
"""

import asyncio
import aiohttp
import time
import threading
import numpy as np
import json
import signal
import sys
from datetime import datetime, timedelta
from collections import defaultdict
import matplotlib.pyplot as plt

class IncrementalLoadTester:
    def __init__(self, base_url, duration_minutes=10, initial_tps=100, delta_time_minutes=1, delta_tps=50):
        self.base_url = base_url.rstrip('/')
        self.duration_seconds = duration_minutes * 60
        self.initial_tps = initial_tps
        self.delta_time_seconds = delta_time_minutes * 60
        self.delta_tps = delta_tps
        self.running = False
        
        # Current TPS tracking
        self.current_target_tps = initial_tps
        self.last_tps_increase = 0

        # Metrics storage with timestamps for incremental analysis
        self.response_times = []
        self.successful_requests = 0
        self.failed_requests = 0
        self.status_codes = defaultdict(int)
        self.timestamps = []
        self.start_time = None
        self.end_time = None
        
        # Time-series data for smooth plotting
        self.time_series_data = {
            'timestamps': [],
            'current_tps': [],
            'avg_latency': [],
            'p90_latency': [],
            'target_tps': [],
            'success_rate': []
        }

        # Thread-safe locks
        self.lock = threading.Lock()
        
        # Rate limiting
        self.requests_per_second = []
        self.second_buckets = defaultdict(int)
        self.active_workers = 0

        # Dynamic worker pool
        self.worker_semaphore = asyncio.Semaphore(1000)  # Max workers limit

    def signal_handler(self, signum, frame):
        """Handle Ctrl+C gracefully"""
        print(f"\n⚠️  Received signal {signum}. Stopping load test...")
        self.running = False

    def get_current_target_tps(self):
        """Calculate current target TPS based on elapsed time"""
        if not self.start_time:
            return self.initial_tps

        elapsed = time.time() - self.start_time
        intervals_passed = int(elapsed // self.delta_time_seconds)
        return self.initial_tps + (intervals_passed * self.delta_tps)

    def calculate_delay_for_tps(self, target_tps):
        """Calculate delay between requests to achieve target TPS"""
        if target_tps <= 0:
            return 1.0
        return 1.0 / target_tps

    async def make_request(self, session, endpoint="/ping"):
        """Make a single HTTP request"""
        url = f"{self.base_url}{endpoint}"
        start_time = time.time()

        try:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as response:
                await response.text()  # Read response body
                end_time = time.time()
                response_time = (end_time - start_time) * 1000  # Convert to ms
                
                with self.lock:
                    self.response_times.append(response_time)
                    self.timestamps.append(time.time())
                    self.status_codes[response.status] += 1
                    
                    # Count requests per second
                    current_second = int(time.time())
                    self.second_buckets[current_second] += 1
                    
                    if response.status == 200:
                        self.successful_requests += 1
                    else:
                        self.failed_requests += 1
                
                return response_time, response.status
                
        except Exception as e:
            end_time = time.time()
            response_time = (end_time - start_time) * 1000
            
            with self.lock:
                self.failed_requests += 1
                self.status_codes['error'] += 1
                
            return response_time, 'error'

    async def controlled_worker(self, session, worker_id):
        """Worker that controls request rate based on target TPS"""
        async with self.worker_semaphore:
            self.active_workers += 1
            try:
                while self.running:
                    current_target = self.get_current_target_tps()
                    delay = self.calculate_delay_for_tps(current_target / max(1, self.active_workers))

                    await self.make_request(session)
                    await asyncio.sleep(delay)

            except Exception as e:
                print(f"Worker {worker_id} error: {e}")
            finally:
                self.active_workers -= 1

    def collect_time_series_data(self):
        """Collect current metrics for time series plotting"""
        current_time = time.time()
        elapsed = current_time - self.start_time

        with self.lock:
            # Calculate current TPS (last 10 seconds)
            recent_cutoff = current_time - 10
            recent_timestamps = [t for t in self.timestamps if t >= recent_cutoff]
            current_tps = len(recent_timestamps) / 10 if recent_timestamps else 0

            # Calculate recent latency metrics
            recent_response_times = []
            for i, timestamp in enumerate(self.timestamps):
                if timestamp >= recent_cutoff:
                    recent_response_times.append(self.response_times[i])

            avg_latency = np.mean(recent_response_times) if recent_response_times else 0
            p90_latency = np.percentile(recent_response_times, 90) if len(recent_response_times) >= 10 else 0

            # Calculate success rate
            total_requests = self.successful_requests + self.failed_requests
            success_rate = (self.successful_requests / total_requests * 100) if total_requests > 0 else 0

            # Store time series data
            self.time_series_data['timestamps'].append(elapsed / 60)  # Convert to minutes
            self.time_series_data['current_tps'].append(current_tps)
            self.time_series_data['avg_latency'].append(avg_latency)
            self.time_series_data['p90_latency'].append(p90_latency)
            self.time_series_data['target_tps'].append(self.get_current_target_tps())
            self.time_series_data['success_rate'].append(success_rate)

    async def run_load_test(self):
        """Main load testing function with incremental TPS ramping"""
        print(f"🚀 Starting incremental load test...")
        print(f"📊 Target: {self.base_url}")
        print(f"⏱️  Duration: {self.duration_seconds} seconds ({self.duration_seconds/60:.1f} minutes)")
        print(f"🎯 Initial TPS: {self.initial_tps}")
        print(f"⏰ TPS increase interval: {self.delta_time_seconds} seconds ({self.delta_time_seconds/60:.1f} minutes)")
        print(f"📈 TPS increase step: {self.delta_tps}")
        print(f"🏁 Final target TPS: {self.initial_tps + ((self.duration_seconds // self.delta_time_seconds) * self.delta_tps)}")
        print(f"📅 Start time: {datetime.now()}")
        print("-" * 80)

        # Setup signal handlers
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)
        
        self.running = True
        self.start_time = time.time()
        
        # Configure aiohttp session
        connector = aiohttp.TCPConnector(limit=1000, limit_per_host=500)
        timeout = aiohttp.ClientTimeout(total=10)
        
        async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
            # Create controlled worker tasks
            max_workers = min(500, self.initial_tps + ((self.duration_seconds // self.delta_time_seconds) * self.delta_tps))
            tasks = []

            for i in range(max_workers):
                task = asyncio.create_task(self.controlled_worker(session, i))
                tasks.append(task)
            
            # Monitor progress with time series collection
            monitor_task = asyncio.create_task(self.monitor_incremental_progress())

            # Wait for duration or interruption
            try:
                await asyncio.sleep(self.duration_seconds)
            except KeyboardInterrupt:
                print("\\n⚠️  Load test interrupted by user")
            
            # Stop all workers
            self.running = False
            self.end_time = time.time()
            
            # Cancel all tasks
            for task in tasks + [monitor_task]:
                task.cancel()
            
            # Wait for tasks to complete
            await asyncio.gather(*tasks, monitor_task, return_exceptions=True)

    async def monitor_incremental_progress(self):
        """Monitor and display progress with TPS ramping information"""
        last_requests = 0
        last_target_tps = self.initial_tps

        while self.running:
            await asyncio.sleep(5)  # Update every 5 seconds for more responsive monitoring

            current_target_tps = self.get_current_target_tps()

            # Collect time series data
            self.collect_time_series_data()

            with self.lock:
                total_requests = self.successful_requests + self.failed_requests
                current_actual_tps = (total_requests - last_requests) / 5  # 5-second window

                # Calculate recent latency metrics
                recent_response_times = self.response_times[-50:] if len(self.response_times) >= 50 else self.response_times
                avg_latency = np.mean(recent_response_times) if recent_response_times else 0
                p90_latency = np.percentile(recent_response_times, 90) if len(recent_response_times) >= 10 else 0

                elapsed = time.time() - self.start_time
                success_rate = (self.successful_requests / total_requests * 100) if total_requests > 0 else 0

                # Show TPS increase notification
                if current_target_tps != last_target_tps:
                    print(f"🎯 TPS TARGET INCREASED: {last_target_tps} → {current_target_tps}")
                    last_target_tps = current_target_tps

                print(f"⏱️  {elapsed:6.1f}s | "
                      f"🎯 Target: {current_target_tps:4.0f} | "
                      f"🚀 Actual: {current_actual_tps:6.1f} | "
                      f"✅ {self.successful_requests:6d} | "
                      f"❌ {self.failed_requests:4d} | "
                      f"📊 {success_rate:5.1f}% | "
                      f"⚡ Avg: {avg_latency:5.1f}ms | "
                      f"📈 P90: {p90_latency:5.1f}ms")

                last_requests = total_requests
    
    def calculate_metrics(self):
        """Calculate and return performance metrics"""
        if not self.response_times:
            return None
        
        total_requests = self.successful_requests + self.failed_requests
        duration = self.end_time - self.start_time
        
        # Calculate percentiles
        p50 = np.percentile(self.response_times, 50)
        p90 = np.percentile(self.response_times, 90)
        p95 = np.percentile(self.response_times, 95)
        p99 = np.percentile(self.response_times, 99)
        
        # Calculate TPS metrics
        tps_average = total_requests / duration
        tps_values = list(self.second_buckets.values())
        tps_max = max(tps_values) if tps_values else 0
        
        # Error rate
        error_rate = (self.failed_requests / total_requests * 100) if total_requests > 0 else 0
        
        metrics = {
            'test_config': {
                'initial_tps': self.initial_tps,
                'delta_time_seconds': self.delta_time_seconds,
                'delta_tps': self.delta_tps,
                'duration_seconds': duration
            },
            'duration_seconds': duration,
            'total_requests': total_requests,
            'successful_requests': self.successful_requests,
            'failed_requests': self.failed_requests,
            'error_rate_percent': error_rate,
            'latency': {
                'average_ms': np.mean(self.response_times),
                'median_ms': p50,
                'p90_ms': p90,
                'p95_ms': p95,
                'p99_ms': p99,
                'min_ms': np.min(self.response_times),
                'max_ms': np.max(self.response_times),
                'std_dev_ms': np.std(self.response_times)
            },
            'throughput': {
                'average_tps': tps_average,
                'max_tps': tps_max
            },
            'status_codes': dict(self.status_codes),
            'time_series': self.time_series_data
        }
        
        return metrics

    def print_results(self, metrics):
        """Print detailed test results"""
        print("\\n" + "="*80)
        print("🎯 INCREMENTAL LOAD TEST RESULTS")
        print("="*80)
        
        config = metrics['test_config']
        print(f"📈 Test Configuration:")
        print(f"   Initial TPS: {config['initial_tps']}")
        print(f"   TPS Increase Interval: {config['delta_time_seconds']}s ({config['delta_time_seconds']/60:.1f}min)")
        print(f"   TPS Increase Step: {config['delta_tps']}")
        print(f"   Total Duration: {config['duration_seconds']:.1f}s ({config['duration_seconds']/60:.1f}min)")

        print(f"\\n⏱️  Test Duration: {metrics['duration_seconds']:.1f} seconds")
        print(f"📊 Total Requests: {metrics['total_requests']:,}")
        print(f"✅ Successful: {metrics['successful_requests']:,}")
        print(f"❌ Failed: {metrics['failed_requests']:,}")
        print(f"📉 Error Rate: {metrics['error_rate_percent']:.2f}%")
        
        print("\\n📈 LATENCY METRICS:")
        print(f"  Average: {metrics['latency']['average_ms']:.2f} ms")
        print(f"  Median (P50): {metrics['latency']['median_ms']:.2f} ms")
        print(f"  P90: {metrics['latency']['p90_ms']:.2f} ms")
        print(f"  P95: {metrics['latency']['p95_ms']:.2f} ms")
        print(f"  P99: {metrics['latency']['p99_ms']:.2f} ms")

        print("\\n🚀 THROUGHPUT METRICS:")
        print(f"  Average TPS: {metrics['throughput']['average_tps']:.2f}")
        print(f"  Max TPS: {metrics['throughput']['max_tps']}")
        
        print("\\n📊 STATUS CODES:")
        for code, count in metrics['status_codes'].items():
            print(f"  {code}: {count:,}")
        
        if metrics['time_series']['current_tps']:
            final_tps = metrics['time_series']['current_tps'][-1]
            final_avg_latency = metrics['time_series']['avg_latency'][-1]
            final_p90_latency = metrics['time_series']['p90_latency'][-1]
            print(f"\\n📊 FINAL METRICS:")
            print(f"  Final Actual TPS: {final_tps:.2f}")
            print(f"  Final Avg Latency: {final_avg_latency:.2f} ms")
            print(f"  Final P90 Latency: {final_p90_latency:.2f} ms")

        print("="*80)

    def save_results(self, metrics, filename_prefix="incremental_load_test"):
        """Save results to JSON and generate plots"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Save JSON report
        json_filename = f"{filename_prefix}_{timestamp}.json"
        with open(json_filename, 'w') as f:
            json.dump(metrics, f, indent=2)
        print(f"📄 Results saved to: {json_filename}")

        # Generate smooth plots
        self.generate_smooth_plots(filename_prefix, timestamp)

    def generate_smooth_plots(self, filename_prefix, timestamp):
        """Generate smooth time-series plots for incremental load testing"""
        try:
            import matplotlib.pyplot as plt
            import numpy as np

            # Create figure with 3 subplots for the key metrics
            fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(12, 15))
            fig.suptitle(f'Incremental Load Test - {timestamp}', fontsize=16, fontweight='bold')

            if not self.time_series_data['timestamps']:
                print("📊 No time series data available for plotting")
                return

            times = np.array(self.time_series_data['timestamps'])

            # Plot 1: TPS Comparison (Target vs Actual)
            target_tps = np.array(self.time_series_data['target_tps'])
            actual_tps = np.array(self.time_series_data['current_tps'])

            ax1.plot(times, target_tps, 'b-', linewidth=2, label='Target TPS', alpha=0.8)
            ax1.plot(times, actual_tps, 'r-', linewidth=2, label='Actual TPS', alpha=0.8)
            ax1.fill_between(times, target_tps, alpha=0.2, color='blue')
            ax1.fill_between(times, actual_tps, alpha=0.2, color='red')

            ax1.set_title('🎯 TPS Ramping: Target vs Actual', fontsize=14, fontweight='bold')
            ax1.set_xlabel('Time (minutes)')
            ax1.set_ylabel('Transactions Per Second')
            ax1.legend()
            ax1.grid(True, alpha=0.3)
            ax1.set_ylim(bottom=0)

            # Plot 2: Latency Metrics (Average and P90)
            avg_latency = np.array(self.time_series_data['avg_latency'])
            p90_latency = np.array(self.time_series_data['p90_latency'])

            ax2.plot(times, avg_latency, 'g-', linewidth=2, label='Average Latency', alpha=0.8)
            ax2.plot(times, p90_latency, 'orange', linewidth=2, label='P90 Latency', alpha=0.8)
            ax2.fill_between(times, avg_latency, alpha=0.2, color='green')
            ax2.fill_between(times, p90_latency, alpha=0.2, color='orange')

            ax2.set_title('⚡ Response Time Trends', fontsize=14, fontweight='bold')
            ax2.set_xlabel('Time (minutes)')
            ax2.set_ylabel('Latency (ms)')
            ax2.legend()
            ax2.grid(True, alpha=0.3)
            ax2.set_ylim(bottom=0)

            # Plot 3: Success Rate
            success_rate = np.array(self.time_series_data['success_rate'])

            ax3.plot(times, success_rate, 'purple', linewidth=2, label='Success Rate', alpha=0.8)
            ax3.fill_between(times, success_rate, alpha=0.2, color='purple')
            ax3.axhline(y=95, color='red', linestyle='--', alpha=0.7, label='95% Threshold')

            ax3.set_title('📊 Success Rate Over Time', fontsize=14, fontweight='bold')
            ax3.set_xlabel('Time (minutes)')
            ax3.set_ylabel('Success Rate (%)')
            ax3.legend()
            ax3.grid(True, alpha=0.3)
            ax3.set_ylim(0, 105)

            plt.tight_layout()
            plot_filename = f"{filename_prefix}_{timestamp}_smooth_plots.png"
            plt.savefig(plot_filename, dpi=300, bbox_inches='tight')
            print(f"📊 Smooth plots saved to: {plot_filename}")

        except ImportError as e:
            print(f"📊 Missing required libraries for smooth plotting: {e}")
            print("    Install with: pip install matplotlib scipy")
        except Exception as e:
            print(f"📊 Error generating smooth plots: {e}")

def main():
    """Main function"""
    print("🚀 Incremental Load Tester for Kubernetes Auto-scaling")
    print("="*60)

    # Configuration
    base_url = input("Enter your application URL (e.g., http://localhost:9080): ").strip()
    if not base_url:
        base_url = "http://localhost:9080"

    print("\\n📈 Incremental Load Test Configuration:")

    duration = input("Enter total test duration in minutes (default: 10): ").strip()
    duration = int(duration) if duration else 10

    initial_tps = input("Enter initial TPS (default: 100): ").strip()
    initial_tps = int(initial_tps) if initial_tps else 100

    delta_time = input("Enter TPS increase interval in minutes (default: 1): ").strip()
    delta_time = int(delta_time) if delta_time else 1

    delta_tps = input("Enter TPS increase step (default: 50): ").strip()
    delta_tps = int(delta_tps) if delta_tps else 50

    final_tps = initial_tps + ((duration * 60) // (delta_time * 60)) * delta_tps

    print(f"\\n🎯 Test Plan Summary:")
    print(f"   📊 URL: {base_url}")
    print(f"   ⏱️  Duration: {duration} minutes")
    print(f"   🚀 Initial TPS: {initial_tps}")
    print(f"   ⏰ Increase every: {delta_time} minute(s)")
    print(f"   📈 Increase by: {delta_tps} TPS")
    print(f"   🏁 Final TPS: ~{final_tps}")
    print("\\n💡 Monitor: kubectl get hpa && kubectl get pods")

    input("\\nPress Enter to start the incremental load test...")

    # Run the test
    tester = IncrementalLoadTester(base_url, duration, initial_tps, delta_time, delta_tps)

    try:
        asyncio.run(tester.run_load_test())
    except KeyboardInterrupt:
        print("\\n⚠️  Test interrupted by user")

    # Calculate and display results
    metrics = tester.calculate_metrics()
    if metrics:
        tester.print_results(metrics)
        tester.save_results(metrics)

        print("\\n🎯 AUTO-SCALING VERIFICATION:")
        print("   kubectl get pods -o wide")
        print("   kubectl get hpa")
        print("   kubectl top pods")
    else:
        print("❌ No metrics collected. Please check your application URL.")

if __name__ == "__main__":
    main()
