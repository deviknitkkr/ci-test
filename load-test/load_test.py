#!/usr/bin/env python3
"""
Load Testing Script for Kubernetes Auto-scaling Validation
=========================================================

This script performs load testing on your Spring Boot application to:
1. Test auto-scaling behavior (HPA scaling from 1-5 replicas)
2. Measure performance metrics (latency, TPS)
3. Generate detailed reports

Requirements: pip install requests numpy matplotlib
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
from concurrent.futures import ThreadPoolExecutor
import matplotlib.pyplot as plt

class LoadTester:
    def __init__(self, base_url, duration_minutes=5, max_threads=50):
        self.base_url = base_url.rstrip('/')
        self.duration_seconds = duration_minutes * 60
        self.max_threads = max_threads
        self.running = False
        
        # Metrics storage
        self.response_times = []
        self.successful_requests = 0
        self.failed_requests = 0
        self.status_codes = defaultdict(int)
        self.timestamps = []
        self.start_time = None
        self.end_time = None
        
        # Thread-safe locks
        self.lock = threading.Lock()
        
        # Rate limiting
        self.requests_per_second = []
        self.second_buckets = defaultdict(int)
    
    def signal_handler(self, signum, frame):
        """Handle Ctrl+C gracefully"""
        print(f"\n⚠️  Received signal {signum}. Stopping load test...")
        self.running = False
    
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
    
    async def worker(self, session):
        """Worker coroutine that makes continuous requests"""
        while self.running:
            try:
                await self.make_request(session)
                # Small delay to prevent overwhelming
                await asyncio.sleep(0.01)  # 10ms delay
            except Exception as e:
                print(f"Worker error: {e}")
                await asyncio.sleep(0.1)
    
    async def run_load_test(self):
        """Main load testing function"""
        print(f"🚀 Starting load test...")
        print(f"📊 Target: {self.base_url}")
        print(f"⏱️  Duration: {self.duration_seconds} seconds")
        print(f"🧵 Max concurrent threads: {self.max_threads}")
        print(f"📅 Start time: {datetime.now()}")
        print("-" * 60)
        
        # Setup signal handlers
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)
        
        self.running = True
        self.start_time = time.time()
        
        # Configure aiohttp session
        connector = aiohttp.TCPConnector(limit=100, limit_per_host=50)
        timeout = aiohttp.ClientTimeout(total=10)
        
        async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
            # Create worker tasks
            tasks = []
            for i in range(self.max_threads):
                task = asyncio.create_task(self.worker(session))
                tasks.append(task)
            
            # Monitor progress
            monitor_task = asyncio.create_task(self.monitor_progress())
            
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
    
    async def monitor_progress(self):
        """Monitor and display progress during the test"""
        last_requests = 0
        
        while self.running:
            await asyncio.sleep(10)  # Update every 10 seconds
            
            with self.lock:
                total_requests = self.successful_requests + self.failed_requests
                current_tps = (total_requests - last_requests) / 10
                
                if self.response_times:
                    avg_latency = np.mean(self.response_times[-100:])  # Last 100 requests
                else:
                    avg_latency = 0
                
                elapsed = time.time() - self.start_time
                
                print(f"⏱️  {elapsed:6.1f}s | "
                      f"📊 Total: {total_requests:6d} | "
                      f"✅ Success: {self.successful_requests:6d} | "
                      f"❌ Failed: {self.failed_requests:6d} | "
                      f"🚀 TPS: {current_tps:6.1f} | "
                      f"⚡ Avg Latency: {avg_latency:6.1f}ms")
                
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
            'status_codes': dict(self.status_codes)
        }
        
        return metrics
    
    def print_results(self, metrics):
        """Print detailed test results"""
        print("\\n" + "="*80)
        print("🎯 LOAD TEST RESULTS")
        print("="*80)
        
        print(f"⏱️  Test Duration: {metrics['duration_seconds']:.1f} seconds")
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
        print(f"  Min: {metrics['latency']['min_ms']:.2f} ms")
        print(f"  Max: {metrics['latency']['max_ms']:.2f} ms")
        print(f"  Std Dev: {metrics['latency']['std_dev_ms']:.2f} ms")
        
        print("\\n🚀 THROUGHPUT METRICS:")
        print(f"  Average TPS: {metrics['throughput']['average_tps']:.2f}")
        print(f"  Max TPS: {metrics['throughput']['max_tps']}")
        
        print("\\n📊 STATUS CODES:")
        for code, count in metrics['status_codes'].items():
            print(f"  {code}: {count:,}")
        
        print("="*80)
    
    def save_results(self, metrics, filename_prefix="load_test"):
        """Save results to JSON and generate plots"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Save JSON report
        json_filename = f"{filename_prefix}_{timestamp}.json"
        with open(json_filename, 'w') as f:
            json.dump(metrics, f, indent=2)
        print(f"📄 Results saved to: {json_filename}")
        
        # Generate plots
        self.generate_plots(filename_prefix, timestamp)
    
    def generate_plots(self, filename_prefix, timestamp):
        """Generate performance visualization plots"""
        try:
            import matplotlib.pyplot as plt
            
            fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(15, 10))
            fig.suptitle(f'Load Test Results - {timestamp}', fontsize=16)
            
            # Plot 1: Response time over time
            if self.timestamps and self.response_times:
                relative_times = [(t - self.start_time) / 60 for t in self.timestamps]  # Convert to minutes
                ax1.plot(relative_times, self.response_times, alpha=0.6, markersize=1)
                ax1.set_title('Response Time Over Time')
                ax1.set_xlabel('Time (minutes)')
                ax1.set_ylabel('Response Time (ms)')
                ax1.grid(True)
            
            # Plot 2: Response time histogram
            ax2.hist(self.response_times, bins=50, alpha=0.7, edgecolor='black')
            ax2.set_title('Response Time Distribution')
            ax2.set_xlabel('Response Time (ms)')
            ax2.set_ylabel('Frequency')
            ax2.grid(True)
            
            # Plot 3: TPS over time
            if self.second_buckets:
                seconds = sorted(self.second_buckets.keys())
                tps_values = [self.second_buckets[s] for s in seconds]
                relative_seconds = [(s - min(seconds)) / 60 for s in seconds]
                ax3.plot(relative_seconds, tps_values, marker='o', markersize=2)
                ax3.set_title('Throughput Over Time')
                ax3.set_xlabel('Time (minutes)')
                ax3.set_ylabel('Requests per Second')
                ax3.grid(True)
            
            # Plot 4: Status code distribution
            if self.status_codes:
                codes = list(self.status_codes.keys())
                counts = list(self.status_codes.values())
                ax4.pie(counts, labels=codes, autopct='%1.1f%%')
                ax4.set_title('Status Code Distribution')
            
            plt.tight_layout()
            plot_filename = f"{filename_prefix}_{timestamp}_plots.png"
            plt.savefig(plot_filename, dpi=300, bbox_inches='tight')
            print(f"📊 Plots saved to: {plot_filename}")
            
        except ImportError:
            print("📊 Matplotlib not available. Skipping plot generation.")
            print("    Install with: pip install matplotlib")
        except Exception as e:
            print(f"📊 Error generating plots: {e}")

