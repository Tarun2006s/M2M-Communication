import axios from 'axios';

const API_BASE_URL = 'http://127.0.0.1:8000'; // Adjust the base URL as needed

export const runSimulation = async (algorithm, parameters) => {
    try {
        const response = await axios.post(`${API_BASE_URL}/simulate`, {
            algorithm,
            parameters
        });
        return response.data;
    } catch (error) {
        console.error('Error running simulation:', error);
        throw error;
    }
};

export const getComparisonResults = async () => {
    try {
        const response = await axios.get(`${API_BASE_URL}/compare`);
        return response.data;
    } catch (error) {
        console.error('Error fetching comparison results:', error);
        throw error;
    }
};
export async function fetchSimulationResults(params) {
    const response = await fetch('http://localhost:8000/run_simulation', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(params)
    });
    if (!response.ok) {
        throw new Error('Failed to fetch simulation results');
    }
    return await response.json();
}