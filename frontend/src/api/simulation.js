const API_BASE_URL = process.env.REACT_APP_API_BASE_URL || 'http://127.0.0.1:8000';

export async function fetchSimulationResults(params) {
    const response = await fetch(`${API_BASE_URL}/run_simulation`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(params)
    });
    if (!response.ok) {
        throw new Error('Failed to fetch simulation results');
    }
    return await response.json();
}