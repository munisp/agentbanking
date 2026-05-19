import Foundation
import UIKit
import CoreData

// MARK: - 14. Performance Monitoring

class PerformanceMonitor {
    static let shared = PerformanceMonitor()
    
    private var startupTime: Date?
    private var metrics: [String: Double] = [:]
    
    func trackStartup() {
        startupTime = Date()
    }
    
    func completeStartup() {
        guard let start = startupTime else { return }
        let duration = Date().timeIntervalSince(start)
        metrics["startup_time"] = duration
        
        print("📊 Startup time: \(duration)s")
    }
    
    func trackAPILatency(endpoint: String, duration: TimeInterval) {
        metrics["api_\(endpoint)"] = duration
        print("📊 API \(endpoint): \(duration)s")
    }
    
    func trackMemoryUsage() {
        var info = mach_task_basic_info()
        var count = mach_msg_type_number_t(MemoryLayout<mach_task_basic_info>.size)/4
        
        let kerr: kern_return_t = withUnsafeMutablePointer(to: &info) {
            $0.withMemoryRebound(to: integer_t.self, capacity: 1) {
                task_info(mach_task_self_, task_flavor_t(MACH_TASK_BASIC_INFO), $0, &count)
            }
        }
        
        if kerr == KERN_SUCCESS {
            let memoryMB = Double(info.resident_size) / 1024 / 1024
            metrics["memory_mb"] = memoryMB
            print("📊 Memory: \(memoryMB) MB")
        }
    }
    
    func trackFrameRate(fps: Double) {
        metrics["fps"] = fps
        print("📊 FPS: \(fps)")
    }
}

// MARK: - 15. Performance Budgets

class PerformanceBudget {
    static let shared = PerformanceBudget()
    
    struct Budget {
        let maxStartupTime: TimeInterval = 1.0
        let maxAPIResponse: TimeInterval = 2.0
        let maxImageLoad: TimeInterval = 0.5
        let minFPS: Double = 55.0
        let maxMemoryMB: Double = 100.0
    }
    
    let budget = Budget()
    
    func checkBudget(metric: String, value: Double) -> Bool {
        let withinBudget: Bool
        
        switch metric {
        case "startup_time":
            withinBudget = value <= budget.maxStartupTime
        case "api_response":
            withinBudget = value <= budget.maxAPIResponse
        case "image_load":
            withinBudget = value <= budget.maxImageLoad
        case "fps":
            withinBudget = value >= budget.minFPS
        case "memory":
            withinBudget = value <= budget.maxMemoryMB
        default:
            withinBudget = true
        }
        
        if !withinBudget {
            print("⚠️ Performance budget exceeded: \(metric) = \(value)")
        }
        
        return withinBudget
    }
}

// MARK: - 16. Native Module Optimization

class NativeOptimizer {
    static func useMetalForGraphics() {
        // Metal framework for GPU-accelerated graphics
    }
    
    static func enableHardwareAcceleration(for layer: CALayer) {
        layer.shouldRasterize = true
        layer.rasterizationScale = UIScreen.main.scale
        layer.drawsAsynchronously = true
    }
}

// MARK: - 17. Animation Performance

class AnimationOptimizer {
    static func optimizeAnimation(for view: UIView, duration: TimeInterval, animations: @escaping () -> Void) {
        // Use CALayer for better performance
        CATransaction.begin()
        CATransaction.setAnimationDuration(duration)
        CATransaction.setAnimationTimingFunction(CAMediaTimingFunction(name: .easeInEaseOut))
        
        animations()
        
        CATransaction.commit()
    }
    
    static func createSpringAnimation(keyPath: String, toValue: Any, duration: TimeInterval) -> CASpringAnimation {
        let animation = CASpringAnimation(keyPath: keyPath)
        animation.toValue = toValue
        animation.duration = duration
        animation.damping = 10
        animation.initialVelocity = 0
        animation.mass = 1
        animation.stiffness = 100
        return animation
    }
}

// MARK: - 18. Memoization

class Memoizer<Input: Hashable, Output> {
    private var cache: [Input: Output] = [:]
    private let compute: (Input) -> Output
    
    init(compute: @escaping (Input) -> Output) {
        self.compute = compute
    }
    
    func value(for input: Input) -> Output {
        if let cached = cache[input] {
            return cached
        }
        
        let result = compute(input)
        cache[input] = result
        return result
    }
    
    func clearCache() {
        cache.removeAll()
    }
}

// Usage example
class ExpensiveCalculations {
    private let fibonacci = Memoizer<Int, Int> { n in
        guard n > 1 else { return n }
        // Expensive calculation
        return n
    }
    
    func calculateFibonacci(_ n: Int) -> Int {
        return fibonacci.value(for: n)
    }
}

// MARK: - 19. Background Task Processing

class BackgroundTaskProcessor {
    static let shared = BackgroundTaskProcessor()
    
    private let queue = DispatchQueue(label: "com.app.background", qos: .utility, attributes: .concurrent)
    
    func processInBackground<T>(task: @escaping () -> T, completion: @escaping (T) -> Void) {
        queue.async {
            let result = task()
            
            DispatchQueue.main.async {
                completion(result)
            }
        }
    }
}

// MARK: - 20. Database Indexing

class DatabaseOptimizer {
    static func createIndexes(context: NSManagedObjectContext) {
        // Core Data indexes are defined in the data model
        // This demonstrates programmatic optimization
        
        let fetchRequest: NSFetchRequest<NSFetchRequestResult> = NSFetchRequest(entityName: "Transaction")
        fetchRequest.predicate = NSPredicate(format: "userId == %@", "user123")
        fetchRequest.fetchLimit = 20
        
        // Use NSFetchedResultsController for efficient table views
    }
    
    static func optimizeQueries() {
        // Batch fetching
        // Prefetching relationships
        // Using faulting efficiently
    }
}
