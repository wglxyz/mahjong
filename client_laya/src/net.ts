// Thin WebSocket client. Same origin as the page (served under /laya/), so it
// connects to ws://<host>/ — the Python server upgrades WS on any path.
import type { ServerMsg } from "./protocol";

export class Net {
  private ws: WebSocket | null = null;
  onMessage: (m: ServerMsg) => void = () => {};
  onStatus: (s: string) => void = () => {};

  connect() {
    const url = (location.protocol === "https:" ? "wss:" : "ws:") + "//" + location.host + "/";
    this.onStatus("connecting " + url);
    const ws = new WebSocket(url);
    this.ws = ws;
    ws.onopen = () => { this.onStatus("connected"); this.requestSnapshot(); };
    ws.onclose = (e) => this.onStatus("disconnected (" + e.code + ")");
    ws.onerror = () => this.onStatus("error");
    ws.onmessage = (ev) => {
      let m: ServerMsg;
      try { m = JSON.parse(ev.data as string); } catch { return; }
      this.onMessage(m);
    };
  }

  private send(obj: any) { if (this.ws && this.ws.readyState === WebSocket.OPEN) this.ws.send(JSON.stringify(obj)); }
  decide(actionId: string) { this.send({ type: "decide", action_id: actionId }); }
  requestSnapshot() { this.send({ type: "request_snapshot" }); }
}
