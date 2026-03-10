# env_wsn.py
import numpy as np
import gymnasium as gym
from gym import spaces

class BatteryModel:
    """
    Simple battery model with SoC and SoH.
    SoC: available energy (0..E_max).
    SoH: health percentage (0..1). Degrades with deep discharge cycles.
    We'll implement a per-step degradation rule:
      - A small calendar fade each timestep (very small)
      - Cycle-related degradation: degradation ∝ (DoD)^alpha * k
    This is a simplified model (justify vs literature in paper).
    """
    def __init__(self, E_max=100.0, soh_init=1.0, k_cycle=1e-4, alpha=1.2, calendar_decay=1e-6):
        self.E_max = E_max
        self.soc = E_max
        self.soh = soh_init
        self.k_cycle = k_cycle
        self.alpha = alpha
        self.calendar_decay = calendar_decay
        self.prev_soc = self.soc

    def discharge(self, energy_draw):
        # energy_draw >= 0
        self.prev_soc = self.soc
        self.soc = max(0.0, self.soc - energy_draw)
        # compute DoD for this small step relative to capacity (percentage)
        dod = abs(self.prev_soc - self.soc) / self.E_max  # 0..1
        # apply cycle-related degradation (approximation)
        if dod > 0:
            self.soh -= self.k_cycle * (dod ** self.alpha)
        # apply calendar fade
        self.soh -= self.calendar_decay
        self.soh = max(0.0, min(1.0, self.soh))

    def charge(self, energy_add):
        self.prev_soc = self.soc
        self.soc = min(self.E_max, self.soc + energy_add)
        # charging stress could also affect soh slightly; skip or add small positive effect
        # keep it simple for now.

    def is_dead(self, soc_threshold=0.01, soh_threshold=0.05):
        return (self.soc <= soc_threshold) or (self.soh <= soh_threshold)