def main():
    """Main function"""
    print("🔧 Kubernetes Load Tester for Auto-scaling Validation")
    print("="*60)
    
    # Configuration
    # Update this URL to your Kubernetes service endpoint
    # You can get it by running: kubectl port-forward svc/ci-test 8080:8080
    base_url = input("Enter your application URL (e.g., http://localhost:8080): ").strip()
    if not base_url:
        base_url = "http://localhost:8080"
    
    duration = input("Enter test duration in minutes (default: 5): ").strip()
    if not duration:
        duration = 5
    else:
        duration = int(duration)
    
    threads = input("Enter number of concurrent threads (default: 50): ").strip()
    if not threads:
        threads = 50
    else:
        threads = int(threads)
    
    print(f"\\n🎯 Configuration:")
    print(f"   URL: {base_url}")
    print(f"   Duration: {duration} minutes")
    print(f"   Threads: {threads}")
    print("\\n💡 Tip: Run 'kubectl get hpa' in another terminal to watch auto-scaling")
    print("💡 Tip: Run 'kubectl top pods' to see resource usage")
    
    input("\\nPress Enter to start the load test...")
    
    # Run the test
    tester = LoadTester(base_url, duration, threads)
    
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
        print("   Check if your pods scaled up during the test:")
        print("   kubectl get pods")
        print("   kubectl get hpa")
        print("   kubectl top pods")
    else:
        print("❌ No metrics collected. Please check your application URL.")

if __name__ == "__main__":
    main()
