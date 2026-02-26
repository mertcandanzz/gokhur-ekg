"""
EKG Monitor - FastAPI Backend
ESP32'den WebSocket ile veri alir, tarayicilara iletir.
Gercekci simulasyon motoru: HRV, baseline wander, kas artefakti, solunum modulasyonu.
"""

import asyncio
import math
import random
import time

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path

app = FastAPI(title="EKG Monitor")

app.mount("/static", StaticFiles(directory=Path(__file__).parent / "static"), name="static")

clients: set[WebSocket] = set()

sim_task: asyncio.Task | None = None
sim_running = False

last_data = {"value": 0, "lead_off": False, "device_connected": False, "timestamp": 0}

# Panik modu durumu (0.0 = normal, 1.0 = tam panik)
panic_level = 0.0
panic_target = 0.0


@app.get("/", response_class=HTMLResponse)
async def index():
    html_path = Path(__file__).parent / "static" / "index.html"
    return html_path.read_text(encoding="utf-8")


@app.websocket("/ws/device")
async def device_ws(ws: WebSocket):
    await ws.accept()
    last_data["device_connected"] = True
    await broadcast({"type": "device_status", "connected": True})

    try:
        while True:
            raw = await ws.receive_text()
            last_data["timestamp"] = time.time()
            lines = raw.strip().split("\n")
            values = []
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                if line == "!":
                    last_data["lead_off"] = True
                    values.append("!")
                else:
                    last_data["lead_off"] = False
                    last_data["value"] = int(line)
                    values.append(line)
            if values:
                await broadcast({"type": "ekg", "d": values})
    except WebSocketDisconnect:
        pass
    finally:
        last_data["device_connected"] = False
        await broadcast({"type": "device_status", "connected": False})


@app.websocket("/ws/client")
async def client_ws(ws: WebSocket):
    global panic_target
    await ws.accept()
    clients.add(ws)

    await ws.send_json({
        "type": "device_status",
        "connected": last_data["device_connected"],
        "sim": sim_running,
    })

    try:
        while True:
            msg = await ws.receive_json()
            cmd = msg.get("cmd")

            if cmd == "sim_start":
                await start_simulation()
            elif cmd == "sim_stop":
                await stop_simulation()
            elif cmd == "panic_on":
                panic_target = 1.0
            elif cmd == "panic_off":
                panic_target = 0.0

    except WebSocketDisconnect:
        pass
    finally:
        clients.discard(ws)


async def broadcast(data: dict):
    dead = set()
    for c in clients:
        try:
            await c.send_json(data)
        except Exception:
            dead.add(c)
    clients.difference_update(dead)


# ================================================================
# GERCEKCI EKG SIMULASYON MOTORU
# ================================================================

