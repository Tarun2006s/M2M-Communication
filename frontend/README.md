# dqn-battery-scheduling-app/frontend/README.md

# DQN Battery Scheduling Application - Frontend

This is the frontend part of the DQN Battery Scheduling Application, which demonstrates the implementation of a Deep Q-Network (DQN) combined with battery health management and sleep/awake scheduling. The frontend is built using React and provides a user interface for running simulations and comparing the performance of the DQN algorithm against other algorithms.

## Table of Contents

- [Installation](#installation)
- [Usage](#usage)
- [Components](#components)
- [API Integration](#api-integration)
- [Contributing](#contributing)
- [License](#license)

## Installation

1. Clone the repository:
   ```
   git clone https://github.com/yourusername/dqn-battery-scheduling-app.git
   ```

2. Navigate to the frontend directory:
   ```
   cd dqn-battery-scheduling-app/frontend
   ```

3. Install the required dependencies:
   ```
   npm install
   ```

## Usage

To start the frontend application, run the following command in the frontend directory:
```
npm start
```
This will start the development server and open the application in your default web browser. The application will be available at `http://localhost:3000`.

## Components

- **App.jsx**: The main component that sets up routing and renders the main layout of the application.
- **SimulationDashboard.jsx**: Displays the results of the simulations, including metrics and visualizations.
- **ComparisonCharts.jsx**: Visualizes the comparison between the DQN-based algorithm and other algorithms using charts.
- **ControlsPanel.jsx**: Provides controls for starting simulations, selecting algorithms, and adjusting parameters.

## API Integration

The frontend interacts with the backend API to run simulations and retrieve results. The API endpoints are defined in the backend and can be accessed through the functions in `src/api/simulation.js`.

## Contributing

Contributions are welcome! If you have suggestions for improvements or new features, please open an issue or submit a pull request.

## License

This project is licensed under the MIT License. See the [LICENSE](../LICENSE) file for details.