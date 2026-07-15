# Browser Python wheel acquisition

`wheels.lock.json` is the authoritative inventory for the Python wheels copied into this internal course candidate. The learner receives these files. Each row records the exact file, SHA-256, upstream artifact, license expression, and whether the source course imports it directly or obtains it through another package.

Pure-Python wheels and the published `uuid-utils` Pyodide wheel are downloaded from the exact `source_url` in the lock. Verify each download before use:

```bash
python3 scripts/pyodide/verify_cfx11_wheels.py
```

`pyahocorasick` and `ormsgpack` do not publish compatible Pyodide 314 wheels. They are built from the recorded source archives with the Pyodide `314.0.2` xbuild environment. `ormsgpack` additionally applies the recorded narrow CPython 3.14 patch before `pyodide build`; the patch replaces a private five-argument integer conversion with CPython's public `PyLong_AsNativeBytes` API. The lock binds both the source and patch hashes to the resulting wheel.

The wheels retain their upstream `.dist-info` metadata and included license files. This inventory documents distribution; it does not approve external release. `SOURCE_PROVENANCE.md` records the unresolved source-course license, and the `grandalf` row remains a named third-party review item because the original course executes LangChain's `draw_ascii()` path.

## Batching and Python threads

The course keeps the real LangChain and LangGraph `batch()` APIs. At startup, the compatibility layer reads the interpreter's thread-capability flag. A pthread-capable Python runtime keeps LangChain's normal GIL-locked thread-pool executor. Pyodide 314.0.2 reports no pthread support, so this browser build uses an ordered executor that completes every batch item instead of raising `RuntimeError: can't start new thread`. The page reports which scheduler is active after the first cell runs.

This distinction is enforced rather than inferred from browser features. Pyodide's [threading FAQ](https://pyodide.org/en/stable/usage/faq.html#can-i-use-threading-multiprocessing-subprocess) says its official build cannot start pthreads, and its [ABI flags](https://pyodide.org/en/stable/development/abi/flags.html#pthread) explain that pthreads are incompatible with the dynamic linking used by this package stack. Web Workers can keep the interface responsive or host isolated interpreters, but they cannot provide a shared Python heap for arbitrary notebook closures; presenting them as CPython threads would change the semantics of these source cells.

The upstream [experimental pthreads pull request](https://github.com/pyodide/pyodide/pull/6285) is a future integration candidate, not the runtime shipped here. Its prototype requires a second pthread ABI, rebuilding every native wheel, and COOP/COEP deployment headers. It also identifies Pyodide's JavaScript FFI as unsafe from spawned threads. This course's NVIDIA transport crosses that FFI boundary, so the prototype must prove main-thread transport dispatch before threaded model batches can replace the ordered fallback.