class EKGSimulator:
    def __init__(self):
        self.t = 0.0               # global zaman (saniye)
        self.dt = 0.002            # sample araligi (500 Hz)
        self.beat_phase = 0.0      # mevcut atim icindeki faz (0-1)
        self.beat_duration = 0.85  # mevcut atim suresi (saniye)
        self.next_beat_duration = 0.85

        # Per-beat varyasyon state
        self.p_amp = 30.0
        self.r_amp = 270.0
        self.s_amp = 40.0
        self.t_amp = 50.0
        self.q_amp = 22.0

        # Timing varyasyonlari
        self.p_start = 0.10
        self.qrs_start = 0.24
        self.t_start = 0.42

        # QRS genisligi
        self.qrs_width = 0.05

        # Baseline wander (solunum ~0.2 Hz + yavas drift ~0.05 Hz)
        self.baseline = 512.0
        self.baseline_drift_phase = random.uniform(0, 2 * math.pi)
        self.resp_phase = random.uniform(0, 2 * math.pi)

        # Kas artefakti state
        self.muscle_burst_until = 0.0
        self.muscle_intensity = 0.0

        # 50Hz powerline (cok hafif)
        self.powerline_phase = 0.0

        # Ilk atim parametrelerini ayarla
        self.new_beat_params(0.0)

    def new_beat_params(self, panic: float):
        """Her yeni atimda parametreleri hafifce degistir (beat-to-beat variability)"""

        # Normal: ~70 BPM (0.85s), Panik: ~165 BPM (0.36s)
        base_duration = 0.85 * (1 - panic) + 0.36 * panic

        # HRV: normal %5-8 varyasyon, panik'te %2-3 (daha rigid)
        hrv_std = 0.06 * (1 - panic * 0.7)
        self.next_beat_duration = base_duration + random.gauss(0, base_duration * hrv_std)
        self.next_beat_duration = max(0.30, min(1.2, self.next_beat_duration))

        # Amplitüd varyasyonlari (her atimda %5-15 fark)
        self.p_amp = (28 + random.gauss(0, 4)) * (1 - panic * 0.3)
        self.r_amp = 270 + random.gauss(0, 25) + panic * 40
        self.s_amp = 38 + random.gauss(0, 6)
        self.t_amp = (48 + random.gauss(0, 7)) * (1 - panic * 0.25)
        self.q_amp = 22 + random.gauss(0, 4)

        # Timing micro-varyasyonlari
        self.p_start = 0.10 + random.gauss(0, 0.008)
        self.qrs_start = 0.24 + random.gauss(0, 0.005)
        self.t_start = 0.42 + random.gauss(0, 0.012)

        # Panik'te QRS biraz daralir
        self.qrs_width = 0.05 * (1 - panic * 0.15)

    def generate_sample(self, panic: float) -> int:
        """Tek bir EKG sample'i uret"""

        # Faz ilerlet
        phase_inc = self.dt / self.beat_duration
        self.beat_phase += phase_inc

        # Yeni atim baslangici
        if self.beat_phase >= 1.0:
            self.beat_phase -= 1.0
            self.beat_duration = self.next_beat_duration
            self.new_beat_params(panic)

        cycle = self.beat_phase
        val = 0.0

        # ---- PQRST dalga formu ----

        # P dalgasi
        p_end = self.p_start + 0.09 + random.gauss(0, 0.002)
        if self.p_start < cycle < p_end:
            p_phase = (cycle - self.p_start) / (p_end - self.p_start)
            val += math.sin(p_phase * math.pi) * self.p_amp
            # P dalgasi hafif asimetri
            if p_phase > 0.6:
                val *= 0.92

        # Q dalgasi
        q_start = self.qrs_start - 0.025
        if q_start < cycle < self.qrs_start:
            q_phase = (cycle - q_start) / 0.025
            val -= math.sin(q_phase * math.pi) * self.q_amp

        # R dalgasi (keskin tepe)
        r_end = self.qrs_start + self.qrs_width
        if self.qrs_start < cycle < r_end:
            r_phase = (cycle - self.qrs_start) / self.qrs_width
            # Daha keskin peak icin power curve
            peak = math.sin(r_phase * math.pi)
            peak = peak ** 0.7  # keskinlestir
            val += peak * self.r_amp

        # S dalgasi
        s_start = self.qrs_start + self.qrs_width
        s_end = s_start + 0.035
        if s_start < cycle < s_end:
            s_phase = (cycle - s_start) / 0.035
            val -= math.sin(s_phase * math.pi) * self.s_amp

        # ST segment (hafif elevasyon/depresyon varyasyonu)
        st_start = s_end
        st_end = self.t_start
        if st_start < cycle < st_end:
            st_phase = (cycle - st_start) / max(0.01, st_end - st_start)
            st_dev = random.gauss(0, 1.5) + panic * 5  # panik'te hafif ST degisimi
            val += st_dev * math.sin(st_phase * math.pi * 0.5)

        # T dalgasi
        t_width = 0.14 + random.gauss(0, 0.003)
        t_end = self.t_start + t_width
        if self.t_start < cycle < t_end:
            t_phase = (cycle - self.t_start) / t_width
            # T dalgasi asimetrik (yavaş yükselis, hızlı düsüs)
            if t_phase < 0.45:
                t_shape = math.sin(t_phase / 0.45 * math.pi / 2)
            else:
                t_shape = math.cos((t_phase - 0.45) / 0.55 * math.pi / 2)
            val += t_shape * self.t_amp

        # ---- BASELINE WANDER ----

        # Solunum kaynakli (~0.2 Hz, ~15 birim amplitüd)
        self.resp_phase += self.dt * 0.2 * 2 * math.pi
        resp_wander = math.sin(self.resp_phase) * (12 + panic * 8)
        # Solunum harmonigi (gercekcilik)
        resp_wander += math.sin(self.resp_phase * 2.3) * 3

        # Yavas baseline drift (~0.05 Hz)
        self.baseline_drift_phase += self.dt * 0.05 * 2 * math.pi
        slow_drift = math.sin(self.baseline_drift_phase) * 8

        # Panik'te daha fazla baseline instabilite
        panic_drift = 0
        if panic > 0.1:
            panic_drift = math.sin(self.t * 0.7 * 2 * math.pi) * panic * 10

        val += resp_wander + slow_drift + panic_drift

        # ---- KAS ARTEFAKTI ----

        # Rastgele kas burst'leri (panik modda daha sik)
        burst_prob = 0.0004 + panic * 0.003
        if random.random() < burst_prob and self.t > self.muscle_burst_until:
            self.muscle_burst_until = self.t + random.uniform(0.05, 0.3 + panic * 0.5)
            self.muscle_intensity = random.uniform(3, 12 + panic * 15)

        if self.t < self.muscle_burst_until:
            # Yuksek frekansli kas gurultusu
            val += random.gauss(0, self.muscle_intensity)
            # Burst sonuna dogru azal
            remaining = self.muscle_burst_until - self.t
            if remaining < 0.05:
                val *= remaining / 0.05

        # ---- ELEKTRONIK GURULTU ----

        # Gaussian (termal) gurultu - AD8232 benzeri
        val += random.gauss(0, 2.5 + panic * 1.5)

        # 50 Hz powerline (cok hafif)
        self.powerline_phase += self.dt * 50 * 2 * math.pi
        val += math.sin(self.powerline_phase) * 1.2

        # ---- FINAL ----
        self.t += self.dt
        final = self.baseline + val
        return max(0, min(1023, int(final)))


