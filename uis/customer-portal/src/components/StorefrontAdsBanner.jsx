import { ChevronLeft, ChevronRight, X } from "lucide-react";
import React, { useEffect, useState } from "react";
import { storefrontAdvertisingApi } from "../utils/api";

const StorefrontAdsBanner = ({ maxAds = 5 }) => {
  const [ads, setAds] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [currentAdIndex, setCurrentAdIndex] = useState(0);
  const [dismissed, setDismissed] = useState(false);

  useEffect(() => {
    loadAds();
  }, []);

  const loadAds = async () => {
    try {
      setLoading(true);
      setError(null);
      const response = await storefrontAdvertisingApi.getActiveAds();
      const adsList = Array.isArray(response)
        ? response
        : Array.isArray(response?.ads)
          ? response.ads
          : [];
      setAds(adsList.slice(0, maxAds));
    } catch (err) {
      // Silently fail for 404 or service unavailable errors (optional feature)
      // Only log if it's an unexpected error
      if (err.message && !err.message.includes("404")) {
        console.debug("Storefront ads unavailable:", err.message);
      }
      setError(null); // Don't show error to user - this is optional
      setAds([]);
    } finally {
      setLoading(false);
    }
  };

  const handleRecordImpression = async (ad) => {
    try {
      await storefrontAdvertisingApi.recordImpression(ad.id);
    } catch (err) {
      console.error("Failed to record impression:", err);
    }
  };

  const handleRecordClick = async (ad) => {
    try {
      await storefrontAdvertisingApi.recordClick(ad.id);
      if (ad.cta_url) {
        window.open(ad.cta_url, "_blank", "noopener,noreferrer");
      }
    } catch (err) {
      console.error("Failed to record click:", err);
    }
  };

  const nextAd = () => {
    setCurrentAdIndex((prev) => (prev + 1) % ads.length);
  };

  const prevAd = () => {
    setCurrentAdIndex((prev) => (prev - 1 + ads.length) % ads.length);
  };

  const currentAd = ads[currentAdIndex];

  useEffect(() => {
    if (ads.length === 0) {
      if (currentAdIndex !== 0) {
        setCurrentAdIndex(0);
      }
      return;
    }

    if (currentAdIndex >= ads.length) {
      setCurrentAdIndex(0);
    }
  }, [ads.length, currentAdIndex]);

  useEffect(() => {
    if (!dismissed && !loading && currentAd?.id) {
      handleRecordImpression(currentAd);
    }
  }, [dismissed, loading, currentAd?.id]);

  if (dismissed || loading || ads.length === 0 || error) {
    return null;
  }

  return (
    <div className="relative bg-linear-to-r from-blue-50 to-indigo-50 rounded-xl shadow-lg overflow-hidden border border-blue-200">
      {/* Close Button */}
      <button
        onClick={() => setDismissed(true)}
        className="absolute top-4 right-4 z-10 text-gray-400 hover:text-gray-600 bg-white rounded-full p-1 shadow-sm"
      >
        <X className="h-5 w-5" />
      </button>

      <div className="p-6 md:p-8">
        <div className="flex flex-col md:flex-row gap-6 items-center">
          {/* Ad Image */}
          {currentAd.image_url && (
            <div className="shrink-0 w-full md:w-48 h-40 bg-gray-200 rounded-lg overflow-hidden">
              <img
                src={currentAd.image_url}
                alt={currentAd.title}
                className="w-full h-full object-cover"
              />
            </div>
          )}

          {/* Ad Content */}
          <div className="flex-1">
            <div className="flex items-center gap-2 mb-2">
              <span className="inline-block px-2 py-1 bg-blue-100 text-blue-700 text-xs font-semibold rounded-full">
                {currentAd.ad_type || "Featured"}
              </span>
              {currentAd.merchant_name && (
                <span className="text-sm text-gray-600">
                  by {currentAd.merchant_name}
                </span>
              )}
            </div>

            <h3 className="text-xl font-bold text-gray-900 mb-2">
              {currentAd.title}
            </h3>

            {currentAd.description && (
              <p className="text-gray-600 mb-4 line-clamp-2">
                {currentAd.description}
              </p>
            )}

            {currentAd.cta_text && (
              <button
                onClick={() => handleRecordClick(currentAd)}
                className="inline-flex items-center px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors font-semibold text-sm"
              >
                {currentAd.cta_text}
              </button>
            )}
          </div>
        </div>

        {/* Carousel Controls */}
        {ads.length > 1 && (
          <div className="flex items-center justify-center gap-4 mt-6">
            <button
              onClick={prevAd}
              className="p-2 text-gray-600 hover:text-gray-900 bg-white rounded-full shadow hover:shadow-md transition-all"
            >
              <ChevronLeft className="h-5 w-5" />
            </button>

            <div className="flex gap-2">
              {ads.map((_, index) => (
                <button
                  key={index}
                  onClick={() => setCurrentAdIndex(index)}
                  className={`h-2 rounded-full transition-all ${
                    index === currentAdIndex
                      ? "bg-blue-600 w-6"
                      : "bg-gray-300 w-2 hover:bg-gray-400"
                  }`}
                  aria-label={`Go to ad ${index + 1}`}
                />
              ))}
            </div>

            <button
              onClick={nextAd}
              className="p-2 text-gray-600 hover:text-gray-900 bg-white rounded-full shadow hover:shadow-md transition-all"
            >
              <ChevronRight className="h-5 w-5" />
            </button>
          </div>
        )}

        {/* Ad Counter */}
        {ads.length > 1 && (
          <p className="text-xs text-gray-500 text-center mt-3">
            {currentAdIndex + 1} of {ads.length}
          </p>
        )}
      </div>
    </div>
  );
};

export default StorefrontAdsBanner;
