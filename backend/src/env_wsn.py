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

    Battery state is stored as flat numpy arrays (``self.soc``, ``self.soh``)
    instead of per-node Python objects, enabling fully vectorised step and
    observation computation.  This gives a large speed-up for large N.
    """
    metadata = {'render.modes': ['human']}

    # Battery parameters (same as the old BatteryModel defaults used in _create_batteries)
    E_max: float = 100.0
    _k_cycle: float = 5e-5
    _alpha: float = 1.2
    _calendar_decay: float = 5e-7
    _soc_dead: float = 0.01
    _soh_dead: float = 0.05

    def __init__(self, N=10, arena_size=(500, 500), sink=(250, 250),
                 timestep_energy_awake=1.0, energy_sleep=0.01,
                 max_steps=10000, seed=None):
        super().__init__()
        self.N = N
        self.arena_size = arena_size
        self.sink = np.array(sink, dtype=float)
        self.timestep_energy_awake = timestep_energy_awake
        self.energy_sleep = energy_sleep
        self.max_steps = max_steps
        self.step_count = 0
        self.rng = np.random.RandomState(seed)

        # initialize node positions and distances to sink
        self.positions = self.rng.rand(N, 2) * np.array(arena_size)
        dists = np.linalg.norm(self.positions - self.sink, axis=1)
        self.dist_norm = dists / np.sqrt(arena_size[0] ** 2 + arena_size[1] ** 2)

        # Vectorised battery state (replaces list of BatteryModel objects)
        self.soc = np.full(N, self.E_max, dtype=np.float64)   # state of charge per node
        self.soh = np.ones(N, dtype=np.float64)                # state of health per node

        # per-node tracking
        self.last_action = np.zeros(N, dtype=np.int32)
        self.recent_activity = np.zeros(N, dtype=np.float64)   # exponential moving avg

        # observation and action spaces
        obs_dim_per_node = 5
        self.observation_space = spaces.Box(
            low=0.0, high=1.0, shape=(N * obs_dim_per_node,), dtype=np.float32
        )
        self.action_space = spaces.MultiDiscrete([2] * N)  # each node: 0 or 1

    def reset(self):
        self.step_count = 0
        self.positions = self.rng.rand(self.N, 2) * np.array(self.arena_size)
        dists = np.linalg.norm(self.positions - self.sink, axis=1)
        self.dist_norm = dists / np.sqrt(self.arena_size[0] ** 2 + self.arena_size[1] ** 2)
        self.soc = np.full(self.N, self.E_max, dtype=np.float64)
        self.soh = np.ones(self.N, dtype=np.float64)
        self.last_action = np.zeros(self.N, dtype=np.int32)
        self.recent_activity = np.zeros(self.N, dtype=np.float64)
        return self._get_obs()

    def _get_obs(self):
        # Stack per-node feature columns and flatten — fully vectorised, no Python loop.
        obs = np.column_stack([
            self.soc / self.E_max,
            self.soh,
            self.last_action.astype(np.float32),
            self.dist_norm,
            self.recent_activity,
        ]).astype(np.float32)
        return obs.ravel()

    def step(self, action):
        """
        action: array-like of length N with values 0/1
        returns: obs, reward, done, info
        """
        action = np.asarray(action)
        assert action.shape == (self.N,)
        self.step_count += 1

        awake_mask = action == 1

        # Vectorised energy draw: awake nodes pay distance-scaled cost, sleeping nodes pay leakage.
        energy_draw = np.where(
            awake_mask,
            self.timestep_energy_awake * (1.0 + 0.1 * self.dist_norm),
            self.energy_sleep,
        )

        # Update SoC and compute per-node depth-of-discharge for SoH degradation.
        prev_soc = self.soc.copy()
        self.soc = np.maximum(0.0, self.soc - energy_draw)
        dod = (prev_soc - self.soc) / self.E_max  # always >= 0

        # Update SoH: cycle degradation + calendar fade (vectorised).
        # Use boolean indexing to avoid creating a zero-filled intermediate array.
        cycle_mask = dod > 0
        self.soh[cycle_mask] -= self._k_cycle * (dod[cycle_mask] ** self._alpha)
        self.soh -= self._calendar_decay
        np.clip(self.soh, 0.0, 1.0, out=self.soh)

        # Update recent activity (exponential moving average) and last action.
        self.recent_activity = 0.9 * self.recent_activity + 0.1 * awake_mask.astype(np.float64)
        self.last_action = action.astype(np.int32)

        total_energy_used = float(energy_draw.sum())
        coverage_active = int(awake_mask.sum())

        # reward components
        # 1) coverage reward (normalize by N)
        coverage_ratio = coverage_active / self.N
        r_coverage = coverage_ratio  # reward 0..1

        # 2) energy penalty (we want low energy usage)
        # scale so typical energy draws (N＊timestep) map to order 0..1
        r_energy = -(total_energy_used / (self.N * self.timestep_energy_awake * 2.0))

        # 3) SoH penalty - we penalize rapid SoH loss: compute average SoH drop this step
        avg_soh = float(self.soh.mean())
        # For reward we want higher SoH -> positive; but we penalize SoH decline
        # keep a running baseline of initial SoH (1.0)
        r_soh = avg_soh - 0.99  # small positive if SoH near 1.0, negative if dips below 0.99

        # 4) fairness / balance reward - penalize nodes with very low SoC vs average
        soc_std = float(self.soc.std()) / (self.E_max + 1e-9)
        r_balance = -soc_std

        # combined reward
        # weights must be tuned; start with these values and justify in paper
        reward = 3.0 * r_coverage + 1.0 * r_energy + 25.0 * r_soh + 1.0 * r_balance

        # detect terminal: if too many nodes are dead -> episode ends
        dead_nodes = int(((self.soc <= self._soc_dead) | (self.soh <= self._soh_dead)).sum())
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
            'dead_nodes': dead_nodes,
        }

        return self._get_obs(), float(reward), done, info

    def render(self, mode='human'):
        # simple text render
        socs = np.round(self.soc, 1).tolist()
        sohs = np.round(self.soh, 3).tolist()
        print(f"Step {self.step_count}: socs={socs}, sohs={sohs}")