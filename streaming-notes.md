# HTTP Streaming Notes

## Mechanism: HTTP Chunked Transfer Encoding

Not SSE, not WebSocket. Plain HTTP/1.1 feature (RFC 7230).

When the server omits `Content-Length` and sets `Transfer-Encoding: chunked`, it can send the response body in pieces:

```
HTTP/1.1 200 OK
Transfer-Encoding: chunked
Content-Type: application/x-ndjson

1a\r\n
{"type":"query","data":"..."}\n
\r\n
2f\r\n
{"type":"tags","data":[...]}\n
\r\n
0\r\n        ← zero signals end of stream
\r\n
```

The client processes each chunk as it arrives without waiting for the full body.

---

## Response Format: NDJSON (Newline-Delimited JSON)

Each chunk is one JSON object followed by `\n`. Simple to produce, simple to parse.

```
{"type":"query","data":"what is websocket?"}\n
{"type":"tags","data":["networking","web-socket"]}\n
{"type":"titles","data":["Article A","Article B"]}\n
{"type":"token","data":"Web"}\n
{"type":"token","data":"sockets"}\n
{"type":"done"}\n
```

Alternative: SSE (`text/event-stream`) uses the same chunked mechanism but with a specific format (`data: ...\n\n`) and built-in reconnect logic. NDJSON is simpler when you don't need reconnect.

---

## Python / FastAPI

`StreamingResponse` sets `Transfer-Encoding: chunked` automatically. Each `yield` flushes one chunk immediately.

```python
from fastapi.responses import StreamingResponse
import json

@app.get("/articles/stream")
async def answer_stream(question: str):
    async def generate():
        yield json.dumps({"type": "query", "data": "..."}) + "\n"
        yield json.dumps({"type": "tags",  "data": [...]}) + "\n"

        # stream OpenAI tokens
        stream = client.chat.completions.create(model=..., messages=..., stream=True)
        for chunk in stream:
            delta = chunk.choices[0].delta.content
            if delta:
                yield json.dumps({"type": "token", "data": delta}) + "\n"

        yield json.dumps({"type": "done"}) + "\n"

    return StreamingResponse(generate(), media_type="application/x-ndjson")
```

---

## Node.js / Express

`res.write()` sends a chunk immediately. `res.end()` closes the stream. Express uses chunked transfer automatically when `res.write()` is called before `res.end()`.

```javascript
app.get("/articles/stream", async (req, res) => {
    res.setHeader("Content-Type", "application/x-ndjson");

    res.write(JSON.stringify({ type: "query", data: query }) + "\n");
    res.write(JSON.stringify({ type: "tags",  data: tags  }) + "\n");

    const stream = await openai.chat.completions.create({ stream: true, ... });
    for await (const chunk of stream) {
        const delta = chunk.choices[0]?.delta?.content;
        if (delta) res.write(JSON.stringify({ type: "token", data: delta }) + "\n");
    }

    res.write(JSON.stringify({ type: "done" }) + "\n");
    res.end();
});
```

---

## Client: fetch (Browser / Node.js)

`fetch` exposes the response body as a `ReadableStream`. Read chunks with `.getReader()`.

```javascript
const response = await fetch("/articles/stream?question=...");
const reader = response.body.getReader();
const decoder = new TextDecoder();
let buffer = "";

try {
    while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value);
        const lines = buffer.split("\n");
        buffer = lines.pop(); // keep incomplete last line in buffer

        for (const line of lines) {
            if (!line.trim()) continue;
            const event = JSON.parse(line);

            if (event.type === "query")  setQuery(event.data);
            if (event.type === "tags")   setTags(event.data);
            if (event.type === "titles") setTitles(event.data);
            if (event.type === "token")  setAnswer(prev => prev + event.data);
        }
    }
} catch (err) {
    // Node's undici throws UND_ERR_SOCKET when server closes connection after stream ends
    if (err?.cause?.code === "UND_ERR_SOCKET") {
        // not a real error — stream was fully consumed
    } else {
        throw err;
    }
}
```

**Why buffer splitting matters:** a single `read()` call may contain multiple JSON lines, or a line may be split across two `read()` calls. Always accumulate into a buffer and split on `\n`.

---

## Client: axios (Browser only)

Axios has limited streaming support. Use `onDownloadProgress` — note it gives the **cumulative** text so far, not just the new chunk.

```javascript
await axios.get("/articles/stream", {
    params: { question },
    responseType: "text",
    onDownloadProgress: (e) => {
        const fullText = e.event.target.responseText; // cumulative
        // parse lines from fullText
    }
});
```

Prefer native `fetch` for streaming — it gives true chunk-by-chunk control.

---

## Lambda Streaming (AWS)

Standard Lambda + API Gateway **always buffers** the full response — chunked encoding is stripped at the gateway.

To stream from Lambda you must:
1. Use **Lambda Function URL** (not API Gateway) with `InvokeMode: RESPONSE_STREAM`
2. Remove Mangum (it's a buffered adapter) or use Mangum v0.17+ streaming mode

### Serverless Framework v3 — correct configuration

**Serverless v3 does NOT support `url.invokeMode` directly.** Setting it there causes a CloudFormation `EarlyValidation` error:
> Could not create Change Set due to: AWS::EarlyValidation::PropertyValidation

The fix is to declare `url` without `invokeMode`, then patch the generated `AWS::Lambda::Url` resource via `resources.extensions`:

```yaml
functions:
  app:
    handler: handler.handler
    url:
      cors:
        allowedOrigins:
          - https://your-frontend.com
          - http://localhost:3000
        allowedHeaders:
          - content-type
          - authorization
        allowedMethods:
          - GET
          - POST
          - OPTIONS

resources:
  extensions:
    AppLambdaFunctionUrl:      # CloudFormation logical ID auto-generated by Serverless
      Properties:
        InvokeMode: RESPONSE_STREAM
```

`AppLambdaFunctionUrl` is the logical ID Serverless generates for the `app` function's URL resource. For a function named `foo` it would be `FooLambdaFunctionUrl`.

The function URL looks like: `https://<id>.lambda-url.<region>.on.aws/`

---

## Comparison: SSE vs WebSocket vs Chunked HTTP

| | Chunked HTTP | SSE | WebSocket |
|---|---|---|---|
| Direction | Server → Client only | Server → Client only | Bidirectional |
| Protocol | Plain HTTP | HTTP (`text/event-stream`) | Protocol upgrade |
| Reconnect | None | Built-in | Manual |
| Format | Any | `data: ...\n\n` | Any |
| Complexity | Lowest | Low | Higher |
| Use case | One-shot stream (RAG answer) | Live feeds, notifications | Chat, real-time collab |
