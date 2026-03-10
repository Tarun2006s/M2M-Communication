import React from 'react';
import ComparisonCharts from './ComparisonCharts';

const SimulationDashboard = ({ results }) => {

    if (!results) {
        return (
            <div>
                <h1>Simulation Dashboard</h1>
                <p>No simulation results yet. Please run the simulation first.</p>
            </div>
        );
    }

    // compute final battery/soh value if available
    const finalBattery = results.battery_history && results.battery_history.length
        ? results.battery_history[results.battery_history.length - 1]
        : null;
    const finalSoh = results.soh_history && results.soh_history.length
        ? results.soh_history[results.soh_history.length - 1]
        : null;

    return (
        <div>
            <h1>Simulation Dashboard</h1>

            <h2>Simulation Results</h2>

            <p>
                <strong>Average Lifetime:</strong> {results.average_lifetime}
            </p>

            <p>
                <strong>Total Energy:</strong> {results.total_energy}
            </p>

            {finalBattery !== null && (
                <p>
                    <strong>Final avg. Battery SoC:</strong> {(finalBattery * 100).toFixed(1)}%
                </p>
            )}
            {finalSoh !== null && (
                <p>
                    <strong>Final avg. Battery SoH:</strong> {(finalSoh * 100).toFixed(1)}%
                </p>
            )}

            <ComparisonCharts results={results} />

        </div>
    );
};

export default SimulationDashboard;