# Customer Portal - Remittance Platform

This is a production-ready React frontend application for the Remittance Platform's Customer Portal. It is built with modern web development best practices, focusing on a professional UI/UX, responsive design, and API integration readiness.

## Features

-   **Modern React with Vite**: Fast development and optimized builds.
-   **Tailwind CSS**: Utility-first CSS framework for rapid UI development.
-   **shadcn/ui components**: Reusable and accessible UI components.
-   **Lucide icons**: A collection of beautiful and customizable open-source icons.
-   **Recharts**: Composable charting library built with React components for data visualization.
-   **Multiple Pages/Routes**: Implemented using `react-router-dom` for clear navigation.
    -   Dashboard
    -   Accounts
    -   Transactions
    -   Profile
    -   Login
    -   404 Not Found
-   **Responsive Design**: Mobile-first approach ensuring optimal experience across devices.
-   **Professional UI/UX**: Clean, modern, and intuitive user interface.
-   **State Management**: Basic authentication state managed using React Context API.
-   **API Integration Ready**: Structure in place for easy integration with backend services.
-   **Protected Routes**: Ensures only authenticated users can access core application features.

## Technologies Used

-   React 19
-   Vite
-   Tailwind CSS
-   shadcn/ui
-   Lucide React
-   Recharts
-   React Router DOM

## Project Structure

```
customer-portal/
├── public/
├── src/
│   ├── assets/             # Static assets like images
│   ├── components/         # Reusable React components (e.g., Navbar, Sidebar, Footer, ProtectedRoute)
│   │   └── ui/             # shadcn/ui components
│   ├── context/            # React Context for state management (e.g., AuthContext)
│   ├── hooks/              # Custom React hooks (if any)
│   ├── lib/                # Utility functions and libraries
│   ├── pages/              # Main application pages (e.g., Dashboard, Accounts, Login)
│   ├── App.css             # App-specific styles
│   ├── App.jsx             # Main application component with routing
│   ├── index.css           # Global styles
│   └── main.jsx            # Entry point of the React application
├── components.json         # shadcn/ui configuration
├── eslint.config.js        # ESLint configuration
├── index.html              # HTML entry point
├── package.json            # Project dependencies and scripts
├── pnpm-lock.yaml          # Lock file for dependencies
└── vite.config.js          # Vite bundler configuration
```

## Getting Started

### Prerequisites

-   Node.js (v18 or higher)
-   pnpm (or npm/yarn)

### Installation

1.  Clone the repository:
    ```bash
    git clone <repository-url>
    cd customer-portal
    ```
2.  Install dependencies:
    ```bash
    pnpm install
    ```

### Running the Development Server

```bash
pnpm run dev
```

This will start the development server, and you can view the application in your browser at `http://localhost:5173` (or another port if 5173 is in use).

## API Integration

The application is structured to be easily integrated with backend services. API calls can be managed within individual page/component logic or through a centralized API service layer (e.g., `src/lib/api.js`). Loading states and error handling are implemented at a basic level and can be extended as needed.

## Contributing

Feel free to fork the repository, make changes, and submit pull requests. Please ensure your code adheres to the project's coding standards and best practices.

## License

This project is licensed under the MIT License.

