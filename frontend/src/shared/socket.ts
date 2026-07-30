import type { AudienceReactionKind, ServerMessage } from "./types";

export type ConnectionStatus = "connecting" | "connected" | "disconnected";

interface LiveSocketOptions {
  role: "bet" | "display";
  onMessage: (message: ServerMessage) => void;
  onStatus: (status: ConnectionStatus) => void;
}

type OutboundMessage =
  | { type: "ping" }
  | { type: "sync.request" }
  | {
      type: "audience.react";
      kind: AudienceReactionKind;
      text?: string;
      racer_id?: number;
    };

export class LiveSocket {
  readonly options: LiveSocketOptions;
  private socket: WebSocket | null = null;
  private reconnectAttempt = 0;
  private reconnectTimer: number | null = null;
  private heartbeatTimer: number | null = null;
  private pongTimer: number | null = null;
  private stopped = true;

  constructor(options: LiveSocketOptions) {
    this.options = options;
  }

  start(): void {
    if (!this.stopped) {
      return;
    }
    this.stopped = false;
    this.reconnectAttempt = 0;
    window.addEventListener("offline", this.handleOffline);
    window.addEventListener("online", this.handleOnline);
    this.connect();
  }

  stop(): void {
    this.stopped = true;
    this.clearReconnectTimer();
    this.clearHeartbeatTimer();
    this.clearPongTimer();
    window.removeEventListener("offline", this.handleOffline);
    window.removeEventListener("online", this.handleOnline);
    this.closeCurrentSocket();
  }

  requestSync(): void {
    this.send({ type: "sync.request" });
  }

  reconnect(): void {
    if (this.stopped) {
      return;
    }
    this.clearReconnectTimer();
    this.clearHeartbeatTimer();
    this.clearPongTimer();
    this.closeCurrentSocket();
    this.connect();
  }

  sendReaction(
    kind: AudienceReactionKind,
    options: { text?: string; racer_id?: number } = {},
  ): void {
    this.send({
      type: "audience.react",
      kind,
      text: options.text,
      racer_id: options.racer_id,
    });
  }

  private connect(): void {
    if (this.stopped || !navigator.onLine) {
      return;
    }
    this.clearReconnectTimer();
    this.closeCurrentSocket();
    this.options.onStatus("connecting");
    const scheme = window.location.protocol === "https:" ? "wss" : "ws";
    const url = `${scheme}://${window.location.host}/ws/live/?role=${this.options.role}`;
    const socket = new WebSocket(url);
    this.socket = socket;

    socket.addEventListener("open", () => {
      if (this.socket !== socket) {
        return;
      }
      this.reconnectAttempt = 0;
      this.options.onStatus("connected");
      if (this.heartbeatTimer !== null) {
        window.clearInterval(this.heartbeatTimer);
      }
      this.heartbeatTimer = window.setInterval(() => {
        this.send({ type: "ping" });
        this.clearPongTimer();
        this.pongTimer = window.setTimeout(() => {
          this.pongTimer = null;
          this.reconnect();
        }, 10_000);
      }, 15_000);
    });

    socket.addEventListener("message", (event: MessageEvent<string>) => {
      if (this.socket !== socket) {
        return;
      }
      try {
        const message = JSON.parse(event.data) as ServerMessage;
        if (message.type === "pong") {
          this.clearPongTimer();
        }
        this.options.onMessage(message);
      } catch (error: unknown) {
        console.error("Ignoring malformed live update", error);
      }
    });

    socket.addEventListener("close", () => {
      if (this.socket !== socket) {
        return;
      }
      this.socket = null;
      this.options.onStatus("disconnected");
      this.clearHeartbeatTimer();
      this.clearPongTimer();
      this.scheduleReconnect();
    });

    socket.addEventListener("error", () => {
      if (this.socket === socket) {
        socket.close();
      }
    });
  }

  private send(message: OutboundMessage): void {
    if (this.socket?.readyState === WebSocket.OPEN) {
      this.socket.send(JSON.stringify(message));
    }
  }

  private clearReconnectTimer(): void {
    if (this.reconnectTimer === null) {
      return;
    }
    window.clearTimeout(this.reconnectTimer);
    this.reconnectTimer = null;
  }

  private clearHeartbeatTimer(): void {
    if (this.heartbeatTimer === null) {
      return;
    }
    window.clearInterval(this.heartbeatTimer);
    this.heartbeatTimer = null;
  }

  private clearPongTimer(): void {
    if (this.pongTimer === null) {
      return;
    }
    window.clearTimeout(this.pongTimer);
    this.pongTimer = null;
  }

  private closeCurrentSocket(): void {
    const socket = this.socket;
    this.socket = null;
    socket?.close();
  }

  private scheduleReconnect(): void {
    if (this.stopped || !navigator.onLine || this.reconnectTimer !== null) {
      return;
    }
    const delay = Math.min(750 * 2 ** this.reconnectAttempt, 8_000);
    this.reconnectAttempt += 1;
    this.reconnectTimer = window.setTimeout(() => {
      this.reconnectTimer = null;
      this.connect();
    }, delay);
  }

  private handleOffline = (): void => {
    this.options.onStatus("disconnected");
    this.clearReconnectTimer();
    this.clearHeartbeatTimer();
    this.clearPongTimer();
    this.closeCurrentSocket();
  };

  private handleOnline = (): void => {
    if (this.stopped) {
      return;
    }
    this.reconnect();
  };
}
