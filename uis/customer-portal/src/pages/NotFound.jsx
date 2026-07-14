import { Home } from "lucide-react";
import React from "react";
import { Link } from "react-router-dom";

const NotFound = () => {
  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50">
      <div className="text-center">
        <h1 className="text-6xl font-bold text-gray-300">404</h1>
        <h2 className="mt-4 text-2xl font-semibold text-gray-900">
          Page Not Found
        </h2>
        <p className="mt-2 text-gray-600">
          The page you're looking for doesn't exist.
        </p>
        <Link
          to="/"
          className="mt-6 inline-flex items-center px-4 py-2 bg-green-600 text-white rounded-md hover:bg-green-700 transition-colors"
        >
          <Home className="w-5 h-5 mr-2" />
          Go Home
        </Link>
      </div>
    </div>
  );
};

export default NotFound;
