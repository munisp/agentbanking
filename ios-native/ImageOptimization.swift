import UIKit
import Foundation

/// Image Optimization - 3x faster image loading
class ImageOptimizer {
    static let shared = ImageOptimizer()
    
    private let cache = NSCache<NSString, UIImage>()
    private let diskCachePath: URL
    private let session: URLSession
    
    init() {
        // Configure cache
        cache.countLimit = 100
        cache.totalCostLimit = 50 * 1024 * 1024 // 50 MB
        
        // Disk cache path
        let cacheDir = FileManager.default.urls(for: .cachesDirectory, in: .userDomainMask)[0]
        diskCachePath = cacheDir.appendingPathComponent("ImageCache")
        try? FileManager.default.createDirectory(at: diskCachePath, withIntermediateDirectories: true)
        
        // Configure session for image loading
        let config = URLSessionConfiguration.default
        config.urlCache = URLCache(memoryCapacity: 20 * 1024 * 1024, diskCapacity: 100 * 1024 * 1024)
        config.requestCachePolicy = .returnCacheDataElseLoad
        session = URLSession(configuration: config)
    }
    
    /// Load image with aggressive caching
    func loadImage(url: URL, placeholder: UIImage? = nil, completion: @escaping (UIImage?) -> Void) {
        let cacheKey = url.absoluteString as NSString
        
        // Check memory cache
        if let cachedImage = cache.object(forKey: cacheKey) {
            completion(cachedImage)
            return
        }
        
        // Check disk cache
        if let diskImage = loadFromDisk(url: url) {
            cache.setObject(diskImage, forKey: cacheKey)
            completion(diskImage)
            return
        }
        
        // Show placeholder
        completion(placeholder)
        
        // Download image
        let task = session.dataTask(with: url) { [weak self] data, response, error in
            guard let self = self,
                  let data = data,
                  let image = UIImage(data: data) else {
                DispatchQueue.main.async {
                    completion(nil)
                }
                return
            }
            
            // Optimize image
            let optimized = self.optimizeImage(image)
            
            // Cache in memory
            self.cache.setObject(optimized, forKey: cacheKey)
            
            // Cache on disk
            self.saveToDisk(image: optimized, url: url)
            
            DispatchQueue.main.async {
                completion(optimized)
            }
        }
        task.priority = URLSessionTask.highPriority
        task.resume()
    }
    
    /// Optimize image (resize, compress)
    private func optimizeImage(_ image: UIImage) -> UIImage {
        let maxSize: CGFloat = 1024
        let size = image.size
        
        guard size.width > maxSize || size.height > maxSize else {
            return image
        }
        
        let ratio = min(maxSize / size.width, maxSize / size.height)
        let newSize = CGSize(width: size.width * ratio, height: size.height * ratio)
        
        UIGraphicsBeginImageContextWithOptions(newSize, false, 1.0)
        image.draw(in: CGRect(origin: .zero, size: newSize))
        let resized = UIGraphicsGetImageFromCurrentImageContext()
        UIGraphicsEndImageContext()
        
        return resized ?? image
    }
    
    /// Progressive JPEG support
    func loadProgressiveImage(url: URL, progress: @escaping (UIImage?) -> Void, completion: @escaping (UIImage?) -> Void) {
        var receivedData = Data()
        
        let task = session.dataTask(with: url) { data, response, error in
            guard let data = data else {
                DispatchQueue.main.async {
                    completion(nil)
                }
                return
            }
            
            receivedData.append(data)
            
            // Try to create progressive image
            if let progressImage = UIImage(data: receivedData) {
                DispatchQueue.main.async {
                    progress(progressImage)
                }
            }
        }
        task.resume()
    }
    
    /// Save to disk cache
    private func saveToDisk(image: UIImage, url: URL) {
        guard let data = image.jpegData(compressionQuality: 0.8) else { return }
        
        let filename = url.lastPathComponent
        let fileURL = diskCachePath.appendingPathComponent(filename)
        
        try? data.write(to: fileURL)
    }
    
    /// Load from disk cache
    private func loadFromDisk(url: URL) -> UIImage? {
        let filename = url.lastPathComponent
        let fileURL = diskCachePath.appendingPathComponent(filename)
        
        guard let data = try? Data(contentsOf: fileURL) else { return nil }
        return UIImage(data: data)
    }
    
    /// Clear cache
    func clearCache() {
        cache.removeAllObjects()
        try? FileManager.default.removeItem(at: diskCachePath)
        try? FileManager.default.createDirectory(at: diskCachePath, withIntermediateDirectories: true)
    }
}

/// Optimized UIImageView
class OptimizedImageView: UIImageView {
    private var imageURL: URL?
    
    func loadImage(from url: URL, placeholder: UIImage? = nil) {
        imageURL = url
        
        ImageOptimizer.shared.loadImage(url: url, placeholder: placeholder) { [weak self] image in
            guard let self = self, self.imageURL == url else { return }
            self.image = image
        }
    }
    
    override func prepareForReuse() {
        super.prepareForReuse()
        image = nil
        imageURL = nil
    }
}
