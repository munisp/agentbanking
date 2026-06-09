"""
Load Test Monitoring and Reporting Script
Remittance Platform V11.0

Real-time monitoring and reporting for load tests.

Usage:
    python3 monitor_load_test.py --duration 3600 --output report.html

Author: Manus AI
Date: November 11, 2025
"""

import os
import sys
import time
import argparse
from datetime import datetime
import asyncpg
import psutil
import json


DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://workflow_service:password@localhost:5432/remittance_platform"
)


class LoadTestMonitor:
    """Monitor load test metrics and generate reports."""
    
    def __init__(self, duration: int, interval: int = 10):
        """
        Initialize monitor.
        
        Args:
            duration: Total monitoring duration in seconds
            interval: Sampling interval in seconds
        """
        self.duration = duration
        self.interval = interval
        self.metrics = []
        self.start_time = None
    
    async def collect_metrics(self):
        """Collect metrics from database and system."""
        conn = await asyncpg.connect(DATABASE_URL)
        
        try:
            # Database metrics
            db_stats = await conn.fetchrow("""
                SELECT 
                    (SELECT count(*) FROM pg_stat_activity WHERE state = 'active') as active_connections,
                    (SELECT count(*) FROM pg_stat_activity) as total_connections,
                    (SELECT sum(numbackends) FROM pg_stat_database) as backends
            """)
            
            # Workflow metrics
            workflow_stats = await conn.fetchrow("""
                SELECT 
                    COUNT(*) as total_workflows,
                    COUNT(*) FILTER (WHERE created_at >= NOW() - INTERVAL '1 minute') as workflows_last_minute
                FROM override_commissions
                WHERE created_at >= $1
            """, self.start_time)
            
            # Hierarchy metrics
            hierarchy_stats = await conn.fetchrow("""
                SELECT 
                    COUNT(*) as total_agents,
                    AVG(hierarchy_level) as avg_depth,
                    MAX(hierarchy_level) as max_depth
                FROM agent_hierarchy
            """)
            
            # System metrics
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            
            metrics = {
                "timestamp": datetime.now().isoformat(),
                "elapsed_seconds": int(time.time() - self.start_time.timestamp()),
                "database": {
                    "active_connections": db_stats["active_connections"],
                    "total_connections": db_stats["total_connections"],
                    "backends": db_stats["backends"]
                },
                "workflows": {
                    "total": workflow_stats["total_workflows"] or 0,
                    "per_minute": workflow_stats["workflows_last_minute"] or 0,
                    "per_second": (workflow_stats["workflows_last_minute"] or 0) / 60.0
                },
                "hierarchy": {
                    "total_agents": hierarchy_stats["total_agents"],
                    "avg_depth": float(hierarchy_stats["avg_depth"] or 0),
                    "max_depth": hierarchy_stats["max_depth"]
                },
                "system": {
                    "cpu_percent": cpu_percent,
                    "memory_percent": memory.percent,
                    "memory_used_gb": memory.used / (1024**3),
                    "disk_percent": disk.percent
                }
            }
            
            return metrics
            
        finally:
            await conn.close()
    
    async def monitor(self):
        """Run monitoring loop."""
        self.start_time = datetime.now()
        end_time = time.time() + self.duration
        
        print("=" * 80)
        print("LOAD TEST MONITORING STARTED")
        print("=" * 80)
        print(f"Start Time: {self.start_time}")
        print(f"Duration: {self.duration} seconds ({self.duration/60:.1f} minutes)")
        print(f"Sampling Interval: {self.interval} seconds")
        print("=" * 80)
        
        while time.time() < end_time:
            try:
                metrics = await self.collect_metrics()
                self.metrics.append(metrics)
                
                # Print real-time stats
                print(f"\n[{metrics['timestamp']}] Elapsed: {metrics['elapsed_seconds']}s")
                print(f"  Workflows: {metrics['workflows']['per_second']:.2f}/s "
                      f"({metrics['workflows']['total']} total)")
                print(f"  DB Connections: {metrics['database']['active_connections']} active, "
                      f"{metrics['database']['total_connections']} total")
                print(f"  System: CPU {metrics['system']['cpu_percent']:.1f}%, "
                      f"Memory {metrics['system']['memory_percent']:.1f}%")
                
            except Exception as e:
                print(f"Error collecting metrics: {e}")
            
            await asyncio.sleep(self.interval)
        
        print("\n" + "=" * 80)
        print("LOAD TEST MONITORING COMPLETE")
        print("=" * 80)
    
    def generate_report(self, output_file: str):
        """Generate HTML report."""
        if not self.metrics:
            print("No metrics collected")
            return
        
        # Calculate summary statistics
        total_workflows = self.metrics[-1]["workflows"]["total"]
        avg_throughput = sum(m["workflows"]["per_second"] for m in self.metrics) / len(self.metrics)
        max_throughput = max(m["workflows"]["per_second"] for m in self.metrics)
        avg_cpu = sum(m["system"]["cpu_percent"] for m in self.metrics) / len(self.metrics)
        max_cpu = max(m["system"]["cpu_percent"] for m in self.metrics)
        avg_memory = sum(m["system"]["memory_percent"] for m in self.metrics) / len(self.metrics)
        max_memory = max(m["system"]["memory_percent"] for m in self.metrics)
        
        html = f"""
<!DOCTYPE html>
<html>
<head>
    <title>Load Test Report - {self.start_time.strftime('%Y-%m-%d %H:%M:%S')}</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; }}
        h1 {{ color: #333; }}
        table {{ border-collapse: collapse; width: 100%; margin: 20px 0; }}
        th, td {{ border: 1px solid #ddd; padding: 12px; text-align: left; }}
        th {{ background-color: #4CAF50; color: white; }}
        tr:nth-child(even) {{ background-color: #f2f2f2; }}
        .summary {{ background-color: #e7f3fe; padding: 15px; margin: 20px 0; border-left: 6px solid #2196F3; }}
        .metric {{ display: inline-block; margin: 10px 20px; }}
        .metric-value {{ font-size: 24px; font-weight: bold; color: #4CAF50; }}
        .metric-label {{ font-size: 14px; color: #666; }}
    </style>
</head>
<body>
    <h1>Load Test Report</h1>
    <p><strong>Test Date:</strong> {self.start_time.strftime('%Y-%m-%d %H:%M:%S')}</p>
    <p><strong>Duration:</strong> {self.duration} seconds ({self.duration/60:.1f} minutes)</p>
    <p><strong>Samples Collected:</strong> {len(self.metrics)}</p>
    
    <div class="summary">
        <h2>Summary Statistics</h2>
        <div class="metric">
            <div class="metric-value">{total_workflows}</div>
            <div class="metric-label">Total Workflows</div>
        </div>
        <div class="metric">
            <div class="metric-value">{avg_throughput:.2f}</div>
            <div class="metric-label">Avg Throughput (workflows/s)</div>
        </div>
        <div class="metric">
            <div class="metric-value">{max_throughput:.2f}</div>
            <div class="metric-label">Max Throughput (workflows/s)</div>
        </div>
        <div class="metric">
            <div class="metric-value">{avg_cpu:.1f}%</div>
            <div class="metric-label">Avg CPU Usage</div>
        </div>
        <div class="metric">
            <div class="metric-value">{max_cpu:.1f}%</div>
            <div class="metric-label">Max CPU Usage</div>
        </div>
        <div class="metric">
            <div class="metric-value">{avg_memory:.1f}%</div>
            <div class="metric-label">Avg Memory Usage</div>
        </div>
    </div>
    
    <h2>Detailed Metrics</h2>
    <table>
        <tr>
            <th>Timestamp</th>
            <th>Elapsed (s)</th>
            <th>Workflows/s</th>
            <th>Total Workflows</th>
            <th>Active Connections</th>
            <th>CPU %</th>
            <th>Memory %</th>
        </tr>
"""
        
        for m in self.metrics:
            html += f"""
        <tr>
            <td>{m['timestamp']}</td>
            <td>{m['elapsed_seconds']}</td>
            <td>{m['workflows']['per_second']:.2f}</td>
            <td>{m['workflows']['total']}</td>
            <td>{m['database']['active_connections']}</td>
            <td>{m['system']['cpu_percent']:.1f}%</td>
            <td>{m['system']['memory_percent']:.1f}%</td>
        </tr>
"""
        
        html += """
    </table>
</body>
</html>
"""
        
        with open(output_file, 'w') as f:
            f.write(html)
        
        print(f"\n✅ Report generated: {output_file}")
        print(f"\nSummary:")
        print(f"  Total Workflows: {total_workflows}")
        print(f"  Avg Throughput: {avg_throughput:.2f} workflows/s")
        print(f"  Max Throughput: {max_throughput:.2f} workflows/s")
        print(f"  Avg CPU: {avg_cpu:.1f}%")
        print(f"  Max CPU: {max_cpu:.1f}%")
        print(f"  Avg Memory: {avg_memory:.1f}%")


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Monitor load test and generate report")
    parser.add_argument(
        "--duration",
        type=int,
        default=3600,
        help="Monitoring duration in seconds (default: 3600 = 1 hour)"
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=10,
        help="Sampling interval in seconds (default: 10)"
    )
    parser.add_argument(
        "--output",
        default="load_test_report.html",
        help="Output HTML report file (default: load_test_report.html)"
    )
    
    args = parser.parse_args()
    
    monitor = LoadTestMonitor(duration=args.duration, interval=args.interval)
    
    try:
        await monitor.monitor()
    except KeyboardInterrupt:
        print("\n\nMonitoring interrupted by user")
    finally:
        monitor.generate_report(args.output)


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
