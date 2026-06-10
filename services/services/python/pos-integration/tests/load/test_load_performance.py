"""
Load Testing Suite for POS Services
Performance and scalability testing
"""

import asyncio
import aiohttp
import time
import statistics
import json
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
import pytest

# Test configuration
TEST_BASE_URL = "http://localhost:8070"
QR_SERVICE_URL = "http://localhost:8071"
ENHANCED_POS_URL = "http://localhost:8072"
DEVICE_MANAGER_URL = "http://localhost:8073"

class LoadTestMetrics:
    """Collect and analyze load test metrics"""
    
    def __init__(self):
        self.response_times = []
        self.success_count = 0
        self.error_count = 0
        self.start_time = None
        self.end_time = None
    
    def add_response(self, response_time: float, success: bool):
        """Add response metrics"""
        self.response_times.append(response_time)
        if success:
            self.success_count += 1
        else:
            self.error_count += 1
    
    def get_statistics(self):
        """Get performance statistics"""
        if not self.response_times:
            return {}
        
        total_requests = len(self.response_times)
        duration = self.end_time - self.start_time if self.end_time and self.start_time else 0
        
        return {
            'total_requests': total_requests,
            'successful_requests': self.success_count,
            'failed_requests': self.error_count,
            'success_rate': (self.success_count / total_requests) * 100,
            'duration_seconds': duration,
            'requests_per_second': total_requests / duration if duration > 0 else 0,
            'avg_response_time': statistics.mean(self.response_times),
            'min_response_time': min(self.response_times),
            'max_response_time': max(self.response_times),
            'median_response_time': statistics.median(self.response_times),
            'p95_response_time': self._percentile(self.response_times, 95),
            'p99_response_time': self._percentile(self.response_times, 99)
        }
    
    def _percentile(self, data, percentile):
        """Calculate percentile"""
        sorted_data = sorted(data)
        index = int((percentile / 100) * len(sorted_data))
        return sorted_data[min(index, len(sorted_data) - 1)]

