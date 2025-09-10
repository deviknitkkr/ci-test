#!/usr/bin/env python3
"""
Enhanced Load Testing Script for Kubernetes Service
Tests load distribution across pods and HPA scaling behavior
"""

import requests
import time
import threading
import json
import matplotlib.pyplot as plt
from collections import defaultdict, Counter
import subprocess
import sys
from datetime import datetime

class KubernetesLoadTester:
    def __init__(self, service_url, namespace="default", service_name="ci-test"):
        self.service_url = service_url
        self.namespace = namespace
        self.service_name = service_name
        self.results = []
        self.pod_distribution = Counter()
        self.response_times = []
        self.errors = []

    def get_pod_info(self):
        """Get current pod information"""
        try:
            cmd = f"kubectl get pods -n {self.namespace} -l app.kubernetes.io/name={self.service_name} -o json"
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
            if result.returncode == 0:
                pods_data = json.loads(result.stdout)
                return [(pod['metadata']['name'], pod['status']['phase']) for pod in pods_data['items']]
            return []
        except Exception as e:
            print(f"Error getting pod info: {e}")
            return []

    def get_hpa_status(self):
        """Get HPA status"""
        try:
            cmd = f"kubectl get hpa -n {self.namespace} {self.service_name} -o json"
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
            if result.returncode == 0:
                hpa_data = json.loads(result.stdout)
                return {
                    'current_replicas': hpa_data['status'].get('currentReplicas', 0),
                    'desired_replicas': hpa_data['status'].get('desiredReplicas', 0),
                    'current_cpu': hpa_data['status'].get('currentCPUUtilizationPercentage', 0)
                }
            return {}
        except Exception as e:
            print(f"Error getting HPA status: {e}")
            return {}

    def make_request(self, thread_id):
        """Make a single request and record metrics"""
        try:
            start_time = time.time()
            response = requests.get(f"{self.service_url}/ping", timeout=10)
            end_time = time.time()

            response_time = (end_time - start_time) * 1000  # Convert to ms

            # Try to extract pod information from response headers or body
            pod_name = response.headers.get('X-Pod-Name', 'unknown')
            if pod_name == 'unknown' and response.status_code == 200:
                # If no header, use a simple identifier based on timing
                pod_name = f"pod-{hash(response.text + str(response_time)) % 100}"

            result = {
                'thread_id': thread_id,
                'timestamp': time.time(),
                'response_time': response_time,
                'status_code': response.status_code,
                'pod_name': pod_name,
                'success': response.status_code == 200
            }

            self.results.append(result)
            self.response_times.append(response_time)
            self.pod_distribution[pod_name] += 1

        except Exception as e:
            error = {
                'thread_id': thread_id,
                'timestamp': time.time(),
                'error': str(e),
                'success': False
            }
            self.results.append(error)
            self.errors.append(error)

    def run_load_test(self, total_requests=1000, concurrent_threads=50, duration=300):
        """Run the load test"""
        print(f"Starting load test: {total_requests} requests, {concurrent_threads} threads, {duration}s duration")
        print(f"Target URL: {self.service_url}")

        # Get initial pod and HPA status
        initial_pods = self.get_pod_info()
        initial_hpa = self.get_hpa_status()
        print(f"Initial pods: {len(initial_pods)} - {[p[0] for p in initial_pods]}")
        print(f"Initial HPA: {initial_hpa}")

        start_time = time.time()
        threads = []
        request_count = 0

        # Create and start threads
        while time.time() - start_time < duration and request_count < total_requests:
            if len(threads) < concurrent_threads:
                thread = threading.Thread(target=self.make_request, args=(request_count,))
                thread.start()
                threads.append(thread)
                request_count += 1

            # Clean up completed threads
            threads = [t for t in threads if t.is_alive()]
            time.sleep(0.1)  # Small delay to prevent overwhelming

        # Wait for all threads to complete
        for thread in threads:
            thread.join()

        print(f"Load test completed. Total requests: {len(self.results)}")

        # Get final pod and HPA status
        final_pods = self.get_pod_info()
        final_hpa = self.get_hpa_status()
        print(f"Final pods: {len(final_pods)} - {[p[0] for p in final_pods]}")
        print(f"Final HPA: {final_hpa}")

        self.analyze_results()

    def analyze_results(self):
        """Analyze and report results"""
        successful_requests = [r for r in self.results if r.get('success', False)]

        print("\n=== LOAD TEST RESULTS ===")
        print(f"Total requests: {len(self.results)}")
        print(f"Successful requests: {len(successful_requests)}")
        print(f"Failed requests: {len(self.errors)}")
        print(f"Success rate: {len(successful_requests)/len(self.results)*100:.2f}%")

        if self.response_times:
            print(f"\nResponse Times:")
            print(f"Average: {sum(self.response_times)/len(self.response_times):.2f}ms")
            print(f"Min: {min(self.response_times):.2f}ms")
            print(f"Max: {max(self.response_times):.2f}ms")

            # Calculate percentiles
            sorted_times = sorted(self.response_times)
            p50 = sorted_times[int(len(sorted_times) * 0.5)]
            p95 = sorted_times[int(len(sorted_times) * 0.95)]
            p99 = sorted_times[int(len(sorted_times) * 0.99)]
            print(f"P50: {p50:.2f}ms, P95: {p95:.2f}ms, P99: {p99:.2f}ms")

        print(f"\n=== LOAD DISTRIBUTION ===")
        total_pod_requests = sum(self.pod_distribution.values())
        for pod_name, count in self.pod_distribution.most_common():
            percentage = (count / total_pod_requests) * 100
            print(f"{pod_name}: {count} requests ({percentage:.1f}%)")

        # Check if load is evenly distributed
        if len(self.pod_distribution) > 1:
            counts = list(self.pod_distribution.values())
            max_count = max(counts)
            min_count = min(counts)
            distribution_ratio = max_count / min_count if min_count > 0 else float('inf')
            print(f"\nLoad distribution ratio (max/min): {distribution_ratio:.2f}")
            if distribution_ratio > 2.0:
                print("⚠️  WARNING: Load is not evenly distributed across pods!")
                print("   Consider checking service configuration or pod readiness.")
            else:
                print("✅ Load is reasonably well distributed across pods.")

        self.save_results()
        self.plot_results()

    def save_results(self):
        """Save results to JSON file"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"load_test_enhanced_{timestamp}.json"

        report = {
            'timestamp': timestamp,
            'service_url': self.service_url,
            'total_requests': len(self.results),
            'successful_requests': len([r for r in self.results if r.get('success', False)]),
            'failed_requests': len(self.errors),
            'pod_distribution': dict(self.pod_distribution),
            'response_times_ms': self.response_times,
            'detailed_results': self.results
        }

        with open(filename, 'w') as f:
            json.dump(report, f, indent=2)

        print(f"Results saved to: {filename}")

    def plot_results(self):
        """Create visualization plots"""
        if not self.response_times:
            return

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(15, 12))

        # Response time histogram
        ax1.hist(self.response_times, bins=50, alpha=0.7, color='blue')
        ax1.set_xlabel('Response Time (ms)')
        ax1.set_ylabel('Frequency')
        ax1.set_title('Response Time Distribution')
        ax1.grid(True, alpha=0.3)

        # Response time over time
        timestamps = [r['timestamp'] for r in self.results if r.get('success', False)]
        response_times = [r['response_time'] for r in self.results if r.get('success', False)]
        if timestamps and response_times:
            start_time = min(timestamps)
            relative_times = [(t - start_time) for t in timestamps]
            ax2.scatter(relative_times, response_times, alpha=0.6, s=1)
            ax2.set_xlabel('Time (seconds)')
            ax2.set_ylabel('Response Time (ms)')
            ax2.set_title('Response Time Over Time')
            ax2.grid(True, alpha=0.3)

        # Pod distribution pie chart
        if len(self.pod_distribution) > 1:
            pods = list(self.pod_distribution.keys())
            counts = list(self.pod_distribution.values())
            ax3.pie(counts, labels=pods, autopct='%1.1f%%', startangle=90)
            ax3.set_title('Load Distribution Across Pods')
        else:
            ax3.text(0.5, 0.5, 'Single Pod\nDetected', ha='center', va='center', transform=ax3.transAxes)
            ax3.set_title('Load Distribution Across Pods')

        # Requests per second over time
        if timestamps:
            # Group requests by second
            requests_per_second = defaultdict(int)
            for timestamp in timestamps:
                second = int(timestamp - start_time)
                requests_per_second[second] += 1

            seconds = sorted(requests_per_second.keys())
            rps_values = [requests_per_second[s] for s in seconds]

            ax4.plot(seconds, rps_values, marker='o', linewidth=1, markersize=2)
            ax4.set_xlabel('Time (seconds)')
            ax4.set_ylabel('Requests per Second')
            ax4.set_title('Request Rate Over Time')
            ax4.grid(True, alpha=0.3)

        plt.tight_layout()
        plot_filename = f"load_test_enhanced_{timestamp}_plots.png"
        plt.savefig(plot_filename, dpi=300, bbox_inches='tight')
        plt.show()

        print(f"Plots saved to: {plot_filename}")

def main():
    if len(sys.argv) < 2:
        print("Usage: python load_test_enhanced.py <service_url> [namespace] [service_name]")
        print("Example: python load_test_enhanced.py http://localhost:8080 default ci-test")
        sys.exit(1)

    service_url = sys.argv[1].rstrip('/')
    namespace = sys.argv[2] if len(sys.argv) > 2 else "default"
    service_name = sys.argv[3] if len(sys.argv) > 3 else "ci-test"

    tester = KubernetesLoadTester(service_url, namespace, service_name)

    # Run the load test
    # Adjust these parameters as needed
    tester.run_load_test(
        total_requests=2000,    # Total number of requests
        concurrent_threads=20,  # Concurrent requests
        duration=180           # Test duration in seconds
    )

if __name__ == "__main__":
    main()
