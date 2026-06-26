// RAG retrieval helpers: remote embeddings plus cosine scoring.

import { fetchRetry, getConfig, _apiHeaders } from "./_shared.js";

// Embed one or more strings and always return a list of vectors.
export async function embed(input, { model = "nvidia/llama-nemotron-embed-1b-v2", inputType = "query" } = {}) {
  /* @doc <code>helpers.embed(text, {model, inputType})</code> ::
       POST to the remote build endpoint <code>{cfg.url}/embeddings</code> (the CORS worker).
       Returns an array of vectors (numbers[]). NVIDIA embed models require <code>inputType:
       "query"</code> or <code>"passage"</code>.
  */
  const cfg = await getConfig();
  const headers = _apiHeaders(cfg);
  const body = {
    input: Array.isArray(input) ? input : [input],
    model,
    input_type: inputType,
  };
  const r = await fetchRetry(`${cfg.url}/embeddings`, {
    method: "POST", headers, body: JSON.stringify(body), credentials: "same-origin",
  });
  if (!r.ok) throw new Error(`embeddings ${r.status}: ${(await r.text()).slice(0, 300)}`);
  const data = await r.json();
  return data.data.map(d => d.embedding);
}

// Score equal-length vectors; closer to 1 means closer match.
export function cosineSim(a, b) {
  /* @doc <code>helpers.cosineSim(a, b)</code> ::
       Cosine similarity between two vectors. Closer to 1 = closer match. The standard retrieval
       primitive.
  */
  let dot = 0, na = 0, nb = 0;
  const n = Math.min(a.length, b.length);
  for (let i = 0; i < n; i++) { dot += a[i] * b[i]; na += a[i] * a[i]; nb += b[i] * b[i]; }
  return dot / (Math.sqrt(na) * Math.sqrt(nb) + 1e-12);
}
