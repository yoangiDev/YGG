/**
 * Parser incremental de Server-Sent Events.
 *
 * No se usa EventSource porque no permite enviar la cabecera Authorization: el
 * stream se lee con fetch y se interpreta aquí según la especificación
 * (campos event/data/id/retry, comentarios con ":" y eventos separados por
 * una línea en blanco).
 */

export interface SseMessage {
  event: string;
  data: string;
  id?: string;
  retry?: number;
}

export class SseParser {
  private buffer = "";
  private event = "";
  private data: string[] = [];
  private id: string | undefined;
  private retry: number | undefined;

  feed(chunk: string): SseMessage[] {
    this.buffer += chunk;
    const lines = this.buffer.split(/\r\n|\r|\n/);
    // La última línea puede estar a medias: se guarda para el siguiente trozo.
    this.buffer = lines.pop() ?? "";

    const messages: SseMessage[] = [];
    for (const line of lines) {
      if (line === "") {
        const message = this.dispatch();
        if (message) messages.push(message);
        continue;
      }
      if (line.startsWith(":")) continue; // comentario (pings de keep-alive)

      const colon = line.indexOf(":");
      const field = colon === -1 ? line : line.slice(0, colon);
      let value = colon === -1 ? "" : line.slice(colon + 1);
      if (value.startsWith(" ")) value = value.slice(1);

      switch (field) {
        case "event":
          this.event = value;
          break;
        case "data":
          this.data.push(value);
          break;
        case "id":
          this.id = value;
          break;
        case "retry": {
          const retry = Number.parseInt(value, 10);
          if (!Number.isNaN(retry)) this.retry = retry;
          break;
        }
      }
    }
    return messages;
  }

  private dispatch(): SseMessage | null {
    if (this.data.length === 0) {
      this.event = "";
      return null;
    }
    const message: SseMessage = { event: this.event || "message", data: this.data.join("\n") };
    if (this.id !== undefined) message.id = this.id;
    if (this.retry !== undefined) message.retry = this.retry;
    // El id se conserva (es el "last event id" de la conexión); event y retry se informan una sola vez.
    this.event = "";
    this.data = [];
    this.retry = undefined;
    return message;
  }
}