class TestPOSLoadPerformance:
    """Load testing for POS services"""
    
    @pytest.fixture
    async def load_test_session(self):
        """Create session for load testing"""
        connector = aiohttp.TCPConnector(limit=100, limit_per_host=100)
        timeout = aiohttp.ClientTimeout(total=30)
        async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
            yield session
    
    @pytest.mark.asyncio
    async def test_qr_generation_load(self, load_test_session):
        """Load test QR code generation"""
        metrics = LoadTestMetrics()
        metrics.start_time = time.time()
        
        # Configuration
        concurrent_users = 50
        requests_per_user = 20
        
        async def generate_qr_request(session, user_id, request_id):
            """Single QR generation request"""
            qr_data = {
                "merchant_id": f"LOAD_TEST_MERCHANT_{user_id}",
                "amount": 100.0 + (request_id * 0.01),
                "currency": "USD",
                "transaction_id": f"LOAD_TXN_{user_id}_{request_id}_{int(time.time())}"
            }
            
            start_time = time.time()
            try:
                async with session.post(f"{QR_SERVICE_URL}/qr/generate", json=qr_data) as response:
                    await response.json()
                    response_time = time.time() - start_time
                    success = response.status == 200
                    metrics.add_response(response_time, success)
                    return success
            except Exception as e:
                response_time = time.time() - start_time
                metrics.add_response(response_time, False)
                return False
        
        # Create tasks for concurrent load
        tasks = []
        for user_id in range(concurrent_users):
            for request_id in range(requests_per_user):
                task = generate_qr_request(load_test_session, user_id, request_id)
                tasks.append(task)
        
        # Execute load test
        results = await asyncio.gather(*tasks, return_exceptions=True)
        metrics.end_time = time.time()
        
        # Analyze results
        stats = metrics.get_statistics()
        
        # Performance assertions
        assert stats['success_rate'] >= 95.0, f"Success rate too low: {stats['success_rate']}%"
        assert stats['avg_response_time'] <= 1.0, f"Average response time too high: {stats['avg_response_time']}s"
        assert stats['p95_response_time'] <= 2.0, f"95th percentile too high: {stats['p95_response_time']}s"
        assert stats['requests_per_second'] >= 100, f"Throughput too low: {stats['requests_per_second']} RPS"
        
        print(f"QR Generation Load Test Results:")
        print(f"  Total Requests: {stats['total_requests']}")
        print(f"  Success Rate: {stats['success_rate']:.2f}%")
        print(f"  Requests/Second: {stats['requests_per_second']:.2f}")
        print(f"  Avg Response Time: {stats['avg_response_time']:.3f}s")
        print(f"  P95 Response Time: {stats['p95_response_time']:.3f}s")
    
    @pytest.mark.asyncio
    async def test_payment_processing_load(self, load_test_session):
        """Load test payment processing"""
        metrics = LoadTestMetrics()
        metrics.start_time = time.time()
        
        # Configuration
        concurrent_users = 30
        requests_per_user = 10
        
        async def process_payment_request(session, user_id, request_id):
            """Single payment processing request"""
            payment_data = {
                "amount": 50.0 + (request_id * 0.5),
                "currency": "USD",
                "payment_method": "card_chip",
                "merchant_id": f"LOAD_MERCHANT_{user_id}",
                "terminal_id": f"LOAD_TERMINAL_{user_id}",
                "transaction_reference": f"LOAD_REF_{user_id}_{request_id}"
            }
            
            start_time = time.time()
            try:
                async with session.post(f"{ENHANCED_POS_URL}/enhanced/process-payment", json=payment_data) as response:
                    await response.json()
                    response_time = time.time() - start_time
                    success = response.status == 200
                    metrics.add_response(response_time, success)
                    return success
            except Exception as e:
                response_time = time.time() - start_time
                metrics.add_response(response_time, False)
                return False
        
        # Create tasks for concurrent load
        tasks = []
        for user_id in range(concurrent_users):
            for request_id in range(requests_per_user):
                task = process_payment_request(load_test_session, user_id, request_id)
                tasks.append(task)
        
        # Execute load test
        results = await asyncio.gather(*tasks, return_exceptions=True)
        metrics.end_time = time.time()
        
        # Analyze results
        stats = metrics.get_statistics()
        
        # Performance assertions
        assert stats['success_rate'] >= 90.0, f"Success rate too low: {stats['success_rate']}%"
        assert stats['avg_response_time'] <= 3.0, f"Average response time too high: {stats['avg_response_time']}s"
        assert stats['p95_response_time'] <= 5.0, f"95th percentile too high: {stats['p95_response_time']}s"
        assert stats['requests_per_second'] >= 50, f"Throughput too low: {stats['requests_per_second']} RPS"
        
        print(f"Payment Processing Load Test Results:")
        print(f"  Total Requests: {stats['total_requests']}")
        print(f"  Success Rate: {stats['success_rate']:.2f}%")
        print(f"  Requests/Second: {stats['requests_per_second']:.2f}")
        print(f"  Avg Response Time: {stats['avg_response_time']:.3f}s")
        print(f"  P95 Response Time: {stats['p95_response_time']:.3f}s")
    
    @pytest.mark.asyncio
    async def test_mixed_workload_load(self, load_test_session):
        """Load test mixed workload (QR + Payment + Device operations)"""
        metrics = LoadTestMetrics()
        metrics.start_time = time.time()
        
        # Configuration
        concurrent_users = 40
        operations_per_user = 15
        
        async def mixed_operation_request(session, user_id, operation_id):
            """Mixed operation request"""
            operation_type = operation_id % 4  # Rotate between 4 operation types
            
            start_time = time.time()
            try:
                if operation_type == 0:  # QR Generation
                    qr_data = {
                        "merchant_id": f"MIXED_MERCHANT_{user_id}",
                        "amount": 75.0,
                        "currency": "USD",
                        "transaction_id": f"MIXED_TXN_{user_id}_{operation_id}"
                    }
                    async with session.post(f"{QR_SERVICE_URL}/qr/generate", json=qr_data) as response:
                        await response.json()
                        success = response.status == 200
                
                elif operation_type == 1:  # Payment Processing
                    payment_data = {
                        "amount": 25.0,
                        "currency": "USD",
                        "payment_method": "card_contactless",
                        "merchant_id": f"MIXED_MERCHANT_{user_id}",
                        "terminal_id": f"MIXED_TERMINAL_{user_id}"
                    }
                    async with session.post(f"{ENHANCED_POS_URL}/enhanced/process-payment", json=payment_data) as response:
                        await response.json()
                        success = response.status == 200
                
                elif operation_type == 2:  # Device Status Check
                    async with session.get(f"{DEVICE_MANAGER_URL}/devices/statistics") as response:
                        await response.json()
                        success = response.status == 200
                
                else:  # Analytics Query
                    async with session.get(f"{ENHANCED_POS_URL}/enhanced/analytics/transactions") as response:
                        await response.json()
                        success = response.status == 200
                
                response_time = time.time() - start_time
                metrics.add_response(response_time, success)
                return success
                
            except Exception as e:
                response_time = time.time() - start_time
                metrics.add_response(response_time, False)
                return False
        
        # Create tasks for concurrent mixed load
        tasks = []
        for user_id in range(concurrent_users):
            for operation_id in range(operations_per_user):
                task = mixed_operation_request(load_test_session, user_id, operation_id)
                tasks.append(task)
        
        # Execute load test
        results = await asyncio.gather(*tasks, return_exceptions=True)
        metrics.end_time = time.time()
        
        # Analyze results
        stats = metrics.get_statistics()
        
        # Performance assertions
        assert stats['success_rate'] >= 85.0, f"Success rate too low: {stats['success_rate']}%"
        assert stats['avg_response_time'] <= 2.0, f"Average response time too high: {stats['avg_response_time']}s"
        assert stats['p95_response_time'] <= 4.0, f"95th percentile too high: {stats['p95_response_time']}s"
        assert stats['requests_per_second'] >= 75, f"Throughput too low: {stats['requests_per_second']} RPS"
        
        print(f"Mixed Workload Load Test Results:")
        print(f"  Total Requests: {stats['total_requests']}")
        print(f"  Success Rate: {stats['success_rate']:.2f}%")
        print(f"  Requests/Second: {stats['requests_per_second']:.2f}")
        print(f"  Avg Response Time: {stats['avg_response_time']:.3f}s")
        print(f"  P95 Response Time: {stats['p95_response_time']:.3f}s")
    
    @pytest.mark.asyncio
    async def test_sustained_load(self, load_test_session):
        """Test sustained load over extended period"""
        metrics = LoadTestMetrics()
        metrics.start_time = time.time()
        
        # Configuration
        duration_seconds = 60  # 1 minute sustained load
        requests_per_second = 50
        
        async def sustained_request(session, request_id):
            """Single sustained load request"""
            qr_data = {
                "merchant_id": f"SUSTAINED_MERCHANT",
                "amount": 100.0,
                "currency": "USD",
                "transaction_id": f"SUSTAINED_TXN_{request_id}_{int(time.time())}"
            }
            
            start_time = time.time()
            try:
                async with session.post(f"{QR_SERVICE_URL}/qr/generate", json=qr_data) as response:
                    await response.json()
                    response_time = time.time() - start_time
                    success = response.status == 200
                    metrics.add_response(response_time, success)
                    return success
            except Exception as e:
                response_time = time.time() - start_time
                metrics.add_response(response_time, False)
                return False
        
        # Generate sustained load
        request_id = 0
        end_time = time.time() + duration_seconds
        
        while time.time() < end_time:
            batch_start = time.time()
            
            # Create batch of requests
            batch_tasks = []
            for _ in range(requests_per_second):
                task = sustained_request(load_test_session, request_id)
                batch_tasks.append(task)
                request_id += 1
            
            # Execute batch
            await asyncio.gather(*batch_tasks, return_exceptions=True)
            
            # Wait for next second
            batch_duration = time.time() - batch_start
            if batch_duration < 1.0:
                await asyncio.sleep(1.0 - batch_duration)
        
        metrics.end_time = time.time()
        
        # Analyze results
        stats = metrics.get_statistics()
        
        # Performance assertions for sustained load
        assert stats['success_rate'] >= 90.0, f"Sustained success rate too low: {stats['success_rate']}%"
        assert stats['avg_response_time'] <= 1.5, f"Sustained avg response time too high: {stats['avg_response_time']}s"
        assert stats['requests_per_second'] >= 40, f"Sustained throughput too low: {stats['requests_per_second']} RPS"
        
        print(f"Sustained Load Test Results:")
        print(f"  Duration: {stats['duration_seconds']:.2f}s")
        print(f"  Total Requests: {stats['total_requests']}")
        print(f"  Success Rate: {stats['success_rate']:.2f}%")
        print(f"  Requests/Second: {stats['requests_per_second']:.2f}")
        print(f"  Avg Response Time: {stats['avg_response_time']:.3f}s")
    
    @pytest.mark.asyncio
    async def test_spike_load(self, load_test_session):
        """Test system behavior under sudden load spikes"""
        metrics = LoadTestMetrics()
        metrics.start_time = time.time()
        
        # Configuration
        normal_load = 10  # Normal concurrent requests
        spike_load = 100  # Spike concurrent requests
        
        async def spike_request(session, request_id, is_spike=False):
            """Single spike load request"""
            payment_data = {
                "amount": 50.0,
                "currency": "USD",
                "payment_method": "card_chip",
                "merchant_id": f"SPIKE_MERCHANT_{request_id}",
                "terminal_id": f"SPIKE_TERMINAL_{request_id}"
            }
            
            start_time = time.time()
            try:
                async with session.post(f"{ENHANCED_POS_URL}/enhanced/process-payment", json=payment_data) as response:
                    await response.json()
                    response_time = time.time() - start_time
                    success = response.status == 200
                    metrics.add_response(response_time, success)
                    return success, is_spike
            except Exception as e:
                response_time = time.time() - start_time
                metrics.add_response(response_time, False)
                return False, is_spike
        
        # Phase 1: Normal load
        normal_tasks = []
        for i in range(normal_load):
            task = spike_request(load_test_session, i, False)
            normal_tasks.append(task)
        
        # Phase 2: Sudden spike
        spike_tasks = []
        for i in range(spike_load):
            task = spike_request(load_test_session, normal_load + i, True)
            spike_tasks.append(task)
        
        # Execute normal load first
        normal_results = await asyncio.gather(*normal_tasks, return_exceptions=True)
        
        # Then execute spike load
        spike_results = await asyncio.gather(*spike_tasks, return_exceptions=True)
        
        metrics.end_time = time.time()
        
        # Analyze results
        stats = metrics.get_statistics()
        
        # Performance assertions for spike handling
        assert stats['success_rate'] >= 80.0, f"Spike handling success rate too low: {stats['success_rate']}%"
        assert stats['p99_response_time'] <= 10.0, f"Spike P99 response time too high: {stats['p99_response_time']}s"
        
        print(f"Spike Load Test Results:")
        print(f"  Total Requests: {stats['total_requests']}")
        print(f"  Success Rate: {stats['success_rate']:.2f}%")
        print(f"  Requests/Second: {stats['requests_per_second']:.2f}")
        print(f"  P99 Response Time: {stats['p99_response_time']:.3f}s")