class WSNEnv(gym.Env):
    """
    Gym-like environment for WSN sleep/awake scheduling with battery SoH.
    Centralized action vector: for N nodes, action vector length N with discrete choices:
      0 -> SLEEP
      1 -> AWAKE
    Observation: concatenated per-node features:
      - soc_normalized (0..1)
      - soh (0..1)
      - last_action (0 or 1)
      - distance_to_sink_normalized (0..1)
      - recent_activity_ratio (0..1)
    """
    metadata = {'render.modes': ['human']}

    def __init__(self, N=10, arena_size=(500,500), sink=(250,250), timestep_energy_awake=1.0,
                 energy_sleep=0.01, max_steps=10000, seed=None):
        super().__init__()
        self.N = N
        self.arena_size = arena_size
        self.sink = np.array(sink, dtype=float)
        self.timestep_energy_awake = timestep_energy_awake
        self.energy_sleep = energy_sleep
        self.max_steps = max_steps
        self.step_count = 0
        self.rng = np.random.RandomState(seed)

        # initialize node positions
        self.positions = self.rng.rand(N, 2) * np.array(arena_size)
        # distances to sink normalized
        dists = np.linalg.norm(self.positions - self.sink, axis=1)
        self.dist_norm = dists / np.sqrt(arena_size[0]**2 + arena_size[1]**2)

        # battery models
        self.batteries = [BatteryModel(E_max=100.0, soh_init=1.0,
                                       k_cycle=5e-5, alpha=1.2, calendar_decay=5e-7)
                          for _ in range(N)]

        # for each node track last action and recent activity (sliding window)
        self.last_action = np.zeros(N, dtype=int)
        self.recent_activity = np.zeros(N, dtype=float)  # exponential moving avg

        # observation and action spaces
        obs_dim_per_node = 5
        self.observation_space = spaces.Box(low=0.0, high=1.0, shape=(N * obs_dim_per_node,), dtype=np.float32)
        # action space - discrete options per node, we flatten into MultiDiscrete
        self.action_space = spaces.MultiDiscrete([2] * N)  # each node: 0 or 1

    def reset(self):
        self.step_count = 0
        self.positions = self.rng.rand(self.N, 2) * np.array(self.arena_size)
        dists = np.linalg.norm(self.positions - self.sink, axis=1)
        self.dist_norm = dists / np.sqrt(self.arena_size[0]**2 + self.arena_size[1]**2)
        self.batteries = [BatteryModel(E_max=100.0, soh_init=1.0,
                                       k_cycle=5e-5, alpha=1.2, calendar_decay=5e-7)
                          for _ in range(self.N)]
        self.last_action = np.zeros(self.N, dtype=int)
        self.recent_activity = np.zeros(self.N, dtype=float)
        return self._get_obs()

    def _get_obs(self):
        obs = []
        for i in range(self.N):
            soc = self.batteries[i].soc / self.batteries[i].E_max
            soh = self.batteries[i].soh
            la = float(self.last_action[i])
            d = self.dist_norm[i]
            ra = self.recent_activity[i]
            obs.extend([soc, soh, la, d, ra])
        return np.array(obs, dtype=np.float32)

    def step(self, action):
        """
        action: array-like of length N with values 0/1
        returns: obs, reward, done, info
        """
        assert len(action) == self.N
        self.step_count += 1

        # simulate energy draw & battery update
        total_energy_used = 0.0
        coverage_active = 0
        for i, a in enumerate(action):
            if a == 1:  # awake
                energy_draw = self.timestep_energy_awake * (1 + 0.1 * self.dist_norm[i])  # distance penalty
                self.batteries[i].discharge(energy_draw)
                self.recent_activity[i] = 0.9 * self.recent_activity[i] + 0.1 * 1.0
                coverage_active += 1
                total_energy_used += energy_draw
            else:  # sleep
                self.batteries[i].discharge(self.energy_sleep)  # tiny leakage
                self.recent_activity[i] = 0.9 * self.recent_activity[i] + 0.1 * 0.0
                total_energy_used += self.energy_sleep

            self.last_action[i] = int(a)

        # compute SoH changes included in battery model (already updated by discharge).

        # reward components
        # 1) coverage reward (normalize by N)
        coverage_ratio = coverage_active / self.N
        r_coverage = coverage_ratio  # reward 0..1

        # 2) energy penalty (we want low energy usage)
        # scale so typical energy draws (N＊timestep) map to order 0..1
        r_energy = - (total_energy_used / (self.N * self.timestep_energy_awake * 2.0))

        # 3) SoH penalty - we penalize rapid SoH loss: compute average SoH drop this step
        avg_soh = np.mean([b.soh for b in self.batteries])
        # For reward we want higher SoH -> positive; but we penalize SoH decline
        # keep a running baseline of initial SoH (1.0)
        r_soh = avg_soh - 0.99  # small positive if SoH near 1.0, negative if dips below 0.99

        # 4) fairness / balance reward - penalize nodes with very low SoC vs average
        socs = np.array([b.soc for b in self.batteries])
        soc_std = np.std(socs) / (self.batteries[0].E_max + 1e-9)
        r_balance = - soc_std

        # combined reward
        # weights must be tuned; start with these values and justify in paper
        reward = 3.0 * r_coverage + 1.0 * r_energy + 25.0 * r_soh + 1.0 * r_balance

        # detect terminal: if too many nodes are dead -> episode ends
        dead_nodes = sum([1 for b in self.batteries if b.is_dead()])
        done = False
        if dead_nodes > 0.3 * self.N:  # alarm: >30% nodes dead
            done = True
            reward -= 10.0  # heavy penalty
        if self.step_count >= self.max_steps:
            done = True

        info = {
            'total_energy': total_energy_used,
            'coverage_ratio': coverage_ratio,
            'avg_soh': avg_soh,
            'dead_nodes': dead_nodes
        }

        return self._get_obs(), float(reward), done, info

    def render(self, mode='human'):
        # simple text render
        socs = [round(b.soc,1) for b in self.batteries]
        sohs = [round(b.soh,3) for b in self.batteries]
        print(f"Step {self.step_count}: socs={socs}, sohs={sohs}")