# Global simulator instance
simulator = EKGSimulator()


async def simulation_loop():
    global sim_running, panic_level
    sim_running = True
    last_data["device_connected"] = True
    await broadcast({"type": "device_status", "connected": True, "sim": True})

    batch_size = 10  # Her 20ms'de 10 sample

    try:
        while sim_running:
            # Panic level'i hedefe dogru yumusak gecis
            if panic_level < panic_target:
                # Panik baslangici: hizli yukselis (~3 saniye)
                panic_level = min(panic_target, panic_level + 0.007)
            elif panic_level > panic_target:
                # Panik bitis: yavas dusus (~8 saniye)
                panic_level = max(panic_target, panic_level - 0.0025)

            values = []
            for _ in range(batch_size):
                values.append(str(simulator.generate_sample(panic_level)))

            msg = {"type": "ekg", "d": values}
            if panic_level > 0.01:
                msg["panic"] = round(panic_level, 2)

            await broadcast(msg)
            await asyncio.sleep(simulator.dt * batch_size)
    except asyncio.CancelledError:
        pass
    finally:
        sim_running = False
        panic_level = 0.0
        last_data["device_connected"] = False
        await broadcast({"type": "device_status", "connected": False, "sim": False})


async def start_simulation():
    global sim_task, sim_running, simulator
    if sim_running:
        return
    simulator = EKGSimulator()
    sim_task = asyncio.create_task(simulation_loop())


async def stop_simulation():
    global sim_task, sim_running, panic_level, panic_target
    sim_running = False
    panic_level = 0.0
    panic_target = 0.0
    if sim_task:
        sim_task.cancel()
        sim_task = None


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
