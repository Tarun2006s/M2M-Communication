from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from .dqn_agent import DDQNAgent
from .env_wsn import WSNEnv
import numpy as np

app = FastAPI()

origins = [
    "http://localhost:3000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
class SimulationRequest(BaseModel):
    seed: int
    N: int
    episodes: int
    max_steps: int

class SimulationResult(BaseModel):
    rewards: list
    average_lifetime: float
    total_energy: float
    # per-step average state of charge for the final episode
    battery_history: list = []
    # per-step average state of health for the final episode
    soh_history: list = []

@app.post("/run_simulation", response_model=SimulationResult)
async def run_simulation(request: SimulationRequest):
    env = WSNEnv(N=request.N, max_steps=request.max_steps, seed=request.seed)
    state_dim = env.observation_space.shape[0]
    action_dim = 2
    agent = DDQNAgent(state_dim, action_dim, node_count=request.N)

    rewards_history = []
    steps_alive_history = []
    total_energy = 0.0
    battery_history = []
    soh_history = []

    for ep in range(request.episodes):
        state = env.reset()
        ep_reward = 0.0
        done = False
        steps_alive = 0
        ep_energy = 0.0

        # per-step histories for this episode
        ep_soc = []
        ep_soh = []

        while not done:
            action = agent.select_action(state)
            next_state, reward, done, info = env.step(action)

            # record battery stats for the current step
            socs = [b.soc for b in env.batteries]
            soh_vals = [b.soh for b in env.batteries]
            avg_soc = np.mean(socs) / env.batteries[0].E_max
            avg_soh = np.mean(soh_vals)
            ep_soc.append(avg_soc)
            ep_soh.append(avg_soh)

            agent.store(state, action, reward, next_state, done)
            agent.train_step()

            state = next_state
            ep_reward += reward
            steps_alive += 1
            if 'total_energy' in info:
                ep_energy += info['total_energy']

        rewards_history.append(ep_reward)
        steps_alive_history.append(steps_alive)
        total_energy += ep_energy

        # keep last episode history for return value
        if ep == request.episodes - 1:
            battery_history = ep_soc.copy()
            soh_history = ep_soh.copy()

    average_lifetime = float(np.mean(steps_alive_history)) if steps_alive_history else 0.0

    return SimulationResult(
        rewards=rewards_history,
        average_lifetime=average_lifetime,
        total_energy=total_energy
    )

@app.get("/")
async def root():
    return {"message": "Welcome to the DQN Battery Scheduling API!"}