/**
 * Incremental Server-Sent Events parser.
 *
 * EventSource isn't used because it doesn't allow sending the Authorization header: the
 * stream is read with fetch and interpreted here according to the specification
 * (event/data/id/retry fields, comments with ":" and events separated by
 * a blank line).
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
    // The last line may be half-received: it is kept for the next chunk.
    this.buffer = lines.pop() ?? "";

    const messages: SseMessage[] = [];
    for (const line of lines) {
      if (line === "") {
        const message = this.dispatch();
        if (message) messages.push(message);
        continue;
      }
      if (line.startsWith(":")) continue; // comment (keep-alive pings)

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
    // The id is kept (it is the connection's "last event id"); event and retry are reported only once.
    this.event = "";
    this.data = [];
    this.retry = undefined;
    return message;
  }
}