class TestPOSStressTest:
    """Stress testing to find system limits"""
    
    @pytest.fixture
    async def stress_test_session(self):
        """Create session for stress testing"""
        connector = aiohttp.TCPConnector(limit=200, limit_per_host=200)
        timeout = aiohttp.ClientTimeout(total=60)
        async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
            yield session
    
    @pytest.mark.asyncio
    async def test_find_throughput_limit(self, stress_test_session):
        """Find maximum throughput limit"""
        print("Finding maximum throughput limit...")
        
        # Start with low load and gradually increase
        load_levels = [50, 100, 200, 300, 400, 500]
        results = {}
        
        for load_level in load_levels:
            print(f"Testing load level: {load_level} concurrent requests")
            
            metrics = LoadTestMetrics()
            metrics.start_time = time.time()
            
            async def throughput_request(session, request_id):
                """Throughput test request"""
                qr_data = {
                    "merchant_id": f"THROUGHPUT_MERCHANT",
                    "amount": 100.0,
                    "currency": "USD",
                    "transaction_id": f"THROUGHPUT_TXN_{request_id}_{int(time.time())}"
                }
                
                start_time = time.time()
                try:
                    async with session.post(f"{QR_SERVICE_URL}/qr/generate", json=qr_data) as response:
                        await response.json()
                        response_time = time.time() - start_time
                        success = response.status == 200
                        metrics.add_response(response_time, success)
                        return success
                except Exception as e:
                    response_time = time.time() - start_time
                    metrics.add_response(response_time, False)
                    return False
            
            # Execute load level
            tasks = [throughput_request(stress_test_session, i) for i in range(load_level)]
            await asyncio.gather(*tasks, return_exceptions=True)
            
            metrics.end_time = time.time()
            stats = metrics.get_statistics()
            results[load_level] = stats
            
            print(f"  Success Rate: {stats['success_rate']:.2f}%")
            print(f"  Requests/Second: {stats['requests_per_second']:.2f}")
            print(f"  Avg Response Time: {stats['avg_response_time']:.3f}s")
            
            # Stop if success rate drops below threshold
            if stats['success_rate'] < 80.0:
                print(f"Throughput limit reached at {load_level} concurrent requests")
                break
        
        # Find optimal load level
        optimal_load = max([level for level, stats in results.items() if stats['success_rate'] >= 95.0])
        print(f"Optimal load level: {optimal_load} concurrent requests")
        
        return results

# Test utilities
@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
