const response = await fetch("https://ks3s7uf6ww2m3o7rj2uum6pska0cvdbc.lambda-url.ap-northeast-1.on.aws/articles/stream?question=what+is+websocket");
const reader = response.body.getReader();
const decoder = new TextDecoder();
let buffer = "";

try {
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value);
    const lines = buffer.split("\n");
    buffer = lines.pop();

    for (const line of lines) {
      if (!line.trim()) continue;
      console.log(JSON.parse(line));
    }
  }
} catch (err) {
  if (err?.cause?.code === "UND_ERR_SOCKET") {
    // server closed the connection after streaming finished — not a real error
  } else {
    throw err;
  }
